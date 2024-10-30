# main.py
from pathlib import Path
import sys
import json
import logging
from typing import Dict

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QMessageBox, QComboBox
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QRect, Qt, QEvent, QObject

from models import configmap
from models.joystick import JoystickConfig, JoyAction, get_joystick_buttons
from models.ui_action import ActionSelectionDialog
from utils.logger import setup_logging

# Additional imports for your specific functions
from models.actions import Action, get_all_defined_game_actions, get_all_subcategories_actions
from models.configmap import ActionMap, Rebind, get_action_maps_object
from globals import get_installation

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

current_path = Path(__file__).parent
left_image_path = current_path / "images/vkb_left.png"
right_image_path = current_path / "images/vkb_right.png"

actions = get_all_subcategories_actions()
all_default_actions = get_all_defined_game_actions()
joystick_buttons = get_joystick_buttons()

width: int = 155
height: int = 35


class ControlMapperApp(QMainWindow):
    CONFIG_FILE = "config.json"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VKB Joystick Mapper")
        self.setGeometry(100, 100, 1950, 938)
        self.background_label = QLabel(self)
        self.background_label.setGeometry(0, 0, 1950, 938)

        self.left_joystick_config = JoystickConfig(side="left", configured_actions={})
        self.right_joystick_config = JoystickConfig(side="right", configured_actions={})
        self.current_config = self.left_joystick_config
        self.current_joystick = "left"

        self.modifier_enabled = False
        self.multitap_enabled = False
        self.hold_enabled = False
        self.unsupported_actions = {}
        self.button_refs : Dict[str, QPushButton]= {}
        self.init_ui()

        self.install = get_installation("LIVE")
        assert self.install is not None
        self.exported_control_maps = self.install.exported_control_maps
        self.populate_control_maps_combo_box()

    def init_ui(self):
        self.load_background(str(left_image_path))
        self.create_joystick_buttons()
        self.create_controls()

    def create_controls(self):
        self.switch_button = QPushButton("Switch to Right Joystick", self)
        self.switch_button.setGeometry(10, 10, 200, 40)
        self.switch_button.clicked.connect(self.toggle_joystick)

        self.modifier_button = QPushButton("Enable Modifier", self)
        self.modifier_button.setGeometry(220, 10, 200, 40)
        self.modifier_button.clicked.connect(self.toggle_modifier)

        self.multitap_button = QPushButton("Enable Multitap", self)
        self.multitap_button.setGeometry(430, 10, 200, 40)
        self.multitap_button.clicked.connect(self.toggle_multitap)

        self.hold_button = QPushButton("Enable Hold", self)
        self.hold_button.setGeometry(640, 10, 200, 40)
        self.hold_button.clicked.connect(self.toggle_hold)

        self.control_maps_combo_box = QComboBox(self)
        self.control_maps_combo_box.setPlaceholderText("--Select Control Map--")
        self.control_maps_combo_box.setVisible(True)
        self.control_maps_combo_box.setGeometry(850, 10, 400, 40)
        self.control_maps_combo_box.setMaxVisibleItems(10)
        self.control_maps_combo_box.activated.connect(self.select_control_map)
        self.control_maps_combo_box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.control_maps_combo_box.installEventFilter(self)

    def toggle_modifier(self) -> None:
        self.modifier_enabled = not self.modifier_enabled
        self.modifier_button.setText(
            "Disable Modifier" if self.modifier_enabled else "Enable Modifier"
        )
        self.update_joystick_buttons()

    def toggle_multitap(self) -> None:
        self.multitap_enabled = not self.multitap_enabled
        self.multitap_button.setText(
            "Disable Multitap" if self.multitap_enabled else "Enable Multitap"
        )
        self.update_joystick_buttons()

    def toggle_hold(self) -> None:
        self.hold_enabled = not self.hold_enabled
        self.hold_button.setText(
            "Disable Hold" if self.hold_enabled else "Enable Hold"
        )
        self.update_joystick_buttons()

    def select_control_map(self, index: int) -> None:
        control_map_file = self.exported_control_maps[index]
        self.control_map = get_action_maps_object(control_map_file)
        self.joystick_sides = self.get_joystick_sides(self.control_map)
        self.load_joystick_mappings()
        self.update_joystick_buttons()

    def get_joystick_sides(self, control_map) -> dict[str, ]:
        instance_number_mapping = {}
        for option in control_map.options:
            if option.product is None:
                continue
            if 'VKBsim Gladiator EVO' in option.product:
                product_name = option.product.split("{")[0]
                side = "left" if "L" in product_name else "right"
                instance_number_mapping[option.instance] = side
        return instance_number_mapping

    def load_joystick_mappings(self):
        self.left_joystick_config.clear_mappings()
        self.right_joystick_config.clear_mappings()
        for actionmap in self.control_map.actionmap:
            self.process_action_map(actionmap)

    def process_action_map(self, actionmap: configmap.ActionMap):
        for action in actionmap.action:
            for rebind in action.rebinding:
                self.process_rebind(action, rebind)

    def process_rebind(self, action: "configmap.Action", rebind: configmap.Rebind):
        try:
            joy_command_input_string = rebind.input
            if not joy_command_input_string.startswith("js"):
                return
            modifier = '+' in joy_command_input_string
            if modifier:
                joy_modifier, js_button = joy_command_input_string.split("+")
                js_str = joy_modifier.split("_")[0]
            else:
                parts = joy_command_input_string.split("_")
                js_str = parts[0]
                js_button = "_".join(parts[1:])
            if not js_button.strip():
                return
            try:
                js_number = int(js_str[2:])
            except:
                pass
            side = self.joystick_sides[js_number]
            try:
                default_action_conf = all_default_actions[action.name]
            except KeyError:
                logger.warning(f"Action {action.name} not found in default actions.")
                self.unsupported_actions[action.name] = action
            hold = default_action_conf.activationmode == "delayed_press"                    
            main_category = default_action_conf.main_category
            sub_category = default_action_conf.sub_category
            multitap = rebind.multitap is not None
            joy_action = JoyAction(
                name=action.name,
                input=rebind.input,
                multitap=multitap,
                category=main_category,
                hold=hold,
                sub_category=sub_category,
                modifier=modifier,
                button=joystick_buttons[js_button]
            )
            if side == "left":
                self.left_joystick_config.set_mapping(joy_action)
            else:
                self.right_joystick_config.set_mapping(joy_action)
        except Exception as e:
            logger.exception(f"Error processing rebind: {e}")

    def populate_control_maps_combo_box(self) -> None:
        self.control_maps_combo_box.clear()
        for control_map in self.exported_control_maps:
            self.control_maps_combo_box.addItem(control_map.split('/')[-1])

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        return super().eventFilter(source, event)

    def toggle_joystick(self) -> None:
        self.save_current_mappings()
        if self.current_joystick == "left":
            self.current_joystick = "right"
            self.current_config = self.right_joystick_config
            self.switch_button.setText("Switch to Left Joystick")
            self.load_background(str(right_image_path))
        else:
            self.current_joystick = "left"
            self.current_config = self.left_joystick_config
            self.switch_button.setText("Switch to Right Joystick")
            self.load_background(str(left_image_path))
        self.update_joystick_buttons()

    def save_current_mappings(self) -> None:
        pass  # Implement if needed

    def load_background(self, image_path: str) -> None:
        pixmap = QPixmap(image_path)
        self.background_label.setPixmap(pixmap)
        self.background_label.setGeometry(0, 0, pixmap.width(), pixmap.height())

    def create_joystick_buttons(self) -> None:
        for button in joystick_buttons.values():
            self.create_mappable_button(
                button.name,
                QRect(button.coord_x_left[self.current_config.side], button.coord_y_top, width, height)
            )

    def update_joystick_buttons(self) -> None:
        for label, button in self.button_refs.items():
            self.update_button_label(label)
            self.update_button_geometry(label, button)
        
    def update_button_geometry(self, label: str, button: QPushButton) -> None:
        geometry: QRect = QRect(joystick_buttons[label].coord_x_left[self.current_config.side], joystick_buttons[label].coord_y_top, width, height)
        button = self.button_refs[label]
        button.setGeometry(geometry)

    def create_mappable_button(self, label: str, geometry: QRect) -> None:
        from functools import partial
        button = QPushButton(label, self)
        button.setGeometry(geometry)
        self.apply_button_style(button, action=False)
        button.clicked.connect(partial(self.show_action_selector, button, label))
        button.show()
        self.button_refs[label] = button

    def show_action_selector(self, button: QPushButton, label: str) -> None:
        dialog = ActionSelectionDialog(actions, self)
        if dialog.exec():
            selected_action = dialog.selected_action
            if selected_action == "Clear Action":
                self.current_config.clear_mapping(label, self.modifier_enabled)
            else:
                self.set_action_for_button(label, selected_action)
            self.update_button_label(label)

    def set_action_for_button(self, label: str, action_name: str):
        action = all_default_actions.get(action_name)
        if action:
            hold = action.activationmode == "delayed_press"
            joy_action = JoyAction(
                name=action_name,
                input=label,
                multitap=self.multitap_enabled,
                hold=hold,
                category=action.main_category,
                sub_category=action.sub_category,
                modifier=self.modifier_enabled,
                button=joystick_buttons[label]
            )
            self.current_config.set_mapping(joy_action)
        else:
            logger.warning(f"Action {action_name} not found.")

    def update_button_label(self, label: str):
        actions = self.current_config.get_actions_for_button(label, self.modifier_enabled, multitap=self.multitap_enabled, hold=self.hold_enabled)
        button = self.button_refs[label]
        if actions:
            button.setText("\n".join(action.name for action in actions.values()))
            self.apply_button_style(button, True)
        else:
            button.setText(label)
            self.apply_button_style(button, False)

    def apply_button_style(self, button: QPushButton, action: bool) -> None:
        if action:
            button.setStyleSheet("""
                QPushButton {
                    background-color: rgba(150, 255, 150, 100);
                    color: rgba(0, 0, 0, 255);
                    border: 2px solid rgba(0, 255, 0, 180);
                }
            """)
        else:
            button.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 255);
                    color: rgba(150, 150, 150, 255);
                    border: 2px solid rgba(255, 255, 255, 0);
                }
                QPushButton:hover {
                    background-color: rgba(150, 150, 255, 100);
                    color: rgba(255, 255, 255, 255);
                    border: 2px solid rgba(255, 255, 255, 180);
                }
            """)

    def save_config(self) -> None:
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump({
                    "left": self.left_joystick_config.model_dump(),
                    "right": self.right_joystick_config.model_dump()
                }, f, indent=4)
            QMessageBox.information(self, "Success", "Configuration saved successfully.")
        except Exception as e:
            logger.exception("Failed to save configuration")
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {e}")

    def load_config(self) -> None:
        try:
            if Path(self.CONFIG_FILE).exists():
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.left_joystick_config = JoystickConfig.model_validate(data["left"])
                    self.right_joystick_config = JoystickConfig.model_validate(data["right"])
                if self.current_joystick == "left":
                    self.current_config = self.left_joystick_config
                else:
                    self.current_config = self.right_joystick_config
                self.update_joystick_buttons()
                QMessageBox.information(self, "Success", "Configuration loaded successfully.")
            else:
                QMessageBox.warning(self, "Error", "No configuration file found.")
        except Exception as e:
            logger.exception("Failed to load configuration")
            QMessageBox.warning(self, "Error", f"Failed to load configuration: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ControlMapperApp()
    window.show()
    sys.exit(app.exec())
