from __future__ import annotations

from pathlib import Path

from app.domain import (
    BindingEdit,
    BindingInput,
    BindingSession,
    Diagnostic,
    ExportResult,
    PassthroughConflict,
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
        self._session = self.profile_repository.load_profile(path, imported_role_map)
        self._baseline_profile = self._to_control_profile(self._session)
        return self._session

    def bind(self, role: str, slot: str, action: str, trigger_mode: str) -> BindingSession:
        session = self._require_session()
        return self._upsert_binding(
            session=session,
            role=role,
            slot=slot,
            action=action,
            trigger_mode=TriggerMode(trigger_mode),
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

    def replace_passthrough(self, conflict_id: str, replacement_binding: BindingInput) -> BindingSession:
        session = self._require_session()
        session.profile.passthrough_records = [
            record
            for record in session.profile.passthrough_records
            if record.record_id != conflict_id and conflict_id != f"conflict:{record.record_id}"
        ]
        return self._upsert_binding(
            session=session,
            role=replacement_binding.role,
            slot=replacement_binding.slot_id,
            action=replacement_binding.action_name,
            trigger_mode=replacement_binding.trigger_mode,
            modifier_token=replacement_binding.modifier_token,
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
        conflicts: list[PassthroughConflict] = []
        for record in session.profile.passthrough_records:
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
    ) -> BindingSession:
        resolved_modifier_token = modifier_token
        if trigger_mode is TriggerMode.MODIFIER and resolved_modifier_token is None:
            resolved_modifier_token = self._default_modifier_token()

        for binding in session.profile.bindings:
            if binding.role == role and binding.slot_id == slot and binding.trigger_mode is trigger_mode:
                binding.action_name = action
                if trigger_mode is TriggerMode.MODIFIER:
                    binding.modifier_token = binding.modifier_token or resolved_modifier_token
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
            )
        )
        return session

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