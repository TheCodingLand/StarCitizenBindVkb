# main.py
from pathlib import Path
import sys
import json
import logging
from typing import Dict, Optional, List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QMessageBox, QComboBox,
    QWidget, QListWidget, QVBoxLayout, QHBoxLayout, QListWidgetItem
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QRect, Qt, QEvent, QObject
from PyQt6.QtGui import QPixmap, QIcon
from localization import LocalizationFile
from models import configmap
from models.joystick import JoystickConfig, JoyAction, get_joystick_buttons
from models.ui_action import ActionSelectionDialog
from utils.logger import setup_logging

# Additional imports for your specific functions
from models.actions import Action, get_all_defined_game_actions, get_all_subcategories_actions
from models.configmap import (
    ExportedActionMapsFile, ActionMap, Rebind, get_action_maps_object
)
from globals import APP_PATH, get_installation

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


icon_path = APP_PATH / "images/app_icon.png" 
left_image_path = APP_PATH / "images/vkb_left.png"
right_image_path = APP_PATH / "images/vkb_right.png"

actions: Dict[str, List[str]] = get_all_subcategories_actions()
all_default_actions: Dict[str, Action] = get_all_defined_game_actions()
joystick_buttons = get_joystick_buttons()

width: int = 155
height: int = 35


class ControlMapperApp(QMainWindow):
    CONFIG_FILE: str = "config.json"

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("VKB Joystick Mapper")

        self.setWindowIcon(QIcon(str(icon_path)))
        self.setWindowIconText("VKB Joystick Mapper")
        # Adjust the main window size to accommodate the action panel
        self.setGeometry(100, 100, 1950 + 400, 938)  # Increased width by 400 for the panel

        # Create central widget and main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)

        # Left side widget for joystick image and buttons
        self.left_widget = QWidget(self.central_widget)
        self.left_layout = QVBoxLayout(self.left_widget)
        self.main_layout.addWidget(self.left_widget)

        # Right side widget for action panel
        self.action_panel = QWidget(self.central_widget)
        self.action_panel_layout = QVBoxLayout(self.action_panel)
        self.main_layout.addWidget(self.action_panel)

        # Store joystick configurations and other variables
        self.left_joystick_config: JoystickConfig = JoystickConfig(
            side="left", configured_actions={}
        )
        self.right_joystick_config: JoystickConfig = JoystickConfig(
            side="right", configured_actions={}
        )
        self.current_config: JoystickConfig = self.left_joystick_config
        self.current_joystick: str = "left"

        self.modifier_enabled: bool = False
        self.multitap_enabled: bool = False
        self.hold_enabled: bool = False
        self.unsupported_actions: Dict[str, configmap.Action] = {}
        self.button_refs: Dict[str, QPushButton] = {}
        self.joystick_sides: Dict[int, str] = {}
        self.selected_button_label: Optional[str] = None  # Currently selected button label

        self.init_ui()

        self.install = get_installation("LIVE")
        assert self.install is not None
        self.exported_control_maps: List[str] = self.install.exported_control_maps
        self.control_map: Optional[ExportedActionMapsFile] = None
        self.populate_control_maps_combo_box()

    def init_ui(self) -> None:
        self.create_controls()
        self.create_joystick_image()
        self.create_joystick_buttons()
        self.create_action_panel()

    def create_controls(self) -> None:
        # Controls at the top of the left widget
        controls_widget = QWidget(self.left_widget)
        controls_layout = QHBoxLayout(controls_widget)

        self.switch_button: QPushButton = QPushButton("Switch to Right Joystick", controls_widget)
        self.switch_button.clicked.connect(self.toggle_joystick)
        controls_layout.addWidget(self.switch_button)

        self.modifier_button: QPushButton = QPushButton("Enable Modifier", controls_widget)
        self.modifier_button.clicked.connect(self.toggle_modifier)
        controls_layout.addWidget(self.modifier_button)

        self.multitap_button: QPushButton = QPushButton("Enable Multitap", controls_widget)
        self.multitap_button.clicked.connect(self.toggle_multitap)
        controls_layout.addWidget(self.multitap_button)

        self.hold_button: QPushButton = QPushButton("Enable Hold", controls_widget)
        self.hold_button.clicked.connect(self.toggle_hold)
        controls_layout.addWidget(self.hold_button)

        self.control_maps_combo_box: QComboBox = QComboBox(controls_widget)
        self.control_maps_combo_box.setPlaceholderText("--Select Control Map--")
        self.control_maps_combo_box.setVisible(True)
        self.control_maps_combo_box.setMaxVisibleItems(10)
        self.control_maps_combo_box.activated.connect(self.select_control_map)
        self.control_maps_combo_box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.control_maps_combo_box.installEventFilter(self)
        controls_layout.addWidget(self.control_maps_combo_box)

        self.left_layout.addWidget(controls_widget)

    def create_joystick_image(self) -> None:
        # Load the joystick image
        self.background_label: QLabel = QLabel(self.left_widget)
        pixmap: QPixmap = QPixmap(str(left_image_path))
        self.background_label.setPixmap(pixmap)
        self.background_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.left_layout.addWidget(self.background_label)

    def create_action_panel(self) -> None:
        # Create a panel on the right side (already part of main_layout)
        panel_width = 400
        self.action_panel.setMinimumWidth(panel_width)
        self.action_panel.setMaximumWidth(panel_width)

        # Label to display the selected button
        self.selected_button_label_widget: QLabel = QLabel("Selected Button: None", self.action_panel)
        self.action_panel_layout.addWidget(self.selected_button_label_widget)

        # List widget to display actions
        self.actions_list_widget: QListWidget = QListWidget(self.action_panel)
        self.action_panel_layout.addWidget(self.actions_list_widget)

        # Buttons to add or remove actions
        buttons_layout = QHBoxLayout()
        self.add_action_button: QPushButton = QPushButton("Add Action", self.action_panel)
        self.add_action_button.clicked.connect(self.add_action_to_button)
        buttons_layout.addWidget(self.add_action_button)

        self.remove_action_button: QPushButton = QPushButton("Remove Selected Action", self.action_panel)
        self.remove_action_button.clicked.connect(self.remove_selected_action)
        buttons_layout.addWidget(self.remove_action_button)

        self.action_panel_layout.addLayout(buttons_layout)

        # Spacer to push the buttons to the top
        self.action_panel_layout.addStretch()

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
        control_map_file: str = self.exported_control_maps[index]
        self.control_map = get_action_maps_object(control_map_file)
        self.joystick_sides: Dict[int, str] = self.get_joystick_sides(self.control_map)
        self.load_joystick_mappings()
        self.update_joystick_buttons()

    def get_joystick_sides(
        self, control_map: ExportedActionMapsFile
    ) -> Dict[int, str]:
        instance_number_mapping: Dict[int, str] = {}
        for option in control_map.options:
            if option.product is None:
                continue
            if "VKBsim Gladiator EVO" in option.product:
                product_name: str = option.product.split("{")[0]
                side: str = "left" if "L" in product_name else "right"
                instance_number_mapping[option.instance] = side
        return instance_number_mapping

    def load_joystick_mappings(self) -> None:
        self.left_joystick_config.clear_mappings()
        self.right_joystick_config.clear_mappings()
        if self.control_map is None:
            return
        for actionmap in self.control_map.actionmap:
            self.process_action_map(actionmap)
        # After processing the control map, apply default bindings
        self.apply_default_bindings()

    def process_action_map(self, actionmap: ActionMap) -> None:
        for action in actionmap.action:
            for rebind in action.rebinding:
                self.process_rebind(action, rebind)

    def process_rebind(
        self, action: configmap.Action, rebind: Rebind
    ) -> None:
        try:
            joy_command_input_string: str = rebind.input
            if not joy_command_input_string.startswith("js"):
                return
            modifier: bool = "+" in joy_command_input_string
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
                js_number: int = int(js_str[2:])
            except ValueError:
                return
            side: str = self.joystick_sides[js_number]
            try:
                default_action_conf: Action = all_default_actions[action.name]
            except KeyError:
                logger.warning(
                    f"Action {action.name} not found in default actions."
                )
                self.unsupported_actions[action.name] = action
                return
            hold: bool = default_action_conf.activationmode == "delayed_press"
            main_category: str = default_action_conf.main_category
            sub_category: str = default_action_conf.sub_category
            multitap: bool = rebind.multitap is not None
            button = joystick_buttons.get(js_button)
            if button is None:
                logger.warning(
                    f"Button {js_button} not found in joystick_buttons."
                )
                return
            joy_action = JoyAction(
                name=action.name,
                input=rebind.input,
                multitap=multitap,
                hold=hold,
                category=main_category,
                sub_category=sub_category,
                modifier=modifier,
                button=button,
            )
            if side == "left":
                self.left_joystick_config.set_mapping(joy_action)
            else:
                self.right_joystick_config.set_mapping(joy_action)
        except Exception as e:
            logger.exception(f"Error processing rebind: {e}")

    def apply_default_bindings(self) -> None:
        """
        Reapply default binds for actions not set elsewhere.
        """
        # Collect all configured action names
        configured_action_names = set()
        for action in self.left_joystick_config.configured_actions.values():
            configured_action_names.add(action.name)
        for action in self.right_joystick_config.configured_actions.values():
            configured_action_names.add(action.name)

        # Determine which joystick is js1 (assumed default)
        js1_side = self.joystick_sides.get(1)
        if js1_side == "left":
            default_joystick = self.left_joystick_config
        elif js1_side == "right":
            default_joystick = self.right_joystick_config
        else:
            # If js1 is not found, default to left joystick
            default_joystick = self.left_joystick_config

        for action in all_default_actions.values():
            if action.name in configured_action_names:
                continue  # Action is already configured
            if action.joystick and action.joystick.strip():
                # Determine if modifier is used
                modifier = '+' in action.joystick
                if modifier:
                    js_button, _ = action.joystick.split('+', 1)
                else:
                    js_button = action.joystick
                if js_button not in joystick_buttons:
                    continue  # Button not recognized
                hold = action.activationmode == "delayed_press"
                joy_action = JoyAction(
                    name=action.name,
                    input=js_button,
                    multitap=False,
                    hold=hold,
                    category=action.main_category,
                    sub_category=action.sub_category,
                    modifier=modifier,
                    button=joystick_buttons[js_button],
                )
                default_joystick.set_mapping(joy_action)

    def populate_control_maps_combo_box(self) -> None:
        self.control_maps_combo_box.clear()
        for control_map in self.exported_control_maps:
            self.control_maps_combo_box.addItem(control_map.split("/")[-1])

    def eventFilter(self, source: QObject, event: QEvent) -> bool:
        return super().eventFilter(source, event)

    def toggle_joystick(self) -> None:
        self.save_current_mappings()
        if self.current_joystick == "left":
            self.current_joystick = "right"
            self.current_config = self.right_joystick_config
            self.switch_button.setText("Switch to Left Joystick")
            self.load_joystick_image(str(right_image_path))
        else:
            self.current_joystick = "left"
            self.current_config = self.left_joystick_config
            self.switch_button.setText("Switch to Right Joystick")
            self.load_joystick_image(str(left_image_path))
        self.update_joystick_buttons()

    def save_current_mappings(self) -> None:
        pass  # Implement if needed

    def load_joystick_image(self, image_path: str) -> None:
        pixmap: QPixmap = QPixmap(image_path)
        self.background_label.setPixmap(pixmap)
        self.background_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Adjust the size of the label to fit the image
        self.background_label.adjustSize()

    def create_joystick_buttons(self) -> None:
        # Overlay buttons on top of the joystick image
        for button in joystick_buttons.values():
            self.create_mappable_button(
                button.name,
                QRect(
                    button.coord_x_left[self.current_config.side],
                    button.coord_y_top,
                    width,
                    height,
                ),
            )

    def update_joystick_buttons(self) -> None:
        for label, button in self.button_refs.items():
            self.update_button_label(label)
            self.update_button_geometry(label, button)

    def update_button_geometry(self, label: str, button: QPushButton) -> None:
        geometry: QRect = QRect(
            joystick_buttons[label].coord_x_left[self.current_config.side],
            joystick_buttons[label].coord_y_top,
            width,
            height,
        )
        button.setGeometry(geometry)

    def create_mappable_button(self, label: str, geometry: QRect) -> None:
        button: QPushButton = QPushButton(label, self.background_label)
        button.setGeometry(geometry)
        button.setStyleSheet("background-color: transparent;")
        self.apply_button_style(button, action=False)
        button.clicked.connect(
            lambda _, b=button, l=label: self.show_action_panel(b, l)
        )
        button.show()
        self.button_refs[label] = button

    def show_action_panel(
        self, button: QPushButton, label: str
    ) -> None:
        """
        Display the action panel with all mappings for the selected button.
        """
        self.selected_button_label = label
        self.selected_button_label_widget.setText(f"Selected Button: {label}")

        # Clear the existing list
        self.actions_list_widget.clear()

        # Get all actions for the button without filtering
        all_actions = self.current_config.get_all_actions_for_button_no_filter(label)

        # Populate the list widget
        for key, joy_action in all_actions.items():
            item_text = f"{joy_action.name} | Modifier: {joy_action.modifier} | Multitap: {joy_action.multitap} | Hold: {joy_action.hold}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, key)  # Store the key for reference
            self.actions_list_widget.addItem(item)

    def add_action_to_button(self) -> None:
        """
        Open the action selection dialog and add the selected action to the button.
        """
        if not self.selected_button_label:
            QMessageBox.warning(self, "Error", "No button selected.")
            return

        dialog = ActionSelectionDialog(actions, self)
        if dialog.exec():
            selected_action_name: str = dialog.selected_action
            action: Optional[Action] = all_default_actions.get(selected_action_name)
            if action:
                hold: bool = self.hold_enabled
                multitap: bool = self.multitap_enabled
                modifier: bool = self.modifier_enabled
                joy_action = JoyAction(
                    name=selected_action_name,
                    input=self.selected_button_label,
                    multitap=multitap,
                    hold=hold,
                    category=action.main_category,
                    sub_category=action.sub_category,
                    modifier=modifier,
                    button=joystick_buttons[self.selected_button_label],
                )
                self.current_config.set_mapping(joy_action)
                self.update_button_label(self.selected_button_label)
                self.show_action_panel(None, self.selected_button_label)  # Refresh the panel
            else:
                logger.warning(f"Action {selected_action_name} not found.")

    def remove_selected_action(self) -> None:
        """
        Remove the selected action from the button's mappings.
        """
        selected_items = self.actions_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Error", "No action selected.")
            return

        for item in selected_items:
            key = item.data(Qt.ItemDataRole.UserRole)
            self.current_config.remove_mapping_by_key(key)
            self.actions_list_widget.takeItem(self.actions_list_widget.row(item))

        self.update_button_label(self.selected_button_label)

    def update_button_label(self, label: str) -> None:
        actions_dict = self.current_config.get_actions_for_button(
            label,
            self.modifier_enabled,
            multitap=self.multitap_enabled,
            hold=self.hold_enabled,
        )
        button: QPushButton = self.button_refs[label]
        if actions_dict:
            button.setText(
                "\n".join(action.name for action in actions_dict.values())
            )
            self.apply_button_style(button, True)
        else:
            button.setText(label)
            self.apply_button_style(button, False)

    def apply_button_style(
        self, button: QPushButton, action: bool
    ) -> None:
        if action:
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: rgba(150, 255, 150, 100);
                    color: rgba(0, 0, 0, 255);
                    border: 2px solid rgba(0, 255, 0, 180);
                }
            """
            )
        else:
            button.setStyleSheet(
                """
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
            """
            )

    def save_config(self) -> None:
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(
                    {
                        "left": self.left_joystick_config.model_dump(),
                        "right": self.right_joystick_config.model_dump(),
                    },
                    f,
                    indent=4,
                )
            QMessageBox.information(
                self, "Success", "Configuration saved successfully."
            )
        except Exception as e:
            logger.exception("Failed to save configuration")
            QMessageBox.warning(
                self, "Error", f"Failed to save configuration: {e}"
            )

    def load_config(self) -> None:
        try:
            if Path(self.CONFIG_FILE).exists():
                with open(self.CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    self.left_joystick_config = JoystickConfig.model_validate(
                        data["left"]
                    )
                    self.right_joystick_config = JoystickConfig.model_validate(
                        data["right"]
                    )
                if self.current_joystick == "left":
                    self.current_config = self.left_joystick_config
                else:
                    self.current_config = self.right_joystick_config
                self.update_joystick_buttons()
                QMessageBox.information(
                    self, "Success", "Configuration loaded successfully."
                )
            else:
                QMessageBox.warning(
                    self, "Error", "No configuration file found."
                )
        except Exception as e:
            logger.exception("Failed to load configuration")
            QMessageBox.warning(
                self, "Error", f"Failed to load configuration: {e}"
            )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ControlMapperApp()
    window.show()
    sys.exit(app.exec())
