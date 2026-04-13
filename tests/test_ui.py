# test_main.py
import platform
from pathlib import Path
from typing import Any, Dict, Iterator

import pytest
import app.config as app_config
from app.models import exported_configmap_xml as configmap
from app.models.joystick import JoyAction, JoystickConfig
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtCore import Qt
from app.domain import (
    BindingReference,
    PassthroughConflict,
    TriggerMode,
    ValidationIssue,
    ValidationReport,
)
from app.services import (
    JoystickActivityEvent,
    ProjectedBindingRow,
    SessionCatalogEntry,
    UiCommandOutcome,
    UiDiagnosticRow,
    UiExportState,
)
from app.ui import ControlMapperApp, joystick_buttons
from app.components.settings_dialog import SettingsDialog


WINDOWS = platform.system() == "Windows"

MINIMAL_EMPTY_EXPORT = """<ActionMaps version="1" optionsVersion="2" rebindVersion="2" profileName="4_71">
 <CustomisationUIHeader label="4_71" description="" image="">
  <devices>
   <keyboard instance="1"/>
   <mouse instance="1"/>
   <joystick instance="1"/>
   <joystick instance="2"/>
  </devices>
  <categories />
 </CustomisationUIHeader>
 <options type="keyboard" instance="1" Product="Keyboard"/>
 <options type="joystick" instance="1" Product="Left Stick"/>
 <options type="joystick" instance="2" Product="Right Stick"/>
 <modifiers />
</ActionMaps>
"""


@pytest.fixture(autouse=True)
def override_config_path(tmp_path: Path):
    original_path = app_config.get_config_path()
    app_config.set_config_path(tmp_path / "config.json")
    yield
    app_config.set_config_path(original_path)


# pytestmark = pytest.mark.skipif(
#     WINDOWS,
#     reason="PyQt UI tests crash under Windows COM apartment (fatal exception 0x8001010d)",
# )


@pytest.fixture
def main_window(qapp: Any, qtbot: Any) -> Iterator[ControlMapperApp]:
    """Fixture for the main window."""
    del qapp
    window = ControlMapperApp()
    qtbot.addWidget(window)
    window.show()
    yield window
    window.close()


def require_attr(instance: object, name: str) -> Any:
    value = getattr(instance, name, None)
    assert value is not None, f"{type(instance).__name__} missing attribute {name}"
    return value


def activity_event(
    product_guid: str = "guid-left",
    pygame_index: int = 0,
    slot_name: str = "button3",
    input_kind: str = "button",
    active: bool = True,
    value: float | None = None,
    timestamp: float = 1000.0,
) -> JoystickActivityEvent:
    return JoystickActivityEvent(
        product_guid=product_guid,
        pygame_index=pygame_index,
        saved_instance=1,
        slot_name=slot_name,
        input_kind=input_kind,
        active=active,
        value=(1.0 if active else 0.0) if value is None else value,
        timestamp=timestamp,
    )


def test_main_window_initialization(main_window: ControlMapperApp):
    """Test the main window initialization."""
    assert main_window.windowTitle() == "VKB Joystick Mapper"
    assert main_window.current_joystick == "left"
    assert not main_window.modifier_enabled
    assert not main_window.multitap_enabled
    assert not main_window.hold_enabled
    assert main_window.config is not None


def test_toggle_modifier(main_window: ControlMapperApp, qtbot: Any) -> None:
    """Test toggling the modifier button."""
    initial_state = main_window.modifier_enabled
    qtbot.mouseClick(main_window.modifier_button, Qt.MouseButton.LeftButton)
    assert main_window.modifier_enabled != initial_state
    expected_text = "Disable Modifier" if main_window.modifier_enabled else "Enable Modifier"
    assert main_window.modifier_button.text() == expected_text


def test_toggle_multitap(main_window: ControlMapperApp, qtbot: Any) -> None:
    """Test toggling the multitap button."""
    initial_state = main_window.multitap_enabled
    qtbot.mouseClick(main_window.multitap_button, Qt.MouseButton.LeftButton)
    assert main_window.multitap_enabled != initial_state
    expected_text = "Disable Multitap" if main_window.multitap_enabled else "Enable Multitap"
    assert main_window.multitap_button.text() == expected_text


def test_toggle_hold(main_window: ControlMapperApp, qtbot: Any) -> None:
    """Test toggling the hold button."""
    initial_state = main_window.hold_enabled
    qtbot.mouseClick(main_window.hold_button, Qt.MouseButton.LeftButton)
    assert main_window.hold_enabled != initial_state
    expected_text = "Disable Hold" if main_window.hold_enabled else "Enable Hold"
    assert main_window.hold_button.text() == expected_text


