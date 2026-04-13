from __future__ import annotations

from pathlib import Path
from typing import Callable

from app.domain import (
    ActionDefinition,
    ActionIdentifier,
    BindingEdit,
    BindingReference,
    BindingSession,
    Diagnostic,
    ExportResult,
    GameCatalog,
    GameCatalogVersion,
    PassthroughConflict,
    SessionCatalogSnapshot,
    TriggerMode,
    UnresolvedBinding,
    WorkingProfile,
)
from app.models.joystick import get_joystick_buttons
from app.services import UiCommandOutcome
from app.services.ui_session_controller import UiSessionController


def make_action_definition(
    action_name: str,
    *,
    actionmap_name: str,
    category: str = "Vehicles",
    subcategory: str = "Flight",
    display_label: str | None = None,
    supports_joystick: bool = True,
    supported_trigger_modes: tuple[TriggerMode, ...] = (
        TriggerMode.PLAIN,
        TriggerMode.MODIFIER,
        TriggerMode.HOLD,
        TriggerMode.MULTITAP,
    ),
) -> ActionDefinition:
    return ActionDefinition(
        identifier=ActionIdentifier(
            name=action_name,
            main_category=category,
            sub_category=subcategory,
        ),
        action_name=action_name,
        actionmap_name=actionmap_name,
        category=category,
        subcategory=subcategory,
        display_label=display_label or action_name,
        supports_joystick=supports_joystick,
        supported_trigger_modes=supported_trigger_modes,
    )


def make_catalog(*entries: ActionDefinition) -> GameCatalog:
    catalog = GameCatalog(version=GameCatalogVersion(key="test-catalog"))
    for entry in entries:
        catalog.actions_by_name.setdefault(entry.action_name, []).append(entry)
        catalog.entries_by_key[(entry.action_name, entry.actionmap_name)] = entry
        if entry.actionmap_name:
            actionmaps = catalog.actionmaps_by_name.get(entry.action_name, ())
            if entry.actionmap_name not in actionmaps:
                catalog.actionmaps_by_name[entry.action_name] = (*actionmaps, entry.actionmap_name)
            catalog.actionmap_by_name.setdefault(entry.action_name, entry.actionmap_name)
    return catalog


def make_binding(
    action_name: str,
    *,
    role: str = "left_stick",
    slot_id: str = "button1",
    trigger_mode: TriggerMode = TriggerMode.PLAIN,
    modifier_token: str | None = None,
    source_actionmap_name: str | None = None,
    source_record_id: str | None = None,
) -> BindingEdit:
    return BindingEdit(
        role=role,
        slot_id=slot_id,
        action_name=action_name,
        trigger_mode=trigger_mode,
        modifier_token=modifier_token,
        source_actionmap_name=source_actionmap_name,
        source_record_id=source_record_id,
    )


def make_session(
    *,
    catalog: GameCatalog,
    bindings: list[BindingEdit] | None = None,
    role_device_tokens: dict[str, str] | None = None,
    diagnostics: list[Diagnostic] | None = None,
    unresolved_bindings: list[UnresolvedBinding] | None = None,
) -> BindingSession:
    return BindingSession(
        profile=WorkingProfile(
            profile_name="ControllerTest",
            bindings=list(bindings or []),
            role_device_tokens=role_device_tokens or {"left_stick": "js1", "right_stick": "js2"},
            unresolved_bindings=list(unresolved_bindings or []),
        ),
        diagnostics=list(diagnostics or []),
        catalog_snapshot=SessionCatalogSnapshot(version=catalog.version, catalog=catalog),
    )


def make_binding_reference(binding: BindingEdit) -> BindingReference:
    return BindingReference(
        role=binding.role,
        slot_id=binding.slot_id,
        action_name=binding.action_name,
        trigger_mode=binding.trigger_mode,
        modifier_token=binding.modifier_token,
        source_record_id=binding.source_record_id,
        source_actionmap_name=binding.source_actionmap_name,
        replaced_passthrough_record_id=binding.replaced_passthrough_record_id,
    )


