from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from app.domain import (
    BindingEdit,
    BindingReference,
    BindingSession,
    GameCatalog,
    GameCatalogVersion,
    TriggerMode,
)
from app.models.joystick import JoyAction, JoyStickButton, JoystickConfig

from .ui_models import (
    ProjectedBindingRow,
    ProjectedSessionView,
    SessionCatalogEntry,
    UiDiagnosticRow,
)


ROLE_TO_SIDE = {
    "left_stick": "left",
    "right_stick": "right",
}


def build_session_catalog_entries(
    catalog: GameCatalog,
    *,
    selected_trigger_mode: TriggerMode | None = None,
) -> list[SessionCatalogEntry]:
    entries: list[SessionCatalogEntry] = []
    for action_name in sorted(catalog.actions_by_name):
        entry = catalog.entry_for(action_name, None)
        if entry is None or not entry.supports_joystick:
            continue
        if selected_trigger_mode is not None and selected_trigger_mode not in entry.supported_trigger_modes:
            continue
        entries.append(
            SessionCatalogEntry(
                action_name=entry.action_name,
                actionmap_name=entry.actionmap_name,
                category=entry.category,
                subcategory=entry.subcategory,
                display_label=entry.display_label,
                supports_joystick=entry.supports_joystick,
                supported_trigger_modes=entry.supported_trigger_modes,
            )
        )

    return sorted(
        entries,
        key=lambda entry: (
            entry.category.casefold(),
            entry.subcategory.casefold(),
            entry.display_label.casefold(),
            entry.action_name,
            entry.actionmap_name or "",
        ),
    )


def project_session_view(
    session: BindingSession,
    *,
    joystick_buttons_by_slot: Mapping[str, JoyStickButton],
) -> ProjectedSessionView:
    projection = ProjectedSessionView(
        left_config=JoystickConfig(side="left", configured_actions={}),
        right_config=JoystickConfig(side="right", configured_actions={}),
    )
    catalog = (
        session.catalog_snapshot.catalog
        if session.catalog_snapshot is not None
        else GameCatalog(version=GameCatalogVersion(key="unknown"))
    )

    valid_rows: list[tuple[tuple[str, ...], ProjectedBindingRow, JoyAction]] = []
    for binding in session.profile.bindings:
        side = ROLE_TO_SIDE.get(binding.role)
        if side is None:
            projection.diagnostics.append(
                UiDiagnosticRow(
                    kind="unsupported-role",
                    action=binding.action_name,
                    detail=f"Role '{binding.role}' cannot be rendered in the joystick UI.",
                    side="unknown",
                    record_id=binding.source_record_id,
                )
            )
            continue

        entry = catalog.entry_for(binding.action_name, binding.source_actionmap_name)
        if entry is None:
            projection.diagnostics.append(_metadata_diagnostic(binding, catalog, side))
            continue

        device_token = session.profile.role_device_tokens.get(binding.role)
        if not device_token:
            projection.diagnostics.append(
                UiDiagnosticRow(
                    kind="unresolved-device",
                    action=binding.action_name,
                    detail=f"Role '{binding.role}' has no imported device token for UI projection.",
                    side=side,
                    record_id=binding.source_record_id,
                )
            )
            continue

        button = joystick_buttons_by_slot.get(binding.slot_id)
        if button is None:
            projection.diagnostics.append(
                UiDiagnosticRow(
                    kind="unrenderable-slot",
                    action=binding.action_name,
                    detail=f"Slot '{binding.slot_id}' cannot be rendered in the current joystick layout.",
                    side=side,
                    record_id=binding.source_record_id,
                )
            )
            continue

        row = ProjectedBindingRow(
            binding_ref=BindingReference(
                role=binding.role,
                slot_id=binding.slot_id,
                action_name=binding.action_name,
                trigger_mode=binding.trigger_mode,
                modifier_token=binding.modifier_token,
                source_record_id=binding.source_record_id,
                source_actionmap_name=binding.source_actionmap_name,
                replaced_passthrough_record_id=binding.replaced_passthrough_record_id,
            ),
            side=side,
            button_name=button.name,
            slot_id=binding.slot_id,
            action_name=binding.action_name,
            display_label=entry.display_label,
            modifier=binding.trigger_mode is TriggerMode.MODIFIER,
            hold=binding.trigger_mode is TriggerMode.HOLD,
            multitap=binding.trigger_mode is TriggerMode.MULTITAP,
        )
        action = JoyAction(
            name=binding.action_name,
            input=_build_binding_input(binding, device_token),
            category=entry.category,
            sub_category=entry.subcategory,
            modifier=row.modifier,
            hold=row.hold,
            multitap=row.multitap,
            button=button.model_copy(),
        )
        valid_rows.append((_binding_snapshot_key(binding), row, action))

    grouped_rows: dict[tuple[str, str, TriggerMode], list[tuple[tuple[str, ...], ProjectedBindingRow, JoyAction]]] = defaultdict(list)
    for item in valid_rows:
        _, row, _ = item
        grouped_rows[(row.side, row.action_name, row.binding_ref.trigger_mode)].append(item)

    selected_rows: list[tuple[tuple[str, ...], ProjectedBindingRow, JoyAction]] = []
    for collisions in grouped_rows.values():
        collisions.sort(key=lambda item: item[0])
        winner = collisions[0]
        selected_rows.append(winner)
        for _, row, overflow_action in collisions[1:]:
            projection.diagnostics.append(
                UiDiagnosticRow(
                    kind="projection-overflow",
                    action=row.action_name,
                    detail=(
                        f"Binding for slot '{overflow_action.button.sc_config_name}' is hidden because the legacy "
                        "projection can render only one binding per action and trigger mode on each side."
                    ),
                    side=row.side,
                    record_id=row.binding_ref.source_record_id,
                )
            )

    selected_rows.sort(key=lambda item: item[0])
    for _, row, action in selected_rows:
        target_config = projection.left_config if row.side == "left" else projection.right_config
        target_config.set_mapping(action)
        projection.binding_rows.append(row)

    return projection