def test_trigger_mode_selector_keeps_single_active_mode(main_window: ControlMapperApp, qtbot: Any) -> None:
    qtbot.mouseClick(main_window.modifier_button, Qt.MouseButton.LeftButton)
    assert main_window.modifier_enabled is True
    assert main_window.hold_enabled is False
    assert main_window.multitap_enabled is False

    qtbot.mouseClick(main_window.hold_button, Qt.MouseButton.LeftButton)
    assert main_window.modifier_enabled is False
    assert main_window.hold_enabled is True
    assert main_window.multitap_enabled is False

    qtbot.mouseClick(main_window.multitap_button, Qt.MouseButton.LeftButton)
    assert main_window.modifier_enabled is False
    assert main_window.hold_enabled is False
    assert main_window.multitap_enabled is True


def test_no_trigger_toggle_maps_to_plain_mode(main_window: ControlMapperApp) -> None:
    main_window.modifier_enabled = False
    main_window.hold_enabled = False
    main_window.multitap_enabled = False

    assert main_window.current_trigger_mode() is TriggerMode.PLAIN


def test_switch_joystick(main_window: ControlMapperApp, qtbot: Any) -> None:
    """Test switching between joysticks."""
    initial_joystick = main_window.current_joystick
    qtbot.mouseClick(main_window.switch_button, Qt.MouseButton.LeftButton)
    assert main_window.current_joystick != initial_joystick
    expected_text = (
        "Switch to Left Joystick"
        if main_window.current_joystick == "right"
        else "Switch to Right Joystick"
    )
    assert main_window.switch_button.text() == expected_text


def test_main_window_highlights_matching_slot_for_assigned_device(
    main_window: ControlMapperApp,
) -> None:
    main_window.config.joystick_instance_left = 1
    main_window.current_joystick = "left"
    require_attr(main_window, "_refresh_live_activity_assignments")()

    require_attr(main_window, "_handle_joystick_activity")(
        activity_event(
            product_guid="guid-left",
            pygame_index=0,
            slot_name="button3",
            active=True,
        )
    )

    overlay = require_attr(main_window, "joystick_activity_overlay")
    assert "button3" in overlay.active_pulses


def test_main_window_keeps_axis_highlight_active_while_displaced(
    main_window: ControlMapperApp,
) -> None:
    main_window.config.joystick_instance_left = 1
    main_window.current_joystick = "left"
    require_attr(main_window, "_refresh_live_activity_assignments")()

    require_attr(main_window, "_handle_joystick_activity")(
        activity_event(
            product_guid="guid-left",
            pygame_index=0,
            slot_name="x",
            input_kind="axis",
            active=True,
            value=0.82,
        )
    )

    overlay = require_attr(main_window, "joystick_activity_overlay")
    overlay._expire_stale_pulses(now_ms=5000.0)
    assert "x" in overlay.active_pulses

    require_attr(main_window, "_handle_joystick_activity")(
        activity_event(
            product_guid="guid-left",
            pygame_index=0,
            slot_name="x",
            input_kind="axis",
            active=False,
            value=0.0,
            timestamp=5001.0,
        )
    )

    assert "x" not in overlay.active_pulses


def test_settings_dialog_accept(qtbot: Any) -> None:
    """Test accepting the settings dialog."""
    # Use a temporary config file to avoid changing the actual config
    config = app_config.Config(installation_path="/original/path")
    config.save()
    dialog = SettingsDialog(config)
    dialog.installation_path_line_edit.setText("/new/path")
    dialog.install_type_combo_box.setCurrentText("PTU")
    dialog.joystick_left_name_filter_line_edit.setText("New Left Joystick")
    dialog.joystick_right_name_filter_line_edit.setText("New Right Joystick")
    dialog.joystick_type_left_line_edit.setText("New Type Left")
    dialog.joystick_type_right_line_edit.setText("New Type Right")
    dialog.joystick_instance_left_spin_box.setValue(3)
    dialog.joystick_instance_right_spin_box.setValue(4)

    # Simulate clicking the OK button
    ok_button = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
    qtbot.mouseClick(ok_button, Qt.MouseButton.LeftButton)

    # Verify that the config has been updated
    assert config.installation_path == "/new/path"
    assert config.install_type == "PTU"
    assert config.joystick_left_name_filter == "New Left Joystick"
    assert config.joystick_right_name_filter == "New Right Joystick"
    assert config.joystick_type_left == "New Type Left"
    assert config.joystick_type_right == "New Type Right"
    assert config.joystick_instance_left == 3
    assert config.joystick_instance_right == 4


def test_settings_dialog_cancel(qtbot: Any) -> None:
    """Test canceling the settings dialog."""
    config = app_config.Config(installation_path="/original/path")
    dialog = SettingsDialog(config)
    dialog.installation_path_line_edit.setText("/should/not/save")

    # Simulate clicking the Cancel button
    cancel_button = dialog.findChild(QDialogButtonBox).button(
        QDialogButtonBox.StandardButton.Cancel
    )
    qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)

    # Config should remain unchanged
    assert config.installation_path == "/original/path"