def joystick_buttons_by_slot() -> dict[str, object]:
    return {
        button.sc_config_name: button
        for button in get_joystick_buttons("VKB Default").values()
    }


class FakeSessionService:
    def __init__(
        self,
        *,
        session: BindingSession | None = None,
        export_steps: list[ExportResult | Callable[[BindingSession], ExportResult]] | None = None,
    ) -> None:
        self.session = session
        self.export_steps = list(export_steps or [])
        self.open_exception: Exception | None = None
        self.export_exception: Exception | None = None
        self.bind_hook: Callable[[BindingSession, str, str, str, str], None] | None = None
        self.move_hook: Callable[[BindingSession, BindingReference, str], None] | None = None
        self.remove_hook: Callable[[BindingSession, BindingReference], None] | None = None
        self.open_calls: list[tuple[Path, dict[str, str], dict[str, str] | None]] = []
        self.bind_calls: list[tuple[str, str, str, str]] = []
        self.move_calls: list[tuple[BindingReference, str]] = []
        self.remove_calls: list[BindingReference] = []

    def open_profile(
        self,
        path: Path,
        imported_role_map: dict[str, str],
        export_role_tokens: dict[str, str] | None = None,
    ) -> BindingSession:
        self.open_calls.append((path, dict(imported_role_map), dict(export_role_tokens) if export_role_tokens else None))
        if self.open_exception is not None:
            raise self.open_exception
        if self.session is None:
            raise RuntimeError("No fake session configured")
        return self.session

    def export(self) -> ExportResult:
        if self.export_exception is not None:
            raise self.export_exception
        if self.session is None:
            raise RuntimeError("No fake session configured")
        if self.export_steps:
            step = self.export_steps.pop(0)
            return step(self.session) if callable(step) else step
        return ExportResult(document={"export": "default"})

    def bind(self, role: str, slot: str, action: str, trigger_mode: str) -> BindingSession:
        self.bind_calls.append((role, slot, action, trigger_mode))
        if self.session is None:
            raise RuntimeError("No fake session configured")
        if self.bind_hook is not None:
            replacement = self.bind_hook(self.session, role, slot, action, trigger_mode)
            if isinstance(replacement, BindingSession):
                self.session = replacement
            return self.session

        for binding in self.session.profile.bindings:
            if (
                binding.role == role
                and binding.slot_id == slot
                and binding.trigger_mode.value == trigger_mode
            ):
                binding.action_name = action
                return self.session

        self.session.profile.bindings.append(
            BindingEdit(
                role=role,
                slot_id=slot,
                action_name=action,
                trigger_mode=TriggerMode(trigger_mode),
            )
        )
        return self.session

    def move_binding(self, binding_ref: BindingReference, target_slot: str) -> BindingSession:
        self.move_calls.append((binding_ref, target_slot))
        if self.session is None:
            raise RuntimeError("No fake session configured")
        if self.move_hook is not None:
            replacement = self.move_hook(self.session, binding_ref, target_slot)
            if isinstance(replacement, BindingSession):
                self.session = replacement
            return self.session

        for binding in self.session.profile.bindings:
            if make_binding_reference(binding) == binding_ref:
                binding.slot_id = target_slot
                return self.session
        return self.session

    def remove_binding(self, binding_ref: BindingReference) -> BindingSession:
        self.remove_calls.append(binding_ref)
        if self.session is None:
            raise RuntimeError("No fake session configured")
        if self.remove_hook is not None:
            replacement = self.remove_hook(self.session, binding_ref)
            if isinstance(replacement, BindingSession):
                self.session = replacement
            return self.session

        self.session.profile.bindings = [
            binding for binding in self.session.profile.bindings if make_binding_reference(binding) != binding_ref
        ]
        return self.session


def make_controller(
    service: FakeSessionService,
    resolver: Callable[[Path], dict[str, str] | dict[str, tuple[str, ...]]],
    export_resolver: Callable[[], dict[str, str]] | None = None,
    default_session_resolver: Callable[[dict[str, str], GameCatalog], BindingSession | None] | None = None,
) -> UiSessionController:
    return UiSessionController(
        session_service=service,
        imported_role_resolver=resolver,
        export_role_token_resolver=export_resolver,
        default_session_resolver=default_session_resolver,
        joystick_buttons_by_slot=joystick_buttons_by_slot(),
    )


