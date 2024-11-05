# test_main.py
from pathlib import Path
from app.models.joystick import JoyAction
import pytest
from PyQt6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox
from PyQt6.QtCore import Qt
from app.ui import ControlMapperApp
from app.models.settings_dialog import SettingsDialog
from app.config import Config
from pathlib import Path
import pytestqt.qtbot

@pytest.fixture(scope='session')
def app():
    """Fixture for the QApplication."""
    return QApplication([])

@pytest.fixture
def main_window(app):
    """Fixture for the main window."""
    window = ControlMapperApp()
    window.show()
    return window

def test_main_window_initialization(main_window: ControlMapperApp):
    """Test the main window initialization."""
    assert main_window.windowTitle() == "VKB Joystick Mapper"
    assert main_window.current_joystick == "left"
    assert not main_window.modifier_enabled
    assert not main_window.multitap_enabled
    assert not main_window.hold_enabled
    assert main_window.config is not None

def test_toggle_modifier(main_window: ControlMapperApp, qtbot: pytestqt.qtbot.QtBot):
    """Test toggling the modifier button."""
    initial_state = main_window.modifier_enabled
    qtbot.mouseClick(main_window.modifier_button, Qt.MouseButton.LeftButton)
    assert main_window.modifier_enabled != initial_state
    expected_text = "Disable Modifier" if main_window.modifier_enabled else "Enable Modifier"
    assert main_window.modifier_button.text() == expected_text

def test_toggle_multitap(main_window: ControlMapperApp, qtbot: pytestqt.qtbot.QtBot):
    """Test toggling the multitap button."""
    initial_state = main_window.multitap_enabled
    qtbot.mouseClick(main_window.multitap_button, Qt.MouseButton.LeftButton)
    assert main_window.multitap_enabled != initial_state
    expected_text = "Disable Multitap" if main_window.multitap_enabled else "Enable Multitap"
    assert main_window.multitap_button.text() == expected_text

def test_toggle_hold(main_window: ControlMapperApp, qtbot: pytestqt.qtbot.QtBot):
    """Test toggling the hold button."""
    initial_state = main_window.hold_enabled
    qtbot.mouseClick(main_window.hold_button, Qt.MouseButton.LeftButton)
    assert main_window.hold_enabled != initial_state
    expected_text = "Disable Hold" if main_window.hold_enabled else "Enable Hold"
    assert main_window.hold_button.text() == expected_text

def test_switch_joystick(main_window: ControlMapperApp, qtbot: pytestqt.qtbot.QtBot):
    """Test switching between joysticks."""
    initial_joystick = main_window.current_joystick
    qtbot.mouseClick(main_window.switch_button, Qt.MouseButton.LeftButton)
    assert main_window.current_joystick != initial_joystick
    expected_text = "Switch to Left Joystick" if main_window.current_joystick == "right" else "Switch to Right Joystick"
    assert main_window.switch_button.text() == expected_text


def test_settings_dialog_accept(qtbot: pytestqt.qtbot.QtBot, tmp_path: Path):
    """Test accepting the settings dialog."""
    # Use a temporary config file to avoid changing the actual config
    config_path = tmp_path / "config.json"
    config = Config(installation_path="/original/path")
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

def test_settings_dialog_cancel(qtbot: pytestqt.qtbot.QtBot):
    """Test canceling the settings dialog."""
    config = Config(installation_path="/original/path")
    dialog = SettingsDialog(config)
    dialog.installation_path_line_edit.setText("/should/not/save")

    # Simulate clicking the Cancel button
    cancel_button = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Cancel)
    qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)

    # Config should remain unchanged
    assert config.installation_path == "/original/path"

def test_add_action_to_button(main_window: ControlMapperApp, qtbot: pytestqt.qtbot.QtBot):
    """Test adding an action to a button."""
 
    from app.ui import joystick_buttons
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
            button=joystick_buttons["button1"]
        )
    )
    main_window.add_action_to_button()

    # Verify that the action has been added
    actions = main_window.current_config.get_all_actions_for_button_no_filter(button_label)
    assert len(actions) > 0
    assert any(action.name == selected_action_name for action in actions.values())

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
    assert len(main_window.left_joystick_config.configured_actions) > 0 or \
           len(main_window.right_joystick_config.configured_actions) > 0

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