def test_add_action_to_button(main_window: ControlMapperApp, qtbot: Any) -> None:
    """Test adding an action to a button."""

    # Simulate selecting a button
    button_label = "button1"  # Select the first button
    button = main_window.button_refs[button_label]
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    # Mock the action selection dialog
    selected_action_name = "v_toggle_power"

    # Add the action to the default actions

    main_window.selected_button_label = button_label
    main_window.modifier_enabled = True
    main_window.multitap_enabled = False
    main_window.hold_enabled = False

    # Since the ActionSelectionDialog is interactive, we mock the selected action
    main_window.add_action_to_button = lambda: main_window.current_config.set_mapping(
        JoyAction(
            name=selected_action_name,
            input=button_label,
            multitap=False,
            hold=False,
            category="Test",
            sub_category="SubTest",
            modifier=True,
            button=joystick_buttons["button1"],
        )
    )
    main_window.add_action_to_button()

    # Verify that the action has been added
    actions = main_window.current_config.get_all_actions_for_button_no_filter(button_label)
    assert len(actions) > 0
    assert any(action.name == selected_action_name for action in actions.values())


class FakeUiController:
    def __init__(self) -> None:
        self.session = object()
        self.catalog_entries: list[SessionCatalogEntry] = []
        self.left_config = JoystickConfig(side="left", configured_actions={})
        self.right_config = JoystickConfig(side="right", configured_actions={})
        self.binding_rows: list[ProjectedBindingRow] = []
        self.diagnostics: list[UiDiagnosticRow] = []
        self.export_state = UiExportState()
        self.open_calls: list[Path] = []
        self.open_result = True
        self.select_calls: list[tuple[str, str, str, TriggerMode]] = []
        self.remove_calls: list[BindingReference] = []

    def open_profile(self, path: Path) -> bool:
        self.open_calls.append(path)
        if not self.open_result:
            self.session = None
            self.left_config = JoystickConfig(side="left", configured_actions={})
            self.right_config = JoystickConfig(side="right", configured_actions={})
            self.binding_rows = []
            self.diagnostics = []
            self.export_state = UiExportState()
            return False
        self.session = object()
        return True

    def select_action(
        self,
        side: str,
        target_slot: str,
        action_name: str,
        trigger_mode: TriggerMode,
    ) -> UiCommandOutcome:
        self.select_calls.append((side, target_slot, action_name, trigger_mode))
        action = JoyAction(
            name=action_name,
            input=f"js1_{target_slot}",
            multitap=trigger_mode is TriggerMode.MULTITAP,
            hold=trigger_mode is TriggerMode.HOLD,
            category="Vehicles",
            sub_category="Flight",
            modifier=trigger_mode is TriggerMode.MODIFIER,
            button=joystick_buttons[target_slot],
        )
        self.left_config = JoystickConfig(side="left", configured_actions={action.key: action})
        self.binding_rows = [
            ProjectedBindingRow(
                binding_ref=BindingReference(
                    role="left_stick",
                    slot_id=target_slot,
                    action_name=action_name,
                    trigger_mode=trigger_mode,
                ),
                side="left",
                button_name=target_slot,
                slot_id=target_slot,
                action_name=action_name,
                display_label=action_name,
                modifier=trigger_mode is TriggerMode.MODIFIER,
                hold=trigger_mode is TriggerMode.HOLD,
                multitap=trigger_mode is TriggerMode.MULTITAP,
            )
        ]
        return UiCommandOutcome.MUTATED

    def remove_binding(self, binding_ref: BindingReference) -> UiCommandOutcome:
        self.remove_calls.append(binding_ref)
        self.left_config = JoystickConfig(side="left", configured_actions={})
        self.binding_rows = []
        return UiCommandOutcome.MUTATED


def test_add_action_refreshes_button_grid_from_projection(main_window: ControlMapperApp, monkeypatch) -> None:
    controller = FakeUiController()
    controller.catalog_entries = [
        SessionCatalogEntry(
            action_name="v_toggle_power",
            actionmap_name="seat_general",
            category="Vehicles",
            subcategory="Flight",
            display_label="Toggle Power",
            supports_joystick=True,
            supported_trigger_modes=(TriggerMode.MODIFIER,),
        )
    ]
    main_window.session_controller = controller
    main_window.left_joystick_config = JoystickConfig(side="left", configured_actions={})
    main_window.right_joystick_config = JoystickConfig(side="right", configured_actions={})
    main_window.current_config = main_window.left_joystick_config
    main_window.selected_button_label = "button1"
    main_window.modifier_enabled = True
    main_window.hold_enabled = False
    main_window.multitap_enabled = False

    class FakeDialog:
        def __init__(self, entries, parent=None):
            self.selected_action = entries[0]

        def exec(self):
            return True

    monkeypatch.setattr("app.ui.ActionSelectionDialog", FakeDialog)

    main_window.add_action_to_button()

    actions = main_window.current_config.get_all_actions_for_button_no_filter("button1")
    assert any(action.name == "v_toggle_power" for action in actions.values())
    assert controller.select_calls == [("left", "button1", "v_toggle_power", TriggerMode.MODIFIER)]