def _metadata_diagnostic(
    binding: BindingEdit,
    catalog: GameCatalog,
    side: str,
) -> UiDiagnosticRow:
    action_entries = catalog.actions_by_name.get(binding.action_name, ())
    if not action_entries:
        return UiDiagnosticRow(
            kind="unknown-action",
            action=binding.action_name,
            detail=f"Action '{binding.action_name}' is missing from the active session catalog.",
            side=side,
            record_id=binding.source_record_id,
        )

    if binding.source_actionmap_name is not None and all(
        entry.actionmap_name != binding.source_actionmap_name for entry in action_entries
    ):
        return UiDiagnosticRow(
            kind="unknown-actionmap",
            action=binding.action_name,
            detail=(
                f"Action '{binding.action_name}' is not present in actionmap '{binding.source_actionmap_name}'."
            ),
            side=side,
            record_id=binding.source_record_id,
        )

    return UiDiagnosticRow(
        kind="ambiguous-actionmap",
        action=binding.action_name,
        detail=(
            f"Action '{binding.action_name}' requires actionmap provenance for projection."
        ),
        side=side,
        record_id=binding.source_record_id,
    )


def _build_binding_input(binding: BindingEdit, device_token: str) -> str:
    if binding.trigger_mode is TriggerMode.MODIFIER and binding.modifier_token:
        return f"{device_token}_{binding.modifier_token}+{binding.slot_id}"
    return f"{device_token}_{binding.slot_id}"


def _binding_snapshot_key(binding: BindingEdit) -> tuple[str, ...]:
    return (
        binding.role,
        binding.slot_id,
        binding.action_name,
        binding.trigger_mode.value,
        binding.modifier_token or "",
        binding.source_actionmap_name or "",
        binding.replaced_passthrough_record_id or "",
    )