def test_open_profile_with_partial_role_map_keeps_load_diagnostics() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        diagnostics=[
            Diagnostic(
                code="unresolved-device",
                level="warning",
                message="Device token 'js2' could not be matched to a role.",
                record_id="record-1",
            )
        ],
        unresolved_bindings=[
            UnresolvedBinding(
                record_id="record-1",
                action_name="seat_exit",
                device_token="js2",
                slot_token="button18",
                reason="unresolved-device",
            )
        ],
    )
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"ok": True})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    assert any(
        row.kind == "unresolved-device" and row.action == "seat_exit"
        for row in controller.load_diagnostics
    )


def test_open_profile_passes_configured_export_role_tokens_to_session_service() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        role_device_tokens={"left_stick": "js2", "right_stick": "js1"},
    )
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"ok": True})])
    controller = make_controller(
        service,
        resolver=lambda _: {"js1": "right_stick", "js2": "left_stick"},
        export_resolver=lambda: {"left_stick": "js1", "right_stick": "js2"},
    )

    assert controller.open_profile(Path("profile.xml")) is True
    assert service.open_calls == [
        (
            Path("profile.xml"),
            {"js1": "right_stick", "js2": "left_stick"},
            {"left_stick": "js1", "right_stick": "js2"},
        )
    ]


def test_open_profile_exposes_effective_default_projection_separately_from_explicit_projection() -> None:
    catalog = make_catalog(make_action_definition("default_pitch", actionmap_name="spaceship_movement"))
    session = make_session(catalog=catalog, bindings=[])
    default_session = make_session(
        catalog=catalog,
        bindings=[
            make_binding(
                "default_pitch",
                slot_id="button1",
                source_actionmap_name="spaceship_movement",
            )
        ],
    )
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"ok": True})])
    controller = make_controller(
        service,
        resolver=lambda _: {"js1": "left_stick"},
        export_resolver=lambda: {"left_stick": "js1"},
        default_session_resolver=lambda _tokens, _catalog: default_session,
    )

    assert controller.open_profile(Path("profile.xml")) is True
    assert not controller.left_config.configured_actions
    assert "default_pitch" in {
        action.name for action in controller.effective_left_config.configured_actions.values()
    }
    assert any(row.binding_source == "default" for row in controller.effective_binding_rows)


def test_open_profile_failure_resets_to_safe_empty_state() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(catalog=catalog, bindings=[make_binding("seat_exit", source_actionmap_name="seat_general")])
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"ok": 1})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("good.xml")) is True

    service.open_exception = RuntimeError("load failed")
    assert controller.open_profile(Path("bad.xml")) is False
    assert controller.session is None
    assert controller.binding_rows == []
    assert controller.catalog_entries == []
    assert controller.diagnostics == []
    assert controller.export_state.document is None
    assert controller.export_state.export_enabled is False


def test_role_resolver_exception_resets_to_safe_empty_state() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(catalog=catalog, bindings=[make_binding("seat_exit", source_actionmap_name="seat_general")])
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"ok": 1})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("good.xml")) is True

    def raising_resolver(_: Path) -> dict[str, str]:
        raise RuntimeError("resolver failed")

    controller = make_controller(service, resolver=raising_resolver)
    assert controller.open_profile(Path("bad.xml")) is False
    assert controller.session is None
    assert controller.diagnostics == []
    assert controller.export_state.document is None


def test_imported_role_resolver_drops_ambiguous_or_duplicate_role_matches() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(catalog=catalog)
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"ok": True})])
    controller = make_controller(
        service,
        resolver=lambda _: {
            "js1": ("left_stick", "right_stick"),
            "js2": ("left_stick",),
            "js3": ("left_stick",),
            "js4": ("right_stick",),
        },
    )

    assert controller.open_profile(Path("profile.xml")) is True
    assert service.open_calls[0][1] == {"js4": "right_stick"}