def test_remove_action_refreshes_button_grid_from_projection(main_window: ControlMapperApp, monkeypatch) -> None:
    controller = FakeUiController()
    action = JoyAction(
        name="v_toggle_power",
        input="js1_button1",
        multitap=False,
        hold=False,
        category="Vehicles",
        sub_category="Flight",
        modifier=False,
        button=joystick_buttons["button1"],
    )
    controller.left_config = JoystickConfig(side="left", configured_actions={action.key: action})
    binding_ref = BindingReference(
        role="left_stick",
        slot_id="button1",
        action_name="v_toggle_power",
        trigger_mode=TriggerMode.PLAIN,
    )
    controller.binding_rows = [
        ProjectedBindingRow(
            binding_ref=binding_ref,
            side="left",
            button_name="button1",
            slot_id="button1",
            action_name="v_toggle_power",
            display_label="Toggle Power",
            modifier=False,
            hold=False,
            multitap=False,
        )
    ]
    main_window.session_controller = controller
    main_window.left_joystick_config = controller.left_config
    main_window.right_joystick_config = controller.right_config
    main_window.current_config = main_window.left_joystick_config
    main_window.show_action_panel(main_window.button_refs["button1"], "button1")
    main_window.actions_table_widget.selectRow(0)

    main_window.remove_selected_action()

    assert controller.remove_calls == [binding_ref]
    assert not main_window.current_config.get_all_actions_for_button_no_filter("button1")


def test_main_window_starts_without_active_session(main_window: ControlMapperApp) -> None:
    assert not main_window.left_joystick_config.configured_actions
    assert not main_window.right_joystick_config.configured_actions
    assert main_window.control_map is None
    assert main_window.control_map_template is None
    assert main_window.add_action_button.isEnabled() is False
    assert main_window.remove_action_button.isEnabled() is False


def test_select_control_map_renders_projected_left_and_right_state(main_window: ControlMapperApp) -> None:
    controller = FakeUiController()
    left_action = JoyAction(
        name="left_action",
        input="js1_button1",
        multitap=False,
        hold=False,
        category="Vehicles",
        sub_category="Flight",
        modifier=False,
        button=joystick_buttons["button1"],
    )
    right_action = JoyAction(
        name="right_action",
        input="js2_button1",
        multitap=False,
        hold=False,
        category="Vehicles",
        sub_category="Flight",
        modifier=False,
        button=joystick_buttons["button1"],
    )
    controller.left_config = JoystickConfig(side="left", configured_actions={left_action.key: left_action})
    controller.right_config = JoystickConfig(side="right", configured_actions={right_action.key: right_action})
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    profile_path = Path("tests/fixtures/profiles/profile_with_unknowns.xml")
    main_window.exported_control_maps = [str(profile_path)]

    main_window.select_control_map(0)

    assert controller.open_calls == [profile_path]
    assert "left_action" in main_window.button_refs["button1"].text()
    main_window.toggle_joystick()
    assert "right_action" in main_window.button_refs["button1"].text()
    assert main_window.add_action_button.isEnabled() is True
    assert main_window.remove_action_button.isEnabled() is True


def test_select_control_map_can_render_inherited_default_rows_when_enabled(main_window: ControlMapperApp) -> None:
    controller = FakeUiController()
    default_action = JoyAction(
        name="default_pitch",
        input="js1_button1",
        multitap=False,
        hold=False,
        category="Vehicles",
        sub_category="Flight",
        modifier=False,
        button=joystick_buttons["button1"],
    )
    controller.effective_left_config = JoystickConfig(
        side="left",
        configured_actions={default_action.key: default_action},
    )
    controller.effective_right_config = JoystickConfig(side="right", configured_actions={})
    controller.effective_binding_rows = [
        ProjectedBindingRow(
            binding_ref=BindingReference(
                role="left_stick",
                slot_id="button1",
                action_name="default_pitch",
                trigger_mode=TriggerMode.PLAIN,
                source_record_id="default:1",
                source_actionmap_name="spaceship_movement",
            ),
            side="left",
            button_name="button1",
            slot_id="button1",
            action_name="default_pitch",
            display_label="Default Pitch",
            modifier=False,
            hold=False,
            multitap=False,
            binding_source="default",
        )
    ]
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]

    main_window.select_control_map(0)
    main_window.show_action_panel(main_window.button_refs["button1"], "button1")

    assert "Default Pitch" in main_window.button_refs["button1"].text()
    assert main_window.actions_table_widget.item(0, 2).text() == "Default"


