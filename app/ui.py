# main.py
from pathlib import Path
import sys
import json
import logging
from typing import Any, Dict, Optional, List, Union

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QMessageBox, QComboBox,
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6 import QtWidgets
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QRect, Qt, QEvent, QObject
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6 import QtGui
from app.config import Config

from app.models import configmap
from app.models.game_control_map import GameAction, GameActionMap
from app.models.joystick import JoystickConfig, JoyAction, get_joystick_buttons
from app.models.settings_dialog import SettingsDialog
from app.models.ui_action import ActionSelectionDialog
from app.utils.logger import setup_logging

# Additional imports for your specific functions
from app.models.actions import Action, get_all_defined_game_actions, get_all_subcategories_actions
from app.models.configmap import (
    ExportedActionMapsFile, ActionMap, Rebind, get_action_maps_object
)
from app.globals import APP_PATH, get_installation, localization_file

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)


icon_path = APP_PATH / "data/images/app_icon.png" 
left_image_path = APP_PATH / "data/images/vkb_left.png"
right_image_path = APP_PATH / "data/images/vkb_right.png"

cat_subcat_actions = get_all_subcategories_actions()
all_default_actions = get_all_defined_game_actions()
joystick_buttons = get_joystick_buttons()

width: int = 155
height: int = 35