def test_open_profile_exposes_binding_references_for_projected_rows() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding(
        "seat_exit",
        slot_id="button3",
        source_actionmap_name="seat_general",
        source_record_id="record-1",
    )
    session = make_session(catalog=catalog, bindings=[binding])
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"ok": True})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    row = controller.binding_rows[0]
    assert row.binding_ref == make_binding_reference(binding)


def test_catalog_entries_are_exposed_from_active_session_snapshot() -> None:
    catalog = make_catalog(
        make_action_definition("valid_action", actionmap_name="seat_general"),
        make_action_definition("ambiguous_action", actionmap_name="seat_general"),
        make_action_definition("ambiguous_action", actionmap_name="vehicle_general"),
        make_action_definition("keyboard_only", actionmap_name="seat_general", supports_joystick=False, supported_trigger_modes=()),
    )
    session = make_session(catalog=catalog)
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"ok": True})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    assert [entry.action_name for entry in controller.catalog_entries] == ["valid_action"]


def test_open_profile_runs_dry_run_export_and_caches_only_unblocked_document() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))

    success_service = FakeSessionService(
        session=make_session(catalog=catalog),
        export_steps=[ExportResult(document={"document": "ok"})],
    )
    success_controller = make_controller(success_service, resolver=lambda _: {"js1": "left_stick"})
    assert success_controller.open_profile(Path("profile.xml")) is True
    assert success_controller.export_state.document == {"document": "ok"}

    blocked_service = FakeSessionService(
        session=make_session(catalog=catalog),
        export_steps=[
            ExportResult(
                blocked_conflicts=[
                    PassthroughConflict(
                        conflict_id="conflict:1",
                        record_id="1",
                        device_token="js1",
                        slot_token="button1",
                        trigger_token="plain",
                        action_name="seat_exit",
                    )
                ]
            )
        ],
    )
    blocked_controller = make_controller(blocked_service, resolver=lambda _: {"js1": "left_stick"})
    assert blocked_controller.open_profile(Path("profile.xml")) is True
    assert blocked_controller.export_state.document is None
    assert len(blocked_controller.export_state.blocked_conflicts) == 1


def test_invalid_or_stale_action_selection_is_rejected_with_command_diagnostic() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(catalog=catalog)
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"doc": 1})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    previous_document = controller.export_state.document

    outcome = controller.select_action("left", "button2", "missing_action", TriggerMode.PLAIN)

    assert outcome is UiCommandOutcome.REJECTED
    assert any(row.kind == "unknown-action" and row.action == "missing_action" for row in controller.command_diagnostics)
    assert controller.export_state.document == previous_document


def test_move_binding_is_atomic_when_target_bind_is_rejected() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(catalog=catalog, bindings=[binding])
    service = FakeSessionService(
        session=session,
        export_steps=[ExportResult(document={"doc": 1})],
    )

    def reject_move(session: BindingSession, _: BindingReference, __: str) -> None:
        session.diagnostics.append(
            Diagnostic(code="unknown-slot", level="error", message="Target slot is invalid.")
        )

    service.move_hook = reject_move
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})
    assert controller.open_profile(Path("profile.xml")) is True
    previous_document = controller.export_state.document

    outcome = controller.select_action("left", "button2", "seat_exit", TriggerMode.PLAIN)

    assert outcome is UiCommandOutcome.REJECTED
    assert controller.binding_rows[0].slot_id == "button1"
    assert controller.export_state.document == previous_document


def test_move_binding_returns_rejected_when_move_raises_unexpectedly() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(catalog=catalog, bindings=[binding])
    service = FakeSessionService(
        session=session,
        export_steps=[ExportResult(document={"doc": 1})],
    )

    def explode(_: BindingSession, __: BindingReference, ___: str) -> None:
        raise RuntimeError("unexpected move failure")

    service.move_hook = explode
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})
    assert controller.open_profile(Path("profile.xml")) is True
    previous_document = controller.export_state.document

    outcome = controller.select_action("left", "button2", "seat_exit", TriggerMode.PLAIN)

    assert outcome is UiCommandOutcome.REJECTED
    assert controller.binding_rows[0].slot_id == "button1"
    assert controller.export_state.document == previous_document