def test_select_control_map_overlays_defaults_with_inverted_export_instances(
    main_window: ControlMapperApp,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "layout_4_71_empty.xml"
    profile_path.write_text(MINIMAL_EMPTY_EXPORT, encoding="utf-8")

    main_window.session_controller = None
    monkeypatch.setattr(
        main_window,
        "_resolve_imported_role_map",
        lambda _path: {"js1": "left_stick", "js2": "right_stick"},
    )
    monkeypatch.setattr(
        main_window,
        "_resolve_export_role_tokens",
        lambda: {"left_stick": "js2", "right_stick": "js1"},
    )
    main_window.exported_control_maps = [str(profile_path)]

    main_window.select_control_map(0)

    assert main_window.session_controller is not None
    assert any(
        row.side == "left" and row.button_name == "y" and row.binding_source == "default"
        for row in main_window.session_controller.effective_binding_rows
    )
    assert main_window.button_refs["y"].text() != "y"


def test_default_toggle_and_search_filter_effective_rows(main_window: ControlMapperApp, qtbot: Any) -> None:
    controller = FakeUiController()
    default_action = JoyAction(
        name="default_pitch",
        input="js1_button1",
        multitap=False,
        hold=False,
        category="Vehicles",
        sub_category="Flight",
        modifier=False,
        button=joystick_buttons["button1"],
    )
    explicit_action = JoyAction(
        name="v_toggle_power",
        input="js1_button2",
        multitap=False,
        hold=False,
        category="Vehicles",
        sub_category="Flight",
        modifier=False,
        button=joystick_buttons["button2"],
    )
    controller.left_config = JoystickConfig(side="left", configured_actions={explicit_action.key: explicit_action})
    controller.right_config = JoystickConfig(side="right", configured_actions={})
    controller.effective_left_config = JoystickConfig(
        side="left",
        configured_actions={
            default_action.key: default_action,
            explicit_action.key: explicit_action,
        },
    )
    controller.effective_right_config = JoystickConfig(side="right", configured_actions={})
    controller.binding_rows = [
        ProjectedBindingRow(
            binding_ref=BindingReference(
                role="left_stick",
                slot_id="button2",
                action_name="v_toggle_power",
                trigger_mode=TriggerMode.PLAIN,
            ),
            side="left",
            button_name="button2",
            slot_id="button2",
            action_name="v_toggle_power",
            display_label="Toggle Power",
            modifier=False,
            hold=False,
            multitap=False,
        )
    ]
    controller.effective_binding_rows = [
        ProjectedBindingRow(
            binding_ref=BindingReference(
                role="left_stick",
                slot_id="button1",
                action_name="default_pitch",
                trigger_mode=TriggerMode.PLAIN,
                source_record_id="default:1",
            ),
            side="left",
            button_name="button1",
            slot_id="button1",
            action_name="default_pitch",
            display_label="Default Pitch",
            modifier=False,
            hold=False,
            multitap=False,
            binding_source="default",
        ),
        ProjectedBindingRow(
            binding_ref=BindingReference(
                role="left_stick",
                slot_id="button2",
                action_name="v_toggle_power",
                trigger_mode=TriggerMode.PLAIN,
            ),
            side="left",
            button_name="button2",
            slot_id="button2",
            action_name="v_toggle_power",
            display_label="Toggle Power",
            modifier=False,
            hold=False,
            multitap=False,
            binding_source="explicit",
        ),
    ]
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]

    main_window.select_control_map(0)
    main_window.action_search_line_edit.setText("power")

    assert main_window.actions_table_widget.rowCount() == 1
    assert main_window.actions_table_widget.item(0, 0).text() == "button2"
    assert main_window.actions_table_widget.item(0, 1).text() == "Toggle Power"
    assert "Toggle Power" in main_window.button_refs["button2"].text()

    qtbot.mouseClick(main_window.show_default_bindings_checkbox, Qt.MouseButton.LeftButton)

    assert "default_pitch" not in main_window.button_refs["button1"].text()


