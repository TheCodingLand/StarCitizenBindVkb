from app.domain import (
    ActionDefinition,
    ActionIdentifier,
    BindingEdit,
    BindingSession,
    GameCatalog,
    GameCatalogVersion,
    SessionCatalogSnapshot,
    TriggerMode,
    WorkingProfile,
)
from app.models.joystick import get_joystick_buttons
from app.services.ui_projection import build_session_catalog_entries, project_session_view


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
        actionmaps = catalog.actionmaps_by_name.get(entry.action_name, ())
        if entry.actionmap_name and entry.actionmap_name not in actionmaps:
            catalog.actionmaps_by_name[entry.action_name] = (*actionmaps, entry.actionmap_name)
        if entry.actionmap_name:
            catalog.actionmap_by_name.setdefault(entry.action_name, entry.actionmap_name)
    return catalog


def make_session(
    *,
    bindings: list[BindingEdit],
    catalog: GameCatalog,
    role_device_tokens: dict[str, str] | None = None,
) -> BindingSession:
    return BindingSession(
        profile=WorkingProfile(
            profile_name="ProjectionTest",
            bindings=bindings,
            role_device_tokens=role_device_tokens or {"left_stick": "js1", "right_stick": "js2"},
        ),
        catalog_snapshot=SessionCatalogSnapshot(version=catalog.version, catalog=catalog),
    )


def joystick_buttons_by_slot() -> dict[str, object]:
    return {
        button.sc_config_name: button
        for button in get_joystick_buttons("VKB Default").values()
    }


def test_project_binding_maps_trigger_mode_to_joy_action_flags() -> None:
    catalog = make_catalog(
        make_action_definition("plain_action", actionmap_name="map_plain"),
        make_action_definition("modifier_action", actionmap_name="map_modifier"),
        make_action_definition("hold_action", actionmap_name="map_hold"),
        make_action_definition("multitap_action", actionmap_name="map_multitap"),
    )
    session = make_session(
        catalog=catalog,
        bindings=[
            BindingEdit(role="left_stick", slot_id="button1", action_name="plain_action", trigger_mode=TriggerMode.PLAIN),
            BindingEdit(
                role="left_stick",
                slot_id="button2",
                action_name="modifier_action",
                trigger_mode=TriggerMode.MODIFIER,
                modifier_token="rctrl",
                source_actionmap_name="map_modifier",
            ),
            BindingEdit(role="left_stick", slot_id="button3", action_name="hold_action", trigger_mode=TriggerMode.HOLD),
            BindingEdit(
                role="right_stick",
                slot_id="button4",
                action_name="multitap_action",
                trigger_mode=TriggerMode.MULTITAP,
            ),
        ],
    )

    projection = project_session_view(session, joystick_buttons_by_slot=joystick_buttons_by_slot())

    projected_actions = {action.name: action for action in projection.left_config.configured_actions.values()}
    projected_actions.update({action.name: action for action in projection.right_config.configured_actions.values()})

    assert projected_actions["plain_action"].modifier is False
    assert projected_actions["plain_action"].hold is False
    assert projected_actions["plain_action"].multitap is False
    assert projected_actions["modifier_action"].modifier is True
    assert projected_actions["modifier_action"].hold is False
    assert projected_actions["modifier_action"].multitap is False
    assert projected_actions["hold_action"].modifier is False
    assert projected_actions["hold_action"].hold is True
    assert projected_actions["hold_action"].multitap is False
    assert projected_actions["multitap_action"].modifier is False
    assert projected_actions["multitap_action"].hold is False
    assert projected_actions["multitap_action"].multitap is True