def test_remove_of_ambiguous_duplicate_name_binding_succeeds_by_identity() -> None:
    catalog = make_catalog(
        make_action_definition("ambiguous_action", actionmap_name="seat_general"),
        make_action_definition("ambiguous_action", actionmap_name="vehicle_general"),
    )
    binding = make_binding(
        "ambiguous_action",
        slot_id="button1",
        source_actionmap_name="seat_general",
        source_record_id="record-1",
    )
    session = make_session(catalog=catalog, bindings=[binding])
    service = FakeSessionService(
        session=session,
        export_steps=[ExportResult(document={"doc": 1}), ExportResult(document={"doc": 2})],
    )
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})
    assert controller.open_profile(Path("profile.xml")) is True

    outcome = controller.remove_binding(controller.binding_rows[0].binding_ref)

    assert outcome is UiCommandOutcome.MUTATED
    assert controller.binding_rows == []


def test_controller_reports_mutated_rejected_and_noop_outcomes() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")

    noop_service = FakeSessionService(
        session=make_session(catalog=catalog, bindings=[make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")]),
        export_steps=[ExportResult(document={"doc": 1})],
    )
    noop_controller = make_controller(noop_service, resolver=lambda _: {"js1": "left_stick"})
    assert noop_controller.open_profile(Path("profile.xml")) is True
    assert noop_controller.move_binding(noop_controller.binding_rows[0].binding_ref, "button1") is UiCommandOutcome.NOOP

    rejected_service = FakeSessionService(
        session=make_session(catalog=catalog, bindings=[make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")]),
        export_steps=[ExportResult(document={"doc": 1})],
    )

    def reject_move(session: BindingSession, _: BindingReference, __: str) -> None:
        session.diagnostics.append(
            Diagnostic(code="unknown-slot", level="error", message="Target slot is invalid.")
        )

    rejected_service.move_hook = reject_move
    rejected_controller = make_controller(rejected_service, resolver=lambda _: {"js1": "left_stick"})
    assert rejected_controller.open_profile(Path("profile.xml")) is True
    assert rejected_controller.move_binding(rejected_controller.binding_rows[0].binding_ref, "button9") is UiCommandOutcome.REJECTED

    mutated_service = FakeSessionService(
        session=make_session(catalog=catalog, bindings=[binding]),
        export_steps=[ExportResult(document={"doc": 1}), ExportResult(document={"doc": 2})],
    )
    mutated_controller = make_controller(mutated_service, resolver=lambda _: {"js1": "left_stick"})
    assert mutated_controller.open_profile(Path("profile.xml")) is True
    assert mutated_controller.remove_binding(mutated_controller.binding_rows[0].binding_ref) is UiCommandOutcome.MUTATED


def test_controller_replaces_only_appended_edit_and_export_diagnostic_slices() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(
        catalog=catalog,
        bindings=[binding],
        diagnostics=[Diagnostic(code="load-warning", level="warning", message="Load warning")],
    )

    def export_with_old_validation(current: BindingSession) -> ExportResult:
        current.diagnostics.append(
            Diagnostic(code="validation-error", level="error", message="Old validation")
        )
        return ExportResult(document=None)

    def export_with_new_validation(current: BindingSession) -> ExportResult:
        current.diagnostics.append(
            Diagnostic(code="validation-error", level="error", message="New validation")
        )
        return ExportResult(document=None)

    service = FakeSessionService(
        session=session,
        export_steps=[export_with_old_validation, export_with_new_validation],
    )

    def reject_move(current: BindingSession, _: BindingReference, __: str) -> None:
        current.diagnostics.append(
            Diagnostic(code="unknown-slot", level="error", message="Edit rejection")
        )

    service.move_hook = reject_move
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})
    assert controller.open_profile(Path("profile.xml")) is True
    assert [row.kind for row in controller.validation_diagnostics] == ["validation-error"]
    assert controller.validation_diagnostics[0].detail == "Old validation"

    outcome = controller.move_binding(controller.binding_rows[0].binding_ref, "button9")
    assert outcome is UiCommandOutcome.REJECTED
    assert [row.kind for row in controller.command_diagnostics] == ["unknown-slot"]
    assert controller.command_diagnostics[0].detail == "Edit rejection"

    outcome = controller.remove_binding(controller.binding_rows[0].binding_ref)
    assert outcome is UiCommandOutcome.MUTATED
    assert [row.kind for row in controller.validation_diagnostics] == ["validation-error"]
    assert controller.validation_diagnostics[0].detail == "New validation"


def test_controller_collapses_diagnostic_rows_by_record_id() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        diagnostics=[
            Diagnostic(
                code="unknown-action",
                level="warning",
                message="Unknown action preserved as passthrough.",
                record_id="record-1",
            )
        ],
        unresolved_bindings=[
            UnresolvedBinding(
                record_id="record-1",
                action_name="seat_exit",
                device_token="js9",
                slot_token="button1",
                reason="unknown-action",
            )
        ],
    )
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"doc": 1})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    assert len(controller.diagnostics) == 1
    assert controller.diagnostics[0].action == "seat_exit"