def test_select_control_map_searches_and_renders_localized_display_labels(
    main_window: ControlMapperApp,
) -> None:
    controller = FakeUiController()
    action = JoyAction(
        name="view_clear_saved_view",
        input="js1_button1",
        multitap=False,
        hold=False,
        category="Camera",
        sub_category="Advanced",
        modifier=False,
        button=joystick_buttons["button1"],
    )
    controller.left_config = JoystickConfig(side="left", configured_actions={action.key: action})
    controller.binding_rows = [
        ProjectedBindingRow(
            binding_ref=BindingReference(
                role="left_stick",
                slot_id="button1",
                action_name="view_clear_saved_view",
                trigger_mode=TriggerMode.PLAIN,
            ),
            side="left",
            button_name="button1",
            slot_id="button1",
            action_name="view_clear_saved_view",
            display_label="@ui_CIAdvanCamClearSave",
            modifier=False,
            hold=False,
            multitap=False,
        )
    ]
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]

    main_window.select_control_map(0)
    main_window.action_search_line_edit.setText("saved view")

    assert main_window.actions_table_widget.rowCount() == 1
    assert main_window.actions_table_widget.item(0, 1).text() == "Clear Saved View"


def test_select_control_map_uses_localized_button_labels(main_window: ControlMapperApp) -> None:
    controller = FakeUiController()
    action = JoyAction(
        name="view_clear_saved_view",
        input="js1_button1",
        multitap=False,
        hold=False,
        category="Camera",
        sub_category="Advanced",
        modifier=False,
        button=joystick_buttons["button1"],
    )
    controller.left_config = JoystickConfig(side="left", configured_actions={action.key: action})
    controller.binding_rows = [
        ProjectedBindingRow(
            binding_ref=BindingReference(
                role="left_stick",
                slot_id="button1",
                action_name="view_clear_saved_view",
                trigger_mode=TriggerMode.PLAIN,
            ),
            side="left",
            button_name="button1",
            slot_id="button1",
            action_name="view_clear_saved_view",
            display_label="@ui_CIAdvanCamClearSave",
            modifier=False,
            hold=False,
            multitap=False,
        )
    ]
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]

    main_window.select_control_map(0)

    assert main_window.button_refs["button1"].text() == "Clear Saved View"


def test_select_control_map_keeps_session_with_partial_role_map_diagnostics(main_window: ControlMapperApp) -> None:
    controller = FakeUiController()
    controller.diagnostics = [
        UiDiagnosticRow(
            kind="unresolved-device",
            action="seat_exit",
            detail="Device token 'js2' could not be matched to a role.",
            side="unknown",
            record_id="record-1",
        )
    ]
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]

    main_window.select_control_map(0)

    assert main_window.session_controller.session is not None
    assert len(main_window.diagnostic_rows) == 1
    assert main_window.diagnostic_rows[0].kind == "unresolved-device"


def test_select_control_map_failure_resets_window_to_safe_empty_state(main_window: ControlMapperApp, monkeypatch) -> None:
    controller = FakeUiController()
    left_action = JoyAction(
        name="left_action",
        input="js1_button1",
        multitap=False,
        hold=False,
        category="Vehicles",
        sub_category="Flight",
        modifier=False,
        button=joystick_buttons["button1"],
    )
    controller.left_config = JoystickConfig(side="left", configured_actions={left_action.key: left_action})
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]
    main_window.select_control_map(0)
    assert main_window.left_joystick_config.configured_actions

    warnings: list[tuple[str, str]] = []

    def fake_warning(parent, title, message):
        warnings.append((title, message))
        return None

    monkeypatch.setattr("app.ui.QMessageBox.warning", fake_warning)
    controller.open_result = False

    main_window.select_control_map(0)

    assert warnings
    assert not main_window.left_joystick_config.configured_actions
    assert not main_window.right_joystick_config.configured_actions
    assert main_window.control_map is None
    assert main_window.diagnostic_rows == []
    assert main_window.add_action_button.isEnabled() is False
    assert main_window.remove_action_button.isEnabled() is False


def test_export_uses_controller_cached_bundle(main_window: ControlMapperApp, monkeypatch) -> None:
    controller = FakeUiController()
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]
    main_window.select_control_map(0)

    captured: list[object] = []

    def fake_unparse(document):
        captured.append(document)
        return "<xml />"

    monkeypatch.setattr("app.ui.unparse", fake_unparse)

    main_window.update_control_map()

    assert captured == [{"doc": 1}]
    assert main_window.control_map == {"doc": 1}


def test_export_failure_shows_message_and_clears_stale_export_state(main_window: ControlMapperApp, monkeypatch) -> None:
    controller = FakeUiController()
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]
    main_window.select_control_map(0)
    assert main_window.control_map == {"doc": 1}

    warnings: list[tuple[str, str]] = []

    def fake_warning(parent, title, message):
        warnings.append((title, message))
        return None

    def fail_unparse(document):
        raise AssertionError("unparse should not be called when export bundle is unavailable")

    monkeypatch.setattr("app.ui.QMessageBox.warning", fake_warning)
    monkeypatch.setattr("app.ui.unparse", fail_unparse)
    controller.export_state = UiExportState(document=None, export_enabled=False)

    main_window.update_control_map()

    assert warnings
    assert main_window.control_map is None


