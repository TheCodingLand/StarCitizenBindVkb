from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.domain import (
    BindingEdit,
    BindingSession,
    Diagnostic,
    ExportResult,
    GameCatalog,
    PassthroughRecord,
    SessionCatalogSnapshot,
    TriggerMode,
    UnresolvedBinding,
    WorkingProfile,
)
from app.io.action_catalog_repository import ActionCatalogRepository
from app.io.layout_repository import DeviceLayoutRepository
from app.models.exported_configmap_xml import Action, ActionMap, ExportedActionMapsFile, Rebind, get_action_maps_object


ROLE_TO_SIDE = {
    "left_stick": "left",
    "right_stick": "right",
}


class StarCitizenProfileRepository:
    def __init__(
        self,
        catalog_repo: ActionCatalogRepository,
        layout_repo: DeviceLayoutRepository,
    ) -> None:
        self.catalog_repo = catalog_repo
        self.layout_repo = layout_repo
        self._catalog = None

    def load_profile(
        self,
        path: Path,
        imported_role_map: dict[str, str],
        catalog: GameCatalog | None = None,
    ) -> BindingSession:
        document = get_action_maps_object(str(path))
        profile = WorkingProfile(
            profile_name=document.profileName,
            role_device_tokens={role: device for device, role in imported_role_map.items()},
            source_path=path,
            source_document=document,
        )
        diagnostics: list[Diagnostic] = []
        active_catalog = catalog or self._load_catalog()
        snapshot_catalog = deepcopy(active_catalog)

        for action_map in document.actionmap:
            for action in action_map.action:
                for rebind_index, rebind in enumerate(action.rebind or []):
                    record_id = self._record_id(action_map.name, action.name, rebind_index)
                    classification = self._classify_rebind(
                        action_map_name=action_map.name,
                        action=action,
                        rebind=rebind,
                        record_id=record_id,
                        imported_role_map=imported_role_map,
                        catalog=active_catalog,
                    )
                    if classification is None:
                        continue
                    if isinstance(classification, BindingEdit):
                        profile.bindings.append(classification)
                        profile.editable_source_record_ids.add(record_id)
                        continue

                    profile.passthrough_records.append(classification[0])
                    if classification[1] is not None:
                        diagnostics.append(classification[1])
                        profile.unresolved_bindings.append(classification[2])

        return BindingSession(
            profile=profile,
            diagnostics=diagnostics,
            catalog_snapshot=SessionCatalogSnapshot(
                version=snapshot_catalog.version,
                catalog=snapshot_catalog,
            ),
        )

    def export_profile(self, session: BindingSession) -> ExportResult:
        profile = session.profile
        catalog = session.catalog_snapshot.catalog if session.catalog_snapshot is not None else self._load_catalog()
        actively_replaced_passthrough_ids = {
            binding.replaced_passthrough_record_id
            for binding in profile.bindings
            if binding.replaced_passthrough_record_id is not None
        }
        preserved_passthrough_count = sum(
            1 for record in profile.passthrough_records if record.record_id not in actively_replaced_passthrough_ids
        )
        if profile.source_document is None:
            return ExportResult(
                changed_bindings=list(profile.bindings),
                preserved_passthrough_count=preserved_passthrough_count,
            )

        document = profile.source_document.model_copy(deep=True)
        self._remove_source_rebinds(
            document,
            profile.editable_source_record_ids | actively_replaced_passthrough_ids,
        )
        self._apply_bindings(
            document,
            profile.bindings,
            profile.role_device_tokens,
            catalog,
            profile.source_document,
        )

        return ExportResult(
            changed_bindings=list(profile.bindings),
            preserved_passthrough_count=preserved_passthrough_count,
            document=document,
        )

    def align_session_device_tokens(self, session: BindingSession, role_device_tokens: dict[str, str]) -> None:
        current_tokens = dict(session.profile.role_device_tokens)
        normalized_tokens = {
            role: token.strip()
            for role, token in role_device_tokens.items()
            if role in ROLE_TO_SIDE and isinstance(token, str) and token.strip()
        }
        if not normalized_tokens:
            return

        merged_tokens = dict(current_tokens)
        merged_tokens.update(normalized_tokens)
        token_replacements = {
            current_token: merged_tokens[role]
            for role, current_token in current_tokens.items()
            if role in merged_tokens and current_token != merged_tokens[role]
        }
        session.profile.role_device_tokens = merged_tokens

        if not token_replacements:
            return

        for record in session.profile.passthrough_records:
            replacement = token_replacements.get(record.device_token)
            if replacement is not None:
                record.device_token = replacement

        for unresolved in session.profile.unresolved_bindings:
            replacement = token_replacements.get(unresolved.device_token)
            if replacement is not None:
                unresolved.device_token = replacement

        if session.profile.source_document is not None:
            self._remap_document_device_tokens(
                session.profile.source_document,
                token_replacements,
                current_tokens,
                merged_tokens,
            )

    def _load_catalog(self):
        if self._catalog is None:
            self._catalog = self.catalog_repo.load()
        return self._catalog

    def _classify_rebind(
        self,
        *,
        action_map_name: str,
        action: Action,
        rebind: Rebind,
        record_id: str,
        imported_role_map: dict[str, str],
        catalog: Any,
    ) -> BindingEdit | tuple[PassthroughRecord, Diagnostic | None, UnresolvedBinding | None] | None:
        device_token, slot_token, modifier_token = self._split_input_tokens(rebind.input)
        if slot_token == "":
            return None
        trigger_mode = self._trigger_mode_from_rebind(rebind, modifier_token)
        trigger_token = self._trigger_token(trigger_mode, modifier_token)
        raw_payload = {
            "actionmap_name": action_map_name,
            "action_name": action.name,
            "action_title": action.title,
            "rebind": rebind.model_dump(by_alias=True, exclude_none=False),
        }

        if not device_token.startswith("js"):
            return (
                PassthroughRecord(
                    record_id=record_id,
                    action_name=action.name,
                    device_token=device_token,
                    slot_token=slot_token,
                    trigger_token=trigger_token,
                    raw_payload=raw_payload,
                ),
                None,
                None,
            )

        if action.name not in catalog.actions_by_name:
            diagnostic = Diagnostic(
                code="unknown-action",
                level="warning",
                message=f"Unknown action '{action.name}' preserved as passthrough.",
                record_id=record_id,
            )
            unresolved = UnresolvedBinding(
                record_id=record_id,
                action_name=action.name,
                device_token=device_token,
                slot_token=slot_token,
                reason=diagnostic.code,
            )
            return (
                PassthroughRecord(
                    record_id=record_id,
                    action_name=action.name,
                    device_token=device_token,
                    slot_token=slot_token,
                    trigger_token=trigger_token,
                    raw_payload=raw_payload,
                ),
                diagnostic,
                unresolved,
            )

        if catalog.entry_for(action.name, action_map_name) is None:
            diagnostic = Diagnostic(
                code="unknown-actionmap",
                level="warning",
                message=(
                    f"Action '{action.name}' is not present in actionmap '{action_map_name}' and "
                    "was preserved as passthrough."
                ),
                record_id=record_id,
            )
            unresolved = UnresolvedBinding(
                record_id=record_id,
                action_name=action.name,
                device_token=device_token,
                slot_token=slot_token,
                reason=diagnostic.code,
            )
            return (
                PassthroughRecord(
                    record_id=record_id,
                    action_name=action.name,
                    device_token=device_token,
                    slot_token=slot_token,
                    trigger_token=trigger_token,
                    raw_payload=raw_payload,
                ),
                diagnostic,
                unresolved,
            )

        role = imported_role_map.get(device_token)
        if role is None:
            diagnostic = Diagnostic(
                code="unresolved-device",
                level="warning",
                message=f"Device token '{device_token}' could not be matched to a role.",
                record_id=record_id,
            )
            unresolved = UnresolvedBinding(
                record_id=record_id,
                action_name=action.name,
                device_token=device_token,
                slot_token=slot_token,
                reason=diagnostic.code,
            )
            return (
                PassthroughRecord(
                    record_id=record_id,
                    action_name=action.name,
                    device_token=device_token,
                    slot_token=slot_token,
                    trigger_token=trigger_token,
                    raw_payload=raw_payload,
                ),
                diagnostic,
                unresolved,
            )

        layout = self._load_role_layout(role)
        if layout is None or slot_token not in layout.slots:
            diagnostic = Diagnostic(
                code="unknown-slot",
                level="warning",
                message=f"Unknown slot '{slot_token}' preserved as passthrough.",
                record_id=record_id,
            )
            unresolved = UnresolvedBinding(
                record_id=record_id,
                action_name=action.name,
                device_token=device_token,
                slot_token=slot_token,
                reason=diagnostic.code,
            )
            return (
                PassthroughRecord(
                    record_id=record_id,
                    action_name=action.name,
                    device_token=device_token,
                    slot_token=slot_token,
                    trigger_token=trigger_token,
                    raw_payload=raw_payload,
                ),
                diagnostic,
                unresolved,
            )

        return BindingEdit(
            role=role,
            slot_id=slot_token,
            action_name=action.name,
            trigger_mode=trigger_mode,
            modifier_token=modifier_token,
            source_record_id=record_id,
            source_actionmap_name=action_map_name,
        )

    def _load_role_layout(self, role: str):
        side = ROLE_TO_SIDE.get(role)
        if side is None:
            return None
        return self.layout_repo.load_layout(self.layout_repo.SUPPORTED_DEVICE, side)

    @staticmethod
    def _record_id(actionmap_name: str, action_name: str, rebind_index: int) -> str:
        return f"{actionmap_name}:{action_name}:{rebind_index}"

    @staticmethod
    def _split_input_tokens(raw_input: str) -> tuple[str, str, str | None]:
        normalized = (raw_input or "").strip()
        if "_" not in normalized:
            return normalized, "", None

        device_token, remainder = normalized.split("_", 1)
        remainder = remainder.strip()
        modifier_token = None
        slot_token = remainder
        if "+" in remainder:
            modifier_token, slot_token = remainder.split("+", 1)
            modifier_token = modifier_token.strip() or None
            slot_token = slot_token.strip()
        return device_token, slot_token, modifier_token

    @staticmethod
    def _trigger_mode_from_rebind(rebind: Rebind, modifier_token: str | None) -> TriggerMode:
        activation_mode = str((rebind.model_extra or {}).get("@activationMode") or "").strip().lower()
        if rebind.multitap not in {None, 0} or activation_mode.startswith("double_tap"):
            return TriggerMode.MULTITAP
        if activation_mode.startswith("delayed_press"):
            return TriggerMode.HOLD
        if modifier_token:
            return TriggerMode.MODIFIER
        return TriggerMode.PLAIN

    @staticmethod
    def _trigger_token(trigger_mode: TriggerMode, modifier_token: str | None) -> str:
        if trigger_mode is TriggerMode.MODIFIER:
            return f"modifier:{modifier_token or 'modifier'}"
        return trigger_mode.value

    def _remove_source_rebinds(
        self,
        document: ExportedActionMapsFile,
        removed_record_ids: set[str],
    ) -> None:
        for action_map in document.actionmap:
            for action in action_map.action:
                action.rebind = [
                    rebind
                    for rebind_index, rebind in enumerate(action.rebind or [])
                    if self._record_id(action_map.name, action.name, rebind_index)
                    not in removed_record_ids
                ]

    def _apply_bindings(
        self,
        document: ExportedActionMapsFile,
        bindings: list[BindingEdit],
        role_device_tokens: dict[str, str],
        catalog: GameCatalog,
        source_document: ExportedActionMapsFile | None,
    ) -> None:
        actionmaps_by_name = {action_map.name: action_map for action_map in document.actionmap}

        grouped_bindings: dict[str, list[BindingEdit]] = defaultdict(list)
        for binding in bindings:
            if binding.source_actionmap_name is not None:
                if catalog.entry_for(binding.action_name, binding.source_actionmap_name) is None:
                    raise ValueError(
                        f"Action '{binding.action_name}' is not present in actionmap '{binding.source_actionmap_name}'."
                    )
                actionmap_name = binding.source_actionmap_name
            else:
                if len(catalog.actionmaps_by_name.get(binding.action_name, ())) > 1:
                    raise ValueError(
                        f"Action '{binding.action_name}' exists in multiple actionmaps and requires source actionmap context."
                    )
                actionmap_name = catalog.actionmap_by_name.get(binding.action_name)
            if actionmap_name is None:
                raise ValueError(f"Unknown catalog action '{binding.action_name}'.")
            grouped_bindings[actionmap_name].append(binding)

        for actionmap_name, action_bindings in grouped_bindings.items():
            action_map = actionmaps_by_name.get(actionmap_name)
            if action_map is None:
                action_map = ActionMap(name=actionmap_name, action=[])
                document.actionmap.append(action_map)
                actionmaps_by_name[actionmap_name] = action_map

            for binding in action_bindings:
                layout = self._load_role_layout(binding.role)
                if layout is None or binding.slot_id not in layout.slots:
                    raise ValueError(
                        f"Unknown slot '{binding.slot_id}' for role '{binding.role}'."
                    )
                action = next(
                    (candidate for candidate in action_map.action if candidate.name == binding.action_name),
                    None,
                )
                if action is None:
                    action = Action(name=binding.action_name, rebind=[])
                    action_map.action.append(action)

                rendered_input = self._render_binding_input(binding, role_device_tokens)
                new_rebind = self._build_rebind(
                    rendered_input,
                    binding,
                    modifier_activation_mode=self._modifier_activation_mode(binding, source_document),
                )
                if any(
                    self._rebind_signature(existing) == self._rebind_signature(new_rebind)
                    for existing in action.rebind
                ):
                    continue
                action.rebind.append(new_rebind)

    def _remap_document_device_tokens(
        self,
        document: ExportedActionMapsFile,
        token_replacements: dict[str, str],
        previous_role_tokens: dict[str, str],
        current_role_tokens: dict[str, str],
    ) -> None:
        for action_map in document.actionmap:
            for action in action_map.action:
                for rebind in action.rebind or []:
                    original_input = rebind.input or ""
                    if "_" not in original_input:
                        continue
                    device_token, remainder = original_input.split("_", 1)
                    replacement = token_replacements.get(device_token)
                    if replacement is not None:
                        rebind.input = f"{replacement}_{remainder}"

        instance_replacements = {
            previous_instance: current_instance
            for role, previous_token in previous_role_tokens.items()
            if role in current_role_tokens
            if (previous_instance := self._device_instance(previous_token)) is not None
            if (current_instance := self._device_instance(current_role_tokens[role])) is not None
            if previous_instance != current_instance
        }
        if not instance_replacements:
            return

        for option in document.options:
            if option.type != "joystick":
                continue
            replacement = instance_replacements.get(option.instance)
            if replacement is not None:
                option.instance = replacement

        for customization in document.customizations:
            for device_group in customization.devices:
                for device_type, devices in device_group.items():
                    if device_type.lower() != "joystick":
                        continue
                    for device in devices:
                        replacement = instance_replacements.get(self._device_instance(f"js{device.instance}"))
                        if replacement is not None:
                            device.instance = str(replacement)

    @staticmethod
    def _device_instance(device_token: str | None) -> int | None:
        if device_token is None:
            return None
        normalized = str(device_token).strip()
        if not normalized.startswith("js"):
            return None
        try:
            return int(normalized[2:])
        except ValueError:
            return None

    def _render_binding_input(
        self,
        binding: BindingEdit,
        role_device_tokens: dict[str, str],
    ) -> str:
        device_token = role_device_tokens.get(binding.role)
        if device_token is None:
            raise ValueError(f"Missing imported device token for role '{binding.role}'.")
        if binding.trigger_mode is TriggerMode.MODIFIER and binding.modifier_token:
            return f"{device_token}_{binding.modifier_token}+{binding.slot_id}"
        return f"{device_token}_{binding.slot_id}"

    @staticmethod
    def _build_rebind(
        rendered_input: str,
        binding: BindingEdit,
        *,
        modifier_activation_mode: str | None = None,
    ) -> Rebind:
        payload: dict[str, Any] = {"@input": rendered_input}
        if binding.trigger_mode is TriggerMode.MULTITAP:
            payload["@multiTap"] = 2
        if binding.trigger_mode is TriggerMode.MODIFIER and modifier_activation_mode is not None:
            payload["@activationMode"] = modifier_activation_mode
        if binding.trigger_mode is TriggerMode.HOLD:
            payload["@activationMode"] = "delayed_press"
        return Rebind.model_validate(payload)

    def _modifier_activation_mode(
        self,
        binding: BindingEdit,
        source_document: ExportedActionMapsFile | None,
    ) -> str | None:
        if binding.trigger_mode is not TriggerMode.MODIFIER:
            return None
        if source_document is None or binding.source_record_id is None:
            return None

        actionmap_name, action_name, rebind_index = binding.source_record_id.rsplit(":", 2)
        try:
            index = int(rebind_index)
        except ValueError:
            return None

        action_map = next((item for item in source_document.actionmap if item.name == actionmap_name), None)
        if action_map is None:
            return None
        action = next((item for item in action_map.action if item.name == action_name), None)
        if action is None:
            return None
        rebinds = action.rebind or []
        if index >= len(rebinds):
            return None

        activation_mode = str((rebinds[index].model_extra or {}).get("@activationMode") or "").strip().lower()
        if activation_mode == "press":
            return activation_mode
        return None

    @staticmethod
    def _rebind_signature(rebind: Rebind) -> tuple[str, int | None, str | None]:
        activation_mode = str((rebind.model_extra or {}).get("@activationMode") or "").strip().lower() or None
        multitap = rebind.multitap if rebind.multitap not in {None, 0} else None
        return (rebind.input, multitap, activation_mode)