def test_controller_infers_side_for_load_diagnostics_when_device_token_maps_to_role() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        role_device_tokens={"left_stick": "js1"},
        diagnostics=[
            Diagnostic(
                code="unknown-slot",
                level="warning",
                message="Unknown slot 'unknown_button' preserved as passthrough.",
                record_id="record-1",
            )
        ],
        unresolved_bindings=[
            UnresolvedBinding(
                record_id="record-1",
                action_name="seat_exit",
                device_token="js1",
                slot_token="unknown_button",
                reason="unknown-slot",
            )
        ],
    )
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"doc": 1})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    assert controller.load_diagnostics[0].side == "left"


def test_controller_dedupes_diagnostics_without_record_id_by_tuple() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(catalog=catalog)

    def export_with_duplicate_validation(current: BindingSession) -> ExportResult:
        current.diagnostics.extend(
            [
                Diagnostic(code="validation-error", level="error", message="Duplicate issue"),
                Diagnostic(code="validation-error", level="error", message="Duplicate issue"),
            ]
        )
        return ExportResult(document=None)

    service = FakeSessionService(session=session, export_steps=[export_with_duplicate_validation])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    assert len(controller.validation_diagnostics) == 1


def test_controller_uses_replacement_session_returned_by_command_operations() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    original_binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(catalog=catalog, bindings=[original_binding])
    service = FakeSessionService(
        session=session,
        export_steps=[ExportResult(document={"doc": 1}), ExportResult(document={"doc": 2})],
    )

    def replace_session(_: BindingSession, __: BindingReference, target_slot: str) -> BindingSession:
        return make_session(
            catalog=catalog,
            bindings=[make_binding("seat_exit", slot_id=target_slot, source_actionmap_name="seat_general")],
        )

    service.move_hook = replace_session
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    assert controller.move_binding(controller.binding_rows[0].binding_ref, "button4") is UiCommandOutcome.MUTATED
    assert controller.binding_rows[0].slot_id == "button4"


def test_controller_captures_command_diagnostics_from_replacement_session() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        bindings=[make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")],
        diagnostics=[Diagnostic(code="load-warning", level="warning", message="Initial load diagnostic")],
    )
    service = FakeSessionService(
        session=session,
        export_steps=[ExportResult(document={"doc": 1}), ExportResult(document={"doc": 2})],
    )

    def replace_with_warning(_: BindingSession, __: BindingReference, target_slot: str) -> BindingSession:
        return make_session(
            catalog=catalog,
            bindings=[make_binding("seat_exit", slot_id=target_slot, source_actionmap_name="seat_general")],
            diagnostics=[Diagnostic(code="move-warning", level="warning", message="Replacement session warning")],
        )

    service.move_hook = replace_with_warning
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True
    assert controller.move_binding(controller.binding_rows[0].binding_ref, "button4") is UiCommandOutcome.MUTATED
    assert any(row.kind == "move-warning" for row in controller.command_diagnostics)