def test_diagnostics_render_in_generalized_table(main_window: ControlMapperApp) -> None:
    controller = FakeUiController()
    controller.catalog_entries = [
        SessionCatalogEntry(
            action_name="v_emergency_exit",
            actionmap_name="seat_general",
            category="@ui_CCSeatGeneral",
            subcategory="@ui_CGSeatGeneral",
            display_label="@ui_CIEmergencyExit",
            supports_joystick=True,
            supported_trigger_modes=(TriggerMode.PLAIN,),
        )
    ]
    controller.diagnostics = [
        UiDiagnosticRow(
            kind="unresolved-device",
            action="v_emergency_exit",
            detail="Device token 'js2' could not be matched to a role.",
            side="unknown",
            record_id="record-1",
        ),
        UiDiagnosticRow(
            kind="unknown-action",
            action="v_unknown_custom_action",
            detail="The action was preserved as passthrough.",
            side="left",
            record_id="record-2",
        ),
    ]
    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]

    main_window.select_control_map(0)

    assert main_window.unsupported_actions_label.text() == "Diagnostics (2)"
    assert main_window.unsupported_actions_table_widget.horizontalHeaderItem(0).text() == "Kind"
    assert main_window.unsupported_actions_table_widget.horizontalHeaderItem(1).text() == "Action"
    assert main_window.unsupported_actions_table_widget.horizontalHeaderItem(2).text() == "Detail"
    assert main_window.unsupported_actions_table_widget.horizontalHeaderItem(3).text() == "Side"
    assert main_window.unsupported_actions_table_widget.item(0, 0).text() == "unresolved-device"
    assert main_window.unsupported_actions_table_widget.item(0, 1).text() == "Emergency Exit Seat"
    assert main_window.unsupported_actions_table_widget.item(1, 0).text() == "unknown-action"
    assert main_window.unsupported_actions_table_widget.item(1, 1).text() == "v_unknown_custom_action"


def test_validation_label_reflects_controller_export_state(main_window: ControlMapperApp) -> None:
    controller = FakeUiController()
    controller.export_state = UiExportState(
        document=None,
        validation_diagnostics=[
            UiDiagnosticRow(
                kind="overflow",
                action="seat_exit",
                detail="The slot has too many bindings.",
                side="left",
            )
        ],
        export_enabled=False,
    )
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]

    main_window.select_control_map(0)

    assert main_window.validation_status_label.text() == "Binding status: 1 error(s)"

    controller.export_state = UiExportState(document={"doc": 1}, export_enabled=True)
    main_window.select_control_map(0)

    assert main_window.validation_status_label.text() == "Binding status: OK"


def test_blocked_conflict_summary_disables_save_and_export(main_window: ControlMapperApp) -> None:
    controller = FakeUiController()
    controller.catalog_entries = [
        SessionCatalogEntry(
            action_name="v_emergency_exit",
            actionmap_name="seat_general",
            category="@ui_CCSeatGeneral",
            subcategory="@ui_CGSeatGeneral",
            display_label="@ui_CIEmergencyExit",
            supports_joystick=True,
            supported_trigger_modes=(TriggerMode.PLAIN,),
        )
    ]
    controller.export_state = UiExportState(
        document=None,
        blocked_conflicts=[
            PassthroughConflict(
                conflict_id="conflict:1",
                record_id="record-1",
                device_token="js2",
                slot_token="button1",
                trigger_token="plain",
                action_name="v_emergency_exit",
            )
        ],
        export_enabled=False,
    )
    main_window.session_controller = controller
    main_window.exported_control_maps = ["tests/fixtures/profiles/profile_with_unknowns.xml"]

    main_window.select_control_map(0)

    assert main_window.blocked_conflicts_label.text() == "Blocked Conflicts (1)"
    assert "Emergency Exit Seat" in main_window.blocked_conflicts_summary.text()
    assert "js2/button1" in main_window.blocked_conflicts_summary.text()
    assert main_window.export_button.isEnabled() is False
    assert main_window.save_export_button.isEnabled() is False


def test_action_panel_refreshes_on_toggle(main_window: ControlMapperApp) -> None:
    """Ensure the action panel re-renders when switching joystick sides."""
    button_label = "button1"
    button = main_window.button_refs[button_label]

    left_input = main_window.build_binding_input(joystick_buttons[button_label], "left", False)
    left_action = JoyAction(
        name="left_action",
        input=left_input,
        multitap=False,
        hold=False,
        category="Test",
        sub_category="Left",
        modifier=False,
        button=joystick_buttons[button_label],
    )
    main_window.left_joystick_config.set_mapping(left_action)

    right_input = main_window.build_binding_input(joystick_buttons[button_label], "right", False)
    right_action = JoyAction(
        name="right_action",
        input=right_input,
        multitap=False,
        hold=False,
        category="Test",
        sub_category="Right",
        modifier=False,
        button=joystick_buttons[button_label],
    )
    main_window.right_joystick_config.set_mapping(right_action)

    main_window.show_action_panel(button, button_label)
    left_names: set[str] = set()
    for row in range(main_window.actions_table_widget.rowCount()):
        item = main_window.actions_table_widget.item(row, 1)
        if item is not None:
            left_names.add(item.text())
    assert "left_action" in left_names

    main_window.toggle_joystick()

    right_names: set[str] = set()
    for row in range(main_window.actions_table_widget.rowCount()):
        item = main_window.actions_table_widget.item(row, 1)
        if item is not None:
            right_names.add(item.text())
    assert "right_action" in right_names
    assert "left_action" not in right_names


def test_load_joystick_mappings(main_window: ControlMapperApp):
    """Test loading joystick mappings."""
    main_window.control_map = None  # Set control_map to None
    main_window.load_joystick_mappings()
    # Since control_map is None, the mappings should remain empty
    assert len(main_window.left_joystick_config.configured_actions) == 0
    assert len(main_window.right_joystick_config.configured_actions) == 0


def test_apply_default_bindings(main_window: ControlMapperApp):
    """Test applying default bindings."""
    main_window.apply_default_bindings()
    # Check that default bindings have been applied
    assert (
        len(main_window.left_joystick_config.configured_actions) > 0
        or len(main_window.right_joystick_config.configured_actions) > 0
    )


def test_populate_control_maps_combo_box(main_window: ControlMapperApp):
    """Test populating the control maps combo box."""
    main_window.exported_control_maps = ["map1.xml", "map2.xml"]
    main_window.populate_control_maps_combo_box()
    assert main_window.control_maps_combo_box.count() == 2


def test_update_joystick_buttons(main_window: ControlMapperApp):
    """Test updating joystick buttons."""
    # Modify some state
    main_window.modifier_enabled = True
    main_window.update_joystick_buttons()
    # Verify that buttons are updated (This would require checking the state of the buttons)


def test_process_rebind_records_unsupported(main_window: ControlMapperApp) -> None:
    """Unknown buttons should be reflected in the unsupported table."""
    main_window.unsupported_actions.clear()
    main_window.joystick_sides = {1: "left"}
    action = configmap.Action.model_validate({"@name": "v_toggle_power", "rebind": []})
    rebind = configmap.Rebind.model_validate({"@input": "js1_unknown_button"})

    main_window.process_rebind(action, rebind)

    expected_entry: Dict[str, Any] = {
        "action_name": "v_toggle_power",
        "button": "unknown_button",
        "modifier": False,
        "side": "left",
    }
    assert expected_entry in main_window.unsupported_actions

    # Running the handler again should not duplicate the entry.
    main_window.process_rebind(action, rebind)
    assert main_window.unsupported_actions.count(expected_entry) == 1


def test_unsupported_actions_label_updates(main_window: ControlMapperApp) -> None:
    """Label should reflect the number of unsupported mappings."""
    main_window.update_unsupported_actions_table()
    initial_count = len(main_window.unsupported_actions)
    expected_initial = (
        "Diagnostics (none)"
        if initial_count == 0
        else f"Diagnostics ({initial_count})"
    )
    assert main_window.unsupported_actions_label.text() == expected_initial

    entry: Dict[str, Any] = {
        "action_name": "test_action",
        "button": "button_unknown",
        "modifier": False,
        "side": "left",
    }
    main_window.unsupported_actions.append(entry)
    main_window.update_unsupported_actions_table()
    assert (
        main_window.unsupported_actions_label.text() == f"Diagnostics ({initial_count + 1})"
    )

    main_window.unsupported_actions.clear()
    main_window.update_unsupported_actions_table()
    assert main_window.unsupported_actions_label.text() == "Diagnostics (none)"


def test_validation_status_label(main_window: ControlMapperApp) -> None:
    """Validation status label reflects report severity."""
    main_window.update_validation_status_indicator(None)
    assert main_window.binding_validation_report is None
    assert main_window.validation_status_label.text() == "Binding status: Not evaluated"

    report = ValidationReport()
    report.add(ValidationIssue(level="warning", message="example warning"))
    main_window.update_validation_status_indicator(report)
    assert main_window.binding_validation_report is report
    assert main_window.validation_status_label.text() == "Binding status: 1 warning(s)"

    report = ValidationReport()
    report.add(ValidationIssue(level="error", message="example error"))
    report.add(ValidationIssue(level="ERROR", message="another"))
    main_window.update_validation_status_indicator(report)
    assert main_window.binding_validation_report is report
    assert main_window.validation_status_label.text() == "Binding status: 2 error(s)"
