from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from app.domain import (
    BindingEdit,
    BindingInput,
    BindingReference,
    BindingSession,
    Diagnostic,
    ExportResult,
    PassthroughConflict,
    SessionCatalogSnapshot,
    TriggerMode,
)
from app.domain.models import ActionIdentifier, Binding, BindingSet, ControlProfile, InputSlot
from app.config import Config
from app.io import StarCitizenProfileRepository
from app.services.binding_planner import BindingPlanner, BindingPlannerContext


class BindingSessionService:
    def __init__(
        self,
        profile_repository: StarCitizenProfileRepository,
        planner: BindingPlanner | None = None,
    ) -> None:
        self.profile_repository = profile_repository
        self._planner = planner or BindingPlanner(BindingPlannerContext())
        self._session: BindingSession | None = None
        self._baseline_profile: ControlProfile | None = None

    def open_profile(self, path: Path, imported_role_map: dict[str, str]) -> BindingSession:
        catalog = deepcopy(self.profile_repository.catalog_repo.load())
        self._session = self.profile_repository.load_profile(path, imported_role_map, catalog=catalog)
        self._session.catalog_snapshot = SessionCatalogSnapshot(version=catalog.version, catalog=catalog)
        self._baseline_profile = self._to_control_profile(self._session)
        return self._session

    def bind(self, role: str, slot: str, action: str, trigger_mode: str) -> BindingSession:
        session = self._require_session()
        parsed_trigger_mode = TriggerMode(trigger_mode)
        catalog = self._active_catalog(session)
        existing_binding = self._find_slot_binding(session, role, slot, parsed_trigger_mode)
        source_actionmap_name = None
        if (
            existing_binding is not None
            and existing_binding.source_actionmap_name in catalog.actionmaps_by_name.get(action, ())
        ):
            source_actionmap_name = existing_binding.source_actionmap_name
        if not self._validate_binding_request(
            session,
            role,
            slot,
            action,
            parsed_trigger_mode,
            source_actionmap_name=source_actionmap_name,
        ):
            return session
        return self._upsert_binding(
            session=session,
            role=role,
            slot=slot,
            action=action,
            trigger_mode=parsed_trigger_mode,
            source_actionmap_name=source_actionmap_name,
        )

    def unbind(self, role: str, slot: str, trigger_mode: str) -> BindingSession:
        session = self._require_session()
        parsed_trigger_mode = TriggerMode(trigger_mode)
        session.profile.bindings = [
            binding
            for binding in session.profile.bindings
            if not (
                binding.role == role
                and binding.slot_id == slot
                and binding.trigger_mode is parsed_trigger_mode
            )
        ]
        return session

    def remove_binding(self, binding_ref: BindingReference) -> BindingSession:
        session = self._require_session()
        binding_index = self._find_binding_index(session, binding_ref)
        if binding_index is None:
            return session

        session.profile.bindings.pop(binding_index)
        return session

    def move_binding(self, binding_ref: BindingReference, target_slot: str) -> BindingSession:
        session = self._require_session()
        binding_index = self._find_binding_index(session, binding_ref)
        if binding_index is None:
            return session

        source_binding = session.profile.bindings[binding_index]
        if source_binding.slot_id == target_slot:
            return session

        catalog = self._active_catalog(session)
        target_binding = self._find_slot_binding(
            session,
            source_binding.role,
            target_slot,
            source_binding.trigger_mode,
        )
        if len(catalog.actionmaps_by_name.get(source_binding.action_name, ())) > 1:
            session.diagnostics.append(
                Diagnostic(
                    code="ambiguous-actionmap",
                    level="error",
                    message=(
                        f"Action '{source_binding.action_name}' exists in multiple actionmaps and "
                        "cannot be moved without explicit provenance."
                    ),
                )
            )
            return session

        if target_binding is not None and len(catalog.actionmaps_by_name.get(target_binding.action_name, ())) > 1:
            session.diagnostics.append(
                Diagnostic(
                    code="ambiguous-actionmap",
                    level="error",
                    message=(
                        f"Action '{target_binding.action_name}' exists in multiple actionmaps and "
                        "cannot be displaced through a move."
                    ),
                )
            )
            return session

        if not self._validate_binding_request(
            session,
            source_binding.role,
            target_slot,
            source_binding.action_name,
            source_binding.trigger_mode,
            source_actionmap_name=source_binding.source_actionmap_name,
        ):
            return session

        original_bindings = deepcopy(session.profile.bindings)
        try:
            session.profile.bindings.pop(binding_index)
            return self._upsert_binding(
                session=session,
                role=source_binding.role,
                slot=target_slot,
                action=source_binding.action_name,
                trigger_mode=source_binding.trigger_mode,
                modifier_token=source_binding.modifier_token,
                source_record_id=source_binding.source_record_id,
                source_actionmap_name=source_binding.source_actionmap_name,
                replaced_passthrough_record_id=source_binding.replaced_passthrough_record_id,
            )
        except Exception:
            session.profile.bindings = original_bindings
            raise

    def replace_passthrough(self, conflict_id: str, replacement_binding: BindingInput) -> BindingSession:
        session = self._require_session()
        if not self._validate_binding_request(
            session,
            replacement_binding.role,
            replacement_binding.slot_id,
            replacement_binding.action_name,
            replacement_binding.trigger_mode,
        ):
            return session
        record_id = conflict_id.removeprefix("conflict:")
        session = self._drop_conflicting_bindings(session, conflict_id)
        return self._upsert_binding(
            session=session,
            role=replacement_binding.role,
            slot=replacement_binding.slot_id,
            action=replacement_binding.action_name,
            trigger_mode=replacement_binding.trigger_mode,
            modifier_token=replacement_binding.modifier_token,
            replaced_passthrough_record_id=record_id,
        )

    def preserve_passthrough(self, conflict_id: str) -> BindingSession:
        session = self._require_session()
        return self._drop_conflicting_bindings(session, conflict_id)

    def discard_pending_edit(self, conflict_id: str) -> BindingSession:
        session = self._require_session()
        return self._drop_conflicting_bindings(session, conflict_id)

    def export(self) -> ExportResult:
        session = self._require_session()
        conflicts = self._detect_passthrough_conflicts(session)
        if conflicts:
            return ExportResult(
                changed_bindings=list(session.profile.bindings),
                preserved_passthrough_count=len(session.profile.passthrough_records),
                blocked_conflicts=conflicts,
            )

        baseline_profile = self._baseline_profile or self._empty_control_profile(session.profile.profile_name)
        desired_profile = self._to_control_profile(session)
        self._planner.context.default_profile = baseline_profile
        validation_report = self._planner.validate_plan(
            self._planner.plan_diff(baseline_profile, desired_profile.iter_bindings())
        )
        if validation_report.has_errors:
            for issue in validation_report.issues:
                session.diagnostics.append(
                    Diagnostic(code="validation-error", level=issue.level, message=issue.message)
                )
            return ExportResult(
                changed_bindings=list(session.profile.bindings),
                preserved_passthrough_count=len(session.profile.passthrough_records),
            )

        return self.profile_repository.export_profile(session)

    def _require_session(self) -> BindingSession:
        if self._session is None:
            raise RuntimeError("No profile is open.")
        return self._session

    def _detect_passthrough_conflicts(self, session: BindingSession) -> list[PassthroughConflict]:
        binding_keys = {
            self._binding_key(binding, session.profile.role_device_tokens): binding
            for binding in session.profile.bindings
        }
        actively_replaced_record_ids = {
            binding.replaced_passthrough_record_id
            for binding in session.profile.bindings
            if binding.replaced_passthrough_record_id is not None
        }
        conflicts: list[PassthroughConflict] = []
        for record in session.profile.passthrough_records:
            if record.record_id in actively_replaced_record_ids:
                continue
            key = (record.device_token, record.slot_token, record.trigger_token)
            if key not in binding_keys:
                continue
            conflicts.append(
                PassthroughConflict(
                    conflict_id=f"conflict:{record.record_id}",
                    record_id=record.record_id,
                    device_token=record.device_token,
                    slot_token=record.slot_token,
                    trigger_token=record.trigger_token,
                    action_name=record.action_name,
                )
            )
        return conflicts

    def _drop_conflicting_bindings(self, session: BindingSession, conflict_id: str) -> BindingSession:
        record_id = conflict_id.removeprefix("conflict:")
        record = next(
            (candidate for candidate in session.profile.passthrough_records if candidate.record_id == record_id),
            None,
        )
        if record is None:
            return session

        conflict_key = (record.device_token, record.slot_token, record.trigger_token)
        session.profile.bindings = [
            binding
            for binding in session.profile.bindings
            if self._binding_key(binding, session.profile.role_device_tokens) != conflict_key
        ]
        return session

    def _upsert_binding(
        self,
        *,
        session: BindingSession,
        role: str,
        slot: str,
        action: str,
        trigger_mode: TriggerMode,
        modifier_token: str | None = None,
        source_record_id: str | None = None,
        source_actionmap_name: str | None = None,
        replaced_passthrough_record_id: str | None = None,
    ) -> BindingSession:
        resolved_modifier_token = modifier_token
        if trigger_mode is TriggerMode.MODIFIER and resolved_modifier_token is None:
            resolved_modifier_token = self._default_modifier_token()

        catalog = self._active_catalog(session)
        entry = catalog.entry_for(action, source_actionmap_name)
        resolved_actionmap_name = entry.actionmap_name if entry is not None else source_actionmap_name

        for binding in session.profile.bindings:
            if binding.role == role and binding.slot_id == slot and binding.trigger_mode is trigger_mode:
                binding.action_name = action
                binding.source_actionmap_name = resolved_actionmap_name
                binding.source_record_id = source_record_id
                binding.replaced_passthrough_record_id = replaced_passthrough_record_id
                if trigger_mode is TriggerMode.MODIFIER:
                    binding.modifier_token = resolved_modifier_token
                else:
                    binding.modifier_token = None
                return session

        session.profile.bindings.append(
            BindingEdit(
                role=role,
                slot_id=slot,
                action_name=action,
                trigger_mode=trigger_mode,
                modifier_token=resolved_modifier_token,
                source_record_id=source_record_id,
                source_actionmap_name=resolved_actionmap_name,
                replaced_passthrough_record_id=replaced_passthrough_record_id,
            )
        )
        return session

    def _validate_binding_request(
        self,
        session: BindingSession,
        role: str,
        slot: str,
        action: str,
        trigger_mode: TriggerMode,
        source_actionmap_name: str | None = None,
    ) -> bool:
        if role not in session.profile.role_device_tokens:
            session.diagnostics.append(
                Diagnostic(
                    code="unresolved-device",
                    level="error",
                    message=f"Role '{role}' has no imported device token for export.",
                )
            )
            return False

        catalog = self._active_catalog(session)
        if action not in catalog.actions_by_name:
            session.diagnostics.append(
                Diagnostic(
                    code="unknown-action",
                    level="error",
                    message=f"Action '{action}' is not present in the loaded catalog.",
                )
            )
            return False

        if catalog.entry_for(action, source_actionmap_name) is None:
            session.diagnostics.append(
                Diagnostic(
                    code="ambiguous-actionmap",
                    level="error",
                    message=f"Action '{action}' exists in multiple actionmaps and cannot be inferred for a new bind.",
                )
            )
            return False

        side = self._role_to_side(role)
        layout = self.profile_repository.layout_repo.load_layout(
            self.profile_repository.layout_repo.SUPPORTED_DEVICE,
            side,
        )
        if layout is None or slot not in layout.slots:
            session.diagnostics.append(
                Diagnostic(
                    code="unknown-slot",
                    level="error",
                    message=f"Slot '{slot}' is not available for role '{role}'.",
                )
            )
            return False

        return True

    def _active_catalog(self, session: BindingSession):
        if session.catalog_snapshot is not None:
            return session.catalog_snapshot.catalog
        return self.profile_repository.catalog_repo.load()

    @staticmethod
    def _find_slot_binding(
        session: BindingSession,
        role: str,
        slot: str,
        trigger_mode: TriggerMode,
    ) -> BindingEdit | None:
        return next(
            (
                binding
                for binding in session.profile.bindings
                if binding.role == role and binding.slot_id == slot and binding.trigger_mode is trigger_mode
            ),
            None,
        )

    def _find_binding_index(
        self,
        session: BindingSession,
        binding_ref: BindingReference,
    ) -> int | None:
        for index, binding in enumerate(session.profile.bindings):
            if self._binding_matches_reference(binding, binding_ref):
                return index
        return None

    @staticmethod
    def _binding_matches_reference(binding: BindingEdit, binding_ref: BindingReference) -> bool:
        return (
            binding.role == binding_ref.role
            and binding.slot_id == binding_ref.slot_id
            and binding.action_name == binding_ref.action_name
            and binding.trigger_mode is binding_ref.trigger_mode
            and binding.modifier_token == binding_ref.modifier_token
            and binding.source_record_id == binding_ref.source_record_id
            and binding.source_actionmap_name == binding_ref.source_actionmap_name
            and binding.replaced_passthrough_record_id == binding_ref.replaced_passthrough_record_id
        )

    def _to_control_profile(self, session: BindingSession) -> ControlProfile:
        left_bindings = BindingSet(side="left")
        right_bindings = BindingSet(side="right")

        for binding in session.profile.bindings:
            side = self._role_to_side(binding.role)
            binding_set = left_bindings if side == "left" else right_bindings
            device_uid = session.profile.role_device_tokens.get(binding.role, binding.role)
            binding_set.add(
                Binding(
                    action=ActionIdentifier(
                        name=binding.action_name,
                        main_category="",
                        sub_category="",
                    ),
                    slot=InputSlot(device_uid=device_uid, side=side, slot_id=binding.slot_id),
                    modifier=binding.trigger_mode is TriggerMode.MODIFIER,
                    hold=binding.trigger_mode is TriggerMode.HOLD,
                    multitap=binding.trigger_mode is TriggerMode.MULTITAP,
                )
            )

        return ControlProfile(
            profile_name=session.profile.profile_name,
            left=left_bindings,
            right=right_bindings,
        )

    @staticmethod
    def _empty_control_profile(profile_name: str) -> ControlProfile:
        return ControlProfile(
            profile_name=profile_name,
            left=BindingSet(side="left"),
            right=BindingSet(side="right"),
        )

    def _binding_key(
        self,
        binding: BindingEdit,
        role_device_tokens: dict[str, str],
    ) -> tuple[str, str, str]:
        device_token = role_device_tokens.get(binding.role, binding.role)
        if binding.trigger_mode is TriggerMode.MODIFIER:
            trigger_token = f"modifier:{binding.modifier_token or 'modifier'}"
        else:
            trigger_token = binding.trigger_mode.value
        return (device_token, binding.slot_id, trigger_token)

    @staticmethod
    def _role_to_side(role: str) -> str:
        if role.startswith("left"):
            return "left"
        if role.startswith("right"):
            return "right"
        return role

    @staticmethod
    def _default_modifier_token() -> str:
        return Config.get_config().modifier_key