def test_projection_reports_overflowed_duplicate_binding_as_projection_diagnostic() -> None:
    catalog = make_catalog(make_action_definition("overflow_action", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        bindings=[
            BindingEdit(role="left_stick", slot_id="button3", action_name="overflow_action", trigger_mode=TriggerMode.PLAIN),
            BindingEdit(role="left_stick", slot_id="button2", action_name="overflow_action", trigger_mode=TriggerMode.PLAIN),
        ],
    )

    projection = project_session_view(session, joystick_buttons_by_slot=joystick_buttons_by_slot())

    assert any(action.button.sc_config_name == "button2" for action in projection.left_config.configured_actions.values())
    assert not any(action.button.sc_config_name == "button3" for action in projection.left_config.configured_actions.values())
    assert any(
        diagnostic.kind == "projection-overflow"
        and diagnostic.action == "overflow_action"
        and diagnostic.side == "left"
        for diagnostic in projection.diagnostics
    )


def test_projection_uses_spec_snapshot_order_for_collision_winner() -> None:
    catalog = make_catalog(make_action_definition("ordered_action", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        bindings=[
            BindingEdit(role="left_stick", slot_id="button9", action_name="ordered_action", trigger_mode=TriggerMode.PLAIN),
            BindingEdit(role="left_stick", slot_id="button4", action_name="ordered_action", trigger_mode=TriggerMode.PLAIN),
        ],
    )

    projection = project_session_view(session, joystick_buttons_by_slot=joystick_buttons_by_slot())

    rendered = next(action for action in projection.left_config.configured_actions.values() if action.name == "ordered_action")
    assert rendered.button.sc_config_name == "button4"


def test_projection_reports_unrenderable_slot_as_projection_diagnostic() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        bindings=[
            BindingEdit(role="right_stick", slot_id="unknown_button", action_name="seat_exit", trigger_mode=TriggerMode.PLAIN),
        ],
    )

    projection = project_session_view(session, joystick_buttons_by_slot=joystick_buttons_by_slot())

    assert not projection.right_config.configured_actions
    assert any(
        diagnostic.kind == "unrenderable-slot"
        and diagnostic.action == "seat_exit"
        and diagnostic.side == "right"
        for diagnostic in projection.diagnostics
    )


def test_projection_reports_missing_or_ambiguous_action_metadata() -> None:
    catalog = make_catalog(
        make_action_definition("ambiguous_action", actionmap_name="seat_general"),
        make_action_definition("ambiguous_action", actionmap_name="vehicle_general"),
    )
    session = make_session(
        catalog=catalog,
        bindings=[
            BindingEdit(role="left_stick", slot_id="button1", action_name="missing_action", trigger_mode=TriggerMode.PLAIN),
            BindingEdit(role="left_stick", slot_id="button2", action_name="ambiguous_action", trigger_mode=TriggerMode.PLAIN),
        ],
    )

    projection = project_session_view(session, joystick_buttons_by_slot=joystick_buttons_by_slot())

    assert not projection.left_config.configured_actions
    assert any(
        diagnostic.kind == "unknown-action"
        and diagnostic.action == "missing_action"
        for diagnostic in projection.diagnostics
    )
    assert any(
        diagnostic.kind == "ambiguous-actionmap"
        and diagnostic.action == "ambiguous_action"
        for diagnostic in projection.diagnostics
    )


def test_projection_reports_stale_actionmap_provenance_separately_from_ambiguity() -> None:
    catalog = make_catalog(
        make_action_definition("seat_exit", actionmap_name="seat_general"),
    )
    session = make_session(
        catalog=catalog,
        bindings=[
            BindingEdit(
                role="left_stick",
                slot_id="button1",
                action_name="seat_exit",
                trigger_mode=TriggerMode.PLAIN,
                source_actionmap_name="bogus_map",
            ),
        ],
    )

    projection = project_session_view(session, joystick_buttons_by_slot=joystick_buttons_by_slot())

    assert not projection.left_config.configured_actions
    assert any(
        diagnostic.kind == "unknown-actionmap"
        and diagnostic.action == "seat_exit"
        for diagnostic in projection.diagnostics
    )


def test_projection_reports_missing_role_device_token_instead_of_rendering_invalid_input() -> None:
    catalog = make_catalog(make_action_definition("seat_exit", actionmap_name="seat_general"))
    session = make_session(
        catalog=catalog,
        bindings=[
            BindingEdit(role="left_stick", slot_id="button1", action_name="seat_exit", trigger_mode=TriggerMode.PLAIN),
        ],
        role_device_tokens={"right_stick": "js2"},
    )

    projection = project_session_view(session, joystick_buttons_by_slot=joystick_buttons_by_slot())

    assert not projection.left_config.configured_actions
    assert any(
        diagnostic.kind == "unresolved-device"
        and diagnostic.action == "seat_exit"
        and diagnostic.side == "left"
        for diagnostic in projection.diagnostics
    )


def test_catalog_view_filters_non_joystick_and_ambiguous_actions() -> None:
    catalog = make_catalog(
        make_action_definition("valid_action", actionmap_name="seat_general"),
        make_action_definition("keyboard_only", actionmap_name="seat_general", supports_joystick=False, supported_trigger_modes=()),
        make_action_definition("ambiguous_action", actionmap_name="seat_general"),
        make_action_definition("ambiguous_action", actionmap_name="vehicle_general"),
    )

    entries = build_session_catalog_entries(catalog)

    assert [entry.action_name for entry in entries] == ["valid_action"]


def test_catalog_view_preserves_blank_actionmap_name() -> None:
    catalog = make_catalog(
        make_action_definition("no_map_action", actionmap_name=""),
    )

    entries = build_session_catalog_entries(catalog)

    assert len(entries) == 1
    assert entries[0].actionmap_name == ""


def test_projection_reports_stale_provenance_for_blank_actionmap_entry() -> None:
    catalog = make_catalog(
        make_action_definition("no_map_action", actionmap_name=""),
    )
    session = make_session(
        catalog=catalog,
        bindings=[
            BindingEdit(
                role="left_stick",
                slot_id="button1",
                action_name="no_map_action",
                trigger_mode=TriggerMode.PLAIN,
                source_actionmap_name="bogus_map",
            ),
        ],
    )

    projection = project_session_view(session, joystick_buttons_by_slot=joystick_buttons_by_slot())

    assert not projection.left_config.configured_actions
    assert any(
        diagnostic.kind == "unknown-actionmap"
        and diagnostic.action == "no_map_action"
        for diagnostic in projection.diagnostics
    )


def test_catalog_view_filters_entries_for_selected_trigger_mode() -> None:
    catalog = make_catalog(
        make_action_definition(
            "plain_only",
            actionmap_name="seat_general",
            supported_trigger_modes=(TriggerMode.PLAIN,),
        ),
        make_action_definition(
            "hold_ready",
            actionmap_name="vehicle_general",
            supported_trigger_modes=(TriggerMode.PLAIN, TriggerMode.HOLD),
        ),
    )

    entries = build_session_catalog_entries(catalog, selected_trigger_mode=TriggerMode.HOLD)

    assert [entry.action_name for entry in entries] == ["hold_ready"]