def test_controller_accessors_return_snapshot_copies() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(catalog=catalog, bindings=[binding])
    service = FakeSessionService(
        session=session,
        export_steps=[
            ExportResult(
                document={"doc": 1},
                blocked_conflicts=[
                    PassthroughConflict(
                        conflict_id="conflict:1",
                        record_id="1",
                        device_token="js1",
                        slot_token="button2",
                        trigger_token="plain",
                        action_name="seat_exit",
                    )
                ],
            )
        ],
    )
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True

    left_config = controller.left_config
    left_config.clear_mappings()
    export_state = controller.export_state
    export_state.blocked_conflicts[0].slot_token = "button99"
    export_state.blocked_conflicts.append(
        PassthroughConflict(
            conflict_id="conflict:2",
            record_id="2",
            device_token="js1",
            slot_token="button3",
            trigger_token="plain",
            action_name="seat_exit",
        )
    )

    assert controller.left_config.configured_actions
    assert len(controller.export_state.blocked_conflicts) == 1
    assert controller.export_state.blocked_conflicts[0].slot_token == "button2"


def test_controller_session_accessor_returns_snapshot_copy() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(catalog=catalog, bindings=[binding])
    service = FakeSessionService(session=session, export_steps=[ExportResult(document={"doc": 1})])
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})

    assert controller.open_profile(Path("profile.xml")) is True

    session_copy = controller.session
    assert session_copy is not None
    session_copy.profile.bindings.clear()

    assert controller.session is not None
    assert controller.session.profile.bindings
    assert controller.binding_rows


def test_blocked_conflicts_clear_export_bundle_until_next_success() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(catalog=catalog, bindings=[binding])
    service = FakeSessionService(
        session=session,
        export_steps=[
            ExportResult(document={"doc": 1}),
            ExportResult(
                blocked_conflicts=[
                    PassthroughConflict(
                        conflict_id="conflict:1",
                        record_id="1",
                        device_token="js1",
                        slot_token="button2",
                        trigger_token="plain",
                        action_name="seat_exit",
                    )
                ]
            ),
            ExportResult(document={"doc": 2}),
        ],
    )
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})
    assert controller.open_profile(Path("profile.xml")) is True
    assert controller.export_state.document == {"doc": 1}

    assert controller.remove_binding(controller.binding_rows[0].binding_ref) is UiCommandOutcome.MUTATED
    assert controller.export_state.document is None
    assert len(controller.export_state.blocked_conflicts) == 1

    assert controller.select_action("left", "button2", "seat_exit", TriggerMode.PLAIN) is UiCommandOutcome.MUTATED
    assert controller.export_state.document == {"doc": 2}


def test_unexpected_export_failure_clears_cached_export_state() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(catalog=catalog, bindings=[binding])
    service = FakeSessionService(
        session=session,
        export_steps=[ExportResult(document={"doc": 1})],
    )
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})
    assert controller.open_profile(Path("profile.xml")) is True

    service.export_exception = RuntimeError("export failed")
    assert controller.remove_binding(controller.binding_rows[0].binding_ref) is UiCommandOutcome.MUTATED
    assert controller.export_state.document is None
    assert controller.export_state.export_enabled is False


def test_export_without_document_clears_stale_cache_and_surfaces_diagnostics() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    binding = make_binding("seat_exit", slot_id="button1", source_actionmap_name="seat_general")
    session = make_session(catalog=catalog, bindings=[binding])

    def export_without_document(current: BindingSession) -> ExportResult:
        current.diagnostics.append(
            Diagnostic(code="validation-error", level="error", message="Export blocked without document")
        )
        return ExportResult(document=None)

    service = FakeSessionService(
        session=session,
        export_steps=[ExportResult(document={"doc": 1}), export_without_document],
    )
    controller = make_controller(service, resolver=lambda _: {"js1": "left_stick"})
    assert controller.open_profile(Path("profile.xml")) is True

    assert controller.remove_binding(controller.binding_rows[0].binding_ref) is UiCommandOutcome.MUTATED
    assert controller.export_state.document is None
    assert any(row.kind == "validation-error" for row in controller.validation_diagnostics)