class ControlMapperApp(QMainWindow):
    CONFIG_FILE: str = "config.json"

    def __init__(self) -> None:
        super().__init__()
        self.config = Config.get_config()
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
        self.unsupported_actions: List[Dict[str, Any]] = []
        self.install_type: str = self.config.install_type

        self.previous_selected_button: Optional[QPushButton] = None
        self.button_refs: Dict[str, QPushButton] = {}
        self.joystick_sides: Dict[int, str] = {}
        self.selected_button_label: Optional[str] = None  # Currently selected button label
        
        self.init_ui()
        self.init_install_type()

    def init_install_type(self) -> None:
        self.install = get_installation(self.config.installation_path, self.config.install_type)
        if self.install is None:
            # highlight the settings button
            self.settings_button.setStyleSheet("background-color: #FF0000;")
            self.exported_control_maps = []
        else:
            self.settings_button.setStyleSheet("background-color: rgba(150, 150, 150, 255);")
            self.exported_control_maps: List[str] = self.install.exported_control_maps
        self.control_map = None
        self.populate_control_maps_combo_box()

    def init_ui(self) -> None:
        self.create_controls()
        self.create_joystick_image()
        self.create_joystick_buttons()
        self.create_action_panel()

    
            
    def open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            # Reload the config
            self.config = Config.get_config()
            self.install_type = self.config.install_type
            # Reinitialize the installation
            self.init_install_type()
            # Update any other components that depend on the config
            self.update_joystick_buttons()

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

        # Add the Settings button
        self.settings_button: QPushButton = QPushButton("Settings", controls_widget)
        self.settings_button.clicked.connect(self.open_settings_dialog)
        controls_layout.addWidget(self.settings_button)

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
        panel_width = 560
        self.action_panel.setMinimumWidth(panel_width)
        self.action_panel.setMaximumWidth(panel_width)
        
        # Label to display the selected button
        self.selected_button_label_widget: QLabel = QLabel("Selected Button: None", self.action_panel)
        self.action_panel_layout.addWidget(self.selected_button_label_widget)

        # Create a QTableWidget to display actions
        self.actions_table_widget: QTableWidget = QTableWidget(self.action_panel)
        self.actions_table_widget.setColumnCount(4)
        self.actions_table_widget.setHorizontalHeaderLabels(['Action Name', 'Modifier', 'Multitap', 'Hold'])
        self.actions_table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.actions_table_widget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.actions_table_widget.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.actions_table_widget.setFixedHeight(400)
        self.action_panel_layout.addWidget(self.actions_table_widget)

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

        # **Add Unsupported Actions Section**
        self.unsupported_actions_label = QLabel("Unsupported Actions:", self.action_panel)
        self.action_panel_layout.addWidget(self.unsupported_actions_label)

        # Create a QTableWidget to display unsupported actions
        self.unsupported_actions_table_widget: QTableWidget = QTableWidget(self.action_panel)
        self.unsupported_actions_table_widget.setColumnCount(4)
        self.unsupported_actions_table_widget.setHorizontalHeaderLabels(['Action Name', 'Button', 'Modifier', 'Side'])
        self.unsupported_actions_table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.unsupported_actions_table_widget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.unsupported_actions_table_widget.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.unsupported_actions_table_widget.setFixedHeight(400)
        self.action_panel_layout.addWidget(self.unsupported_actions_table_widget)


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
        try:
            self.control_map = get_action_maps_object(control_map_file)
        except Exception as e:
            logger.exception(f"Error loading control map: {e}")
            self.control_map = None
            # Display a message to the user
            QMessageBox.warning(
                self,
                "Error Loading Control Map",
                "An error occurred while loading this control map."
            )
            return

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
            if self.config.joystick_left_name_filter in option.product:
                product_name: str = option.product.split("{")[0]
                side: str = "left" if self.config.joystick_side_identifier_left in product_name else "right"
                instance_number_mapping[option.instance] = side
        return instance_number_mapping


    def update_unsupported_actions_table(self) -> None:
        # Clear the existing table
        self.unsupported_actions_table_widget.setRowCount(0)

        # Populate the table widget
        for action_info in self.unsupported_actions:
            row_position = self.unsupported_actions_table_widget.rowCount()
            self.unsupported_actions_table_widget.insertRow(row_position)

            # Create table items
            action_name_item = QTableWidgetItem(action_info['action_name'])
            button_item = QTableWidgetItem(action_info['button'])
            modifier_item = QTableWidgetItem('Yes' if action_info['modifier'] else 'No')
            side_item = QTableWidgetItem(action_info['side'])

            # Optionally, apply styling based on modifier
            if action_info['modifier']:
                modifier_item.setBackground(QtGui.QColor('lightgreen'))
                modifier_item.setForeground(QtGui.QColor('black'))

            # Add items to the table
            self.unsupported_actions_table_widget.setItem(row_position, 0, action_name_item)
            self.unsupported_actions_table_widget.setItem(row_position, 1, button_item)
            self.unsupported_actions_table_widget.setItem(row_position, 2, modifier_item)
            self.unsupported_actions_table_widget.setItem(row_position, 3, side_item)

        #Adjust column widths
        self.unsupported_actions_table_widget.resizeColumnsToContents()


    def load_joystick_mappings(self) -> None:
        
        self.unsupported_actions.clear()
        self.left_joystick_config.clear_mappings()
        self.right_joystick_config.clear_mappings()
        if self.control_map is None:
            return
        for actionmap in self.control_map.actionmap:
            self.process_action_map(actionmap)
        # After processing the control map, apply default bindings
        self.apply_default_bindings()

        self.update_unsupported_actions_table()

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
                default_action_conf: List[GameAction] = all_default_actions[action.name]
            except KeyError:
                logger.warning(
                    f"Action {action.name} not found in default actions."
                )
                unsupported_action_info : Dict[str, Union[str, bool]]= {
                    'action_name': action.name,
                    'button': js_button,
                    'modifier': modifier,
                    'side': side
                }
                self.unsupported_actions.append(unsupported_action_info)
                return
            for game_action in default_action_conf:
                
                #hold: bool = game_action.activation_mode == "delayed_press"
                hold = game_action.on_hold == '1'
                main_category: str = game_action.main_category
                sub_category: str = game_action.sub_category
                multitap: bool = rebind.multitap is not None
                button = joystick_buttons.get(js_button)
                if button is None:
                    logger.warning(
                        f"Button {js_button} not found in joystick_buttons."
                    )
                    continue
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
        
        for main_cat, action_game_map in cat_subcat_actions.root.items():
            sub_cat = action_game_map.name
            for action in action_game_map.action:
                if action.name in configured_action_names:
                    continue
                if action.joystick is None:
                    continue
                if isinstance(action.joystick, str):
                    #hold = bind.joystick. == "delayed_press"
                    hold = action.activation_mode == "delayed_press"
                    js_button= action.joystick
                    
                else:
                    js_button= action.joystick.input
                    hold = action.joystick.activationmode == "delayed_press"
                if js_button in [" ", ""]:
                    continue
                modifier = "+" in js_button
                if modifier:
                    js_button = js_button.split("+")[-1]
                if 'slider' in js_button:
                    continue
                joy_action = JoyAction(
                        name=action.name,
                        input=js_button,
                        multitap=False,
                        hold=hold,
                        category=main_cat,
                        sub_category=sub_cat,
                        modifier=modifier,
                        button=joystick_buttons[js_button],
                    )
                    
                
                default_joystick.set_mapping(joy_action)

    def binds_from_action(self, bind: GameActionMap) -> List[JoyAction]:
        pass

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

    def show_action_panel(self, button: QPushButton, label: str) -> None:
        """
        Display the action panel with all mappings for the selected button.
        """
        self.apply_button_style(button, action=self.has_action(label), selected=True)
        
        if self.previous_selected_button and self.previous_selected_button != button:
            self.update_button_label(self.selected_button_label)
            self.apply_button_style(self.previous_selected_button, action=self.has_action(self.selected_button_label), selected=False)
        
        

        self.previous_selected_button = button
        self.selected_button_label = label
        self.selected_button_label_widget.setText(f"Selected Button: {label}")

        # Clear the existing table
        self.actions_table_widget.setRowCount(0)

        # Get all actions for the button without filtering
        all_actions = self.current_config.get_all_actions_for_button_no_filter(label)

        # Populate the table widget
        for key, joy_action in all_actions.items():
            row_position = self.actions_table_widget.rowCount()
            self.actions_table_widget.insertRow(row_position)

            # Create table items
            action_name_item = QTableWidgetItem(joy_action.name)
            modifier_item = QTableWidgetItem()
            multitap_item = QTableWidgetItem()
            hold_item = QTableWidgetItem()

            # Use checkmarks or color codes to represent True/False
            modifier_item.setText("")
            multitap_item.setText("")
            hold_item.setText("") 
            if joy_action.modifier:   
                modifier_item.setBackground(QtGui.QColor('lightgreen'))
            if joy_action.multitap:
                multitap_item.setBackground(QtGui.QColor('lightblue'))
            if joy_action.hold:
                hold_item.setBackground(QtGui.QColor('lightcoral'))               

            # Store the key in the first item's data
            action_name_item.setData(Qt.ItemDataRole.UserRole, key)

            # Add items to the table
            self.actions_table_widget.setItem(row_position, 0, action_name_item)
            self.actions_table_widget.setItem(row_position, 1, modifier_item)
            self.actions_table_widget.setItem(row_position, 2, multitap_item)
            self.actions_table_widget.setItem(row_position, 3, hold_item)

        # Adjust column widths
        self.actions_table_widget.resizeColumnsToContents()

    def add_action_to_button(self) -> None:
        """
        Open the action selection dialog and add the selected action to the button.
        """
        if not self.selected_button_label:
            QMessageBox.warning(self, "Error", "No button selected.")
            return

        dialog = ActionSelectionDialog(cat_subcat_actions, self)
        if dialog.exec():
            selected_action_name: str = dialog.selected_action
            #selected_action_key: str = dialog.selected_action
            action: List[GameAction] = all_default_actions.get(selected_action_name)
            action_info = action[0]
            if action:
                hold: bool = self.hold_enabled
                multitap: bool = self.multitap_enabled
                modifier: bool = self.modifier_enabled
                joy_action = JoyAction(
                    name=selected_action_name,
                    input=self.selected_button_label,
                    multitap=multitap,
                    hold=hold,
                    category=action_info.main_category,
                    sub_category=action_info.sub_category,
                    modifier=modifier,
                    button=joystick_buttons[self.selected_button_label],
                )
                self.current_config.set_mapping(joy_action)
                self.update_button_label(self.selected_button_label)
                self.show_action_panel(self.button_refs[self.selected_button_label], self.selected_button_label)  # Refresh the panel
                self.update_control_map()
            else:
                logger.warning(f"Action {selected_action_name} not found.")
    def add_action_to_control_map(self, joy_action: JoyAction) -> None:
        
        category = joy_action.sub_category
        assert category is not None

        for actionmap in self.control_map.actionmap:
            if actionmap.name == category:
                actionmap.action.append(joy_action)
                return

      

        

    def update_control_map(self) -> None:
        self.control_map.actionmap.clear()
        for action in self.left_joystick_config.configured_actions.values():
            self.add_action_to_control_map(action)
        for action in self.right_joystick_config.configured_actions.values():
            self.add_action_to_control_map(action)


    def remove_selected_action(self) -> None:
        """
        Remove the selected action from the button's mappings.
        """
        selected_ranges = self.actions_table_widget.selectedRanges()
        if not selected_ranges:
            QMessageBox.warning(self, "Error", "No action selected.")
            return

        for selected_range in selected_ranges:
            for row in range(selected_range.topRow(), selected_range.bottomRow() + 1):
                key_item = self.actions_table_widget.item(row, 0)  # Key is stored in the first column
                if key_item:
                    key = key_item.data(Qt.ItemDataRole.UserRole)
                    self.current_config.remove_mapping_by_key(key)
            # Remove the rows in reverse order to prevent shifting issues
            for row in reversed(range(selected_range.topRow(), selected_range.bottomRow() + 1)):
                self.actions_table_widget.removeRow(row)
        assert self.selected_button_label
        self.update_button_label(self.selected_button_label)

    def has_action(self, label: str) -> bool:
        actions_dict = self.current_config.get_actions_for_button(
            label,
            self.modifier_enabled,
            multitap=self.multitap_enabled,
            hold=self.hold_enabled,
        )
        return bool(actions_dict)

    def update_button_label(self, label: str) -> None:
        button: QPushButton = self.button_refs[label]
        has_action = self.has_action(label)
        if has_action:
            actions_dict = self.current_config.get_actions_for_button(
                label,
                self.modifier_enabled,
                multitap=self.multitap_enabled,
                hold=self.hold_enabled,
            )
            button.setText(
                "\n".join(action.name for action in actions_dict.values())
            )
        else:
            button.setText(label)
        if self.selected_button_label == label:
            self.apply_button_style(button, action=has_action, selected=True)
        else:
            self.apply_button_style(button, action=has_action)

    def apply_button_style(
        self, button: QPushButton, action: bool, selected: bool = False
    ) -> None:
        if selected:
            # Apply neon purple highlight
            
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: #9B30FF;
                    color: #FFFFFF;
                    border: 2px solid #BF3EFF;
                }
                """
            )
        elif action:
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
