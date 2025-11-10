# main.py
from pathlib import Path
import sys
import json
import logging
import copy
from typing import Any, Dict, Optional, List, cast

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QPushButton,
    QMessageBox,
    QComboBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)
from PyQt6 import QtWidgets
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QRect, Qt, QEvent, QObject
from PyQt6.QtGui import QIcon
from PyQt6 import QtGui
import app.models.exported_configmap_xml as configmap
from app.config import Config

from app.models.full_game_control_options import (
    DeviceActivation,
    GameAction,
    get_all_defined_game_actions,
    get_all_subcategories_actions,
)
from app.models.joystick import JoystickConfig, JoyAction, JoyStickButton, get_joystick_buttons
from app.components.settings_dialog import SettingsDialog
from app.components.ui_action import ActionSelectionDialog
from app.utils.logger import setup_logging

from app.domain import (
    ActionIdentifier,
    Binding,
    BindingSet,
    ControlProfile,
    InputSlot,
    ValidationReport,
)
from app.services import BindingPlanner, BindingPlannerContext

# Additional imports for your specific functions
from app.models.exported_configmap_xml import (
    ExportedActionMapsFile,
    ActionMap,
    Rebind,
    get_action_maps_object,
)
from app.globals import APP_PATH, get_installation
import xmltodict  # type: ignore[import-untyped]

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

DEFAULT_CONTROL_MAP_FILENAME = APP_PATH / "data/SCBindsDefault.xml"
icon_path = APP_PATH / "data/images/app_icon.png"
left_image_path = APP_PATH / "data/images/vkb_default_left.png"
right_image_path = APP_PATH / "data/images/vkb_default_right.png"

cat_subcat_actions = get_all_subcategories_actions()
all_default_actions = get_all_defined_game_actions()
joystick_buttons = get_joystick_buttons("VKB Default")

width: int = 155
height: int = 35

test_output_file = APP_PATH / "data/test_output.xml"


def unparse(data: ExportedActionMapsFile) -> str:
    xml_data = {"ActionMaps": [data.model_dump(exclude_none=True, by_alias=True)]}
    with open(test_output_file, "w") as f:
        f.write(xmltodict.unparse(xml_data, pretty=True, indent=" ", short_empty_elements=True))
    return xmltodict.unparse(xml_data)


class ControlMapperApp(QMainWindow):
    CONFIG_FILE: str = "config.json"

    def __init__(self) -> None:
        super().__init__()
        self.control_map: Optional[ExportedActionMapsFile] = None
        self.control_map_template: Optional[ExportedActionMapsFile] = None
        self.exported_control_maps: List[str] = []
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

        self.binding_planner_context = BindingPlannerContext()
        self.binding_planner = BindingPlanner(self.binding_planner_context)
        self.joystick_buttons_by_slot: Dict[str, JoyStickButton] = {
            button.sc_config_name: button for button in joystick_buttons.values()
        }
        self.binding_validation_report: Optional[ValidationReport] = None

        self.previous_selected_button: Optional[QPushButton] = None
        self.button_refs: Dict[str, QPushButton] = {}
        self.joystick_sides: Dict[int, str] = {}
        self.selected_button_label: Optional[str] = None  # Currently selected button label

        self.init_ui()
        self.init_install_type()
        self.set_default_bindings()

    def init_install_type(self) -> None:
        self.install = get_installation(self.config.installation_path, self.config.install_type)
        if self.install is None:
            # highlight the settings button
            self.settings_button.setStyleSheet("background-color: #FF0000;")
            self.exported_control_maps = []
        else:
            self.settings_button.setStyleSheet("background-color: rgba(150, 150, 150, 255);")
            self.exported_control_maps = self.install.exported_control_maps
        self.control_map = None
        self.control_map_template = None
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
        self.selected_button_label_widget: QLabel = QLabel(
            "Selected Button: None", self.action_panel
        )
        self.action_panel_layout.addWidget(self.selected_button_label_widget)

        # Create a QTableWidget to display actions
        self.actions_table_widget: QTableWidget = QTableWidget(self.action_panel)
        self.actions_table_widget.setColumnCount(4)
        self.actions_table_widget.setHorizontalHeaderLabels(
            ["Action Name", "Modifier", "Multitap", "Hold"]
        )
        actions_header = self.actions_table_widget.horizontalHeader()
        if actions_header is not None:
            actions_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.actions_table_widget.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.actions_table_widget.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.actions_table_widget.setFixedHeight(400)
        self.action_panel_layout.addWidget(self.actions_table_widget)

        # Buttons to add or remove actions
        buttons_layout = QHBoxLayout()
        self.add_action_button: QPushButton = QPushButton("Add Action", self.action_panel)
        self.add_action_button.clicked.connect(self.add_action_to_button)
        buttons_layout.addWidget(self.add_action_button)

        self.remove_action_button: QPushButton = QPushButton(
            "Remove Selected Action", self.action_panel
        )
        self.remove_action_button.clicked.connect(self.remove_selected_action)
        buttons_layout.addWidget(self.remove_action_button)

        self.action_panel_layout.addLayout(buttons_layout)

        # Spacer to push the buttons to the top
        self.action_panel_layout.addStretch()

        # **Add Unsupported Actions Section**
        self.unsupported_actions_label = QLabel("Unsupported Actions (none)", self.action_panel)
        self.action_panel_layout.addWidget(self.unsupported_actions_label)
        self._update_unsupported_actions_label()

        # Create a QTableWidget to display unsupported actions
        self.unsupported_actions_table_widget: QTableWidget = QTableWidget(self.action_panel)
        self.unsupported_actions_table_widget.setColumnCount(4)
        self.unsupported_actions_table_widget.setHorizontalHeaderLabels(
            ["Action Name", "Button", "Modifier", "Side"]
        )
        unsupported_header = self.unsupported_actions_table_widget.horizontalHeader()
        if unsupported_header is not None:
            unsupported_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.unsupported_actions_table_widget.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.unsupported_actions_table_widget.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.unsupported_actions_table_widget.setFixedHeight(400)
        self.action_panel_layout.addWidget(self.unsupported_actions_table_widget)

        self.validation_status_label = QLabel("Binding status: Not evaluated", self.action_panel)
        self.validation_status_label.setStyleSheet("color: #666666;")
        self.action_panel_layout.addWidget(self.validation_status_label)

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
        self.hold_button.setText("Disable Hold" if self.hold_enabled else "Enable Hold")
        self.update_joystick_buttons()

    def set_default_bindings(self) -> None:
        self.control_map = get_action_maps_object(str(DEFAULT_CONTROL_MAP_FILENAME))
        self.control_map_template = copy.deepcopy(self.control_map)
        self.joystick_sides = self.get_joystick_sides(self.control_map)
        self.load_joystick_mappings()
        self.update_joystick_buttons()
        self.binding_planner_context.default_profile = self.build_control_profile_snapshot()
        self.update_validation_status_indicator(None)

    def select_control_map(self, index: int) -> None:
        if index < 0 or index >= len(self.exported_control_maps):
            return
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
                "An error occurred while loading this control map.",
            )
            return

        self.control_map_template = copy.deepcopy(self.control_map)
        self.joystick_sides = self.get_joystick_sides(self.control_map)
        self.load_joystick_mappings()
        self.update_joystick_buttons()
        self.binding_planner_context.default_profile = self.build_control_profile_snapshot()

    def get_joystick_sides(self, control_map: ExportedActionMapsFile) -> Dict[int, str]:
        instance_number_mapping: Dict[int, str] = {}
        if control_map is None:
            return instance_number_mapping

        left_filter = self.config.joystick_left_name_filter
        right_filter = self.config.joystick_right_name_filter
        left_identifier = self.config.joystick_side_identifier_left
        right_identifier = self.config.joystick_side_identifier_right

        for option in control_map.options:
            if option.product is None or option.instance is None:
                continue

            product_name = option.product.split("{")[0]
            side: Optional[str] = None

            if left_filter and left_filter in product_name:
                side = "left"
            elif right_filter and right_filter in product_name:
                side = "right"
            elif left_identifier and left_identifier in product_name:
                side = "left"
            elif right_identifier and right_identifier in product_name:
                side = "right"

            if side:
                instance_number_mapping[option.instance] = side

        if self.config.joystick_instance_left not in instance_number_mapping:
            instance_number_mapping[self.config.joystick_instance_left] = "left"
        if self.config.joystick_instance_right not in instance_number_mapping:
            instance_number_mapping[self.config.joystick_instance_right] = "right"

        return instance_number_mapping

    def update_unsupported_actions_table(self) -> None:
        # Clear the existing table
        self.unsupported_actions_table_widget.setRowCount(0)

        # Populate the table widget
        for action_info in self.unsupported_actions:
            row_position = self.unsupported_actions_table_widget.rowCount()
            self.unsupported_actions_table_widget.insertRow(row_position)

            # Create table items
            action_name_item = QTableWidgetItem(action_info["action_name"])
            button_item = QTableWidgetItem(action_info["button"])
            modifier_item = QTableWidgetItem("Yes" if action_info["modifier"] else "No")
            side_item = QTableWidgetItem(action_info["side"])

            # Optionally, apply styling based on modifier
            if action_info["modifier"]:
                modifier_item.setBackground(QtGui.QColor("lightgreen"))
                modifier_item.setForeground(QtGui.QColor("black"))

            # Add items to the table
            self.unsupported_actions_table_widget.setItem(row_position, 0, action_name_item)
            self.unsupported_actions_table_widget.setItem(row_position, 1, button_item)
            self.unsupported_actions_table_widget.setItem(row_position, 2, modifier_item)
            self.unsupported_actions_table_widget.setItem(row_position, 3, side_item)

        # Adjust column widths
        self.unsupported_actions_table_widget.resizeColumnsToContents()
        self._update_unsupported_actions_label()

    def _update_unsupported_actions_label(self) -> None:
        count = len(self.unsupported_actions)
        if count:
            self.unsupported_actions_label.setText(f"Unsupported Actions ({count})")
            self.unsupported_actions_label.setStyleSheet("color: #cc3300; font-weight: bold;")
        else:
            self.unsupported_actions_label.setText("Unsupported Actions (none)")
            self.unsupported_actions_label.setStyleSheet("color: #666666;")

    def update_validation_status_indicator(self, report: Optional[ValidationReport]) -> None:
        self.binding_validation_report = report

        if report is None:
            self.validation_status_label.setText("Binding status: Not evaluated")
            self.validation_status_label.setStyleSheet("color: #666666;")
            return

        error_count = sum(1 for issue in report.issues if issue.level.lower() == "error")
        warning_count = sum(
            1 for issue in report.issues if issue.level.lower() in {"warn", "warning"}
        )

        if error_count:
            self.validation_status_label.setText(f"Binding status: {error_count} error(s)")
            self.validation_status_label.setStyleSheet("color: #cc3300; font-weight: bold;")
        elif warning_count:
            self.validation_status_label.setText(f"Binding status: {warning_count} warning(s)")
            self.validation_status_label.setStyleSheet("color: #cc7a00; font-weight: bold;")
        else:
            self.validation_status_label.setText("Binding status: OK")
            self.validation_status_label.setStyleSheet("color: #2e7d32; font-weight: bold;")

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
        self.update_validation_status_indicator(None)

    def process_action_map(self, actionmap: ActionMap) -> None:
        for action in actionmap.action:
            for rebind in action.rebind:
                self.process_rebind(action, rebind)

    def unbind_action(self, action_name: str) -> None:
        """Remove an action from all joystick mappings."""
        joy_actions_copy = self.left_joystick_config.configured_actions.copy()
        for joy_action in joy_actions_copy.values():
            if action_name == joy_action.name:
                self.left_joystick_config.unbind_action(action_name)
        joy_actions_copy = self.right_joystick_config.configured_actions.copy()
        for joy_action in joy_actions_copy.values():
            if action_name == joy_action.name:
                self.right_joystick_config.unbind_action(action_name)

    def process_rebind(self, action: configmap.Action, rebind: Rebind) -> None:
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
            side = self.joystick_sides.get(js_number)
            if side is None:
                logger.warning("Joystick instance %s is not mapped to a side", js_number)
                self._record_unsupported_action(action.name, js_button, modifier, None)
                return
            try:
                default_action_conf: List[GameAction] = all_default_actions[action.name]
            except KeyError:
                logger.warning(f"Action {action.name} not found in default actions.")
                self._record_unsupported_action(action.name, js_button, modifier, side)
                return
            for game_action in default_action_conf:
                # hold: bool = game_action.activation_mode == "delayed_press"
                hold = game_action.on_hold == "1"
                main_category: str = game_action.main_category
                sub_category: str = game_action.sub_category
                multitap: bool = rebind.multitap is not None
                button = joystick_buttons.get(js_button)
                if button is None:
                    if "slider" in js_button.lower():
                        self._record_unsupported_action(action.name, js_button, modifier, side)
                        continue
                    logger.warning(f"Button {js_button} not found in joystick_buttons.")
                    self._record_unsupported_action(action.name, js_button, modifier, side)
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
                # an action can only be bound to one button per device, but for joysticks, we want to avoid multiple bindings
                self.unbind_action(action.name)

                if side == "left":
                    self.left_joystick_config.set_mapping(joy_action)
                else:
                    self.right_joystick_config.set_mapping(joy_action)

        except Exception as e:
            logger.exception(f"Error processing rebind: {e}")

    def _record_unsupported_action(
        self,
        action_name: str,
        button: str,
        modifier: bool,
        side: Optional[str],
    ) -> None:
        entry: Dict[str, Any] = {
            "action_name": action_name,
            "button": button,
            "modifier": modifier,
            "side": side or "unknown",
        }
        if entry not in self.unsupported_actions:
            self.unsupported_actions.append(entry)

    def apply_default_bindings(self) -> None:
        """
        Reapply default binds for actions not set elsewhere.
        """
        # Collect all configured action names
        configured_action_names: set[str] = set()
        for configured_action in self.left_joystick_config.configured_actions.values():
            configured_action_names.add(configured_action.name)
        for configured_action in self.right_joystick_config.configured_actions.values():
            configured_action_names.add(configured_action.name)

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
            for game_action in action_game_map.action:
                if game_action.name in configured_action_names:
                    continue
                if game_action.joystick is None:
                    continue
                raw_button: Optional[str]
                if isinstance(game_action.joystick, str):
                    hold = game_action.activation_mode == "delayed_press"
                    raw_button = game_action.joystick
                else:
                    joystick_activation = cast(DeviceActivation, game_action.joystick)
                    raw_button = joystick_activation.input
                    hold = joystick_activation.activationmode == "delayed_press"
                js_button = (raw_button or "").strip()
                if not js_button:
                    continue
                modifier = "+" in js_button
                if modifier:
                    js_button = js_button.split("+")[-1]
                js_button = js_button.strip()
                if not js_button:
                    continue
                if "slider" in js_button.lower():
                    self._record_unsupported_action(
                        game_action.name,
                        js_button,
                        modifier,
                        default_joystick.side,
                    )
                    continue
                button = joystick_buttons.get(js_button)
                if button is None:
                    self._record_unsupported_action(
                        game_action.name,
                        js_button,
                        modifier,
                        default_joystick.side,
                    )
                    continue
                joy_action = JoyAction(
                    name=game_action.name,
                    input=js_button,
                    multitap=False,
                    hold=hold,
                    category=main_cat or "",
                    sub_category=sub_cat or "",
                    modifier=modifier,
                    button=button,
                )

                default_joystick.set_mapping(joy_action)

    def populate_control_maps_combo_box(self) -> None:
        self.control_maps_combo_box.clear()
        for control_map in self.exported_control_maps:
            self.control_maps_combo_box.addItem(Path(control_map).name)

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
        self.refresh_action_panel()

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
            lambda _, btn=button, button_label=label: self.show_action_panel(btn, button_label)
        )
        button.show()
        self.button_refs[label] = button

    def show_action_panel(self, button: QPushButton, label: str) -> None:
        """
        Display the action panel with all mappings for the selected button.
        """
        self.apply_button_style(button, action=self.has_action(label), selected=True)

        if self.previous_selected_button and self.previous_selected_button != button:
            if self.selected_button_label:
                self.update_button_label(self.selected_button_label)
                self.apply_button_style(
                    self.previous_selected_button,
                    action=self.has_action(self.selected_button_label),
                    selected=False,
                )

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
                modifier_item.setBackground(QtGui.QColor("lightgreen"))
            if joy_action.multitap:
                multitap_item.setBackground(QtGui.QColor("lightblue"))
            if joy_action.hold:
                hold_item.setBackground(QtGui.QColor("lightcoral"))

            # Store the key in the first item's data
            action_name_item.setData(Qt.ItemDataRole.UserRole, key)

            # Add items to the table
            self.actions_table_widget.setItem(row_position, 0, action_name_item)
            self.actions_table_widget.setItem(row_position, 1, modifier_item)
            self.actions_table_widget.setItem(row_position, 2, multitap_item)
            self.actions_table_widget.setItem(row_position, 3, hold_item)

        # Adjust column widths
        self.actions_table_widget.resizeColumnsToContents()

    def refresh_action_panel(self) -> None:
        """Synchronise the action panel with the currently selected button/state."""
        if not self.selected_button_label:
            self.actions_table_widget.setRowCount(0)
            self.selected_button_label_widget.setText("Selected Button: None")
            return

        button = self.button_refs.get(self.selected_button_label)
        if button is None:
            self.actions_table_widget.setRowCount(0)
            self.selected_button_label_widget.setText("Selected Button: None")
            self.selected_button_label = None
            self.previous_selected_button = None
            return

        self.show_action_panel(button, self.selected_button_label)

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
            if not selected_action_name:
                return
            action = all_default_actions.get(selected_action_name)
            if action:
                action_info = action[0]
                hold: bool = self.hold_enabled
                multitap: bool = self.multitap_enabled
                modifier: bool = self.modifier_enabled
                joystick_button = joystick_buttons[self.selected_button_label]
                binding_input = self.build_binding_input(
                    joystick_button,
                    self.current_joystick,
                    modifier,
                )
                joy_action = JoyAction(
                    name=selected_action_name,
                    input=binding_input,
                    multitap=multitap,
                    hold=hold,
                    category=action_info.main_category or "",
                    sub_category=action_info.sub_category or "",
                    modifier=modifier,
                    button=joystick_button,
                )
                self.unbind_action(selected_action_name)
                self.current_config.set_mapping(joy_action)
                self.update_button_label(self.selected_button_label)
                self.show_action_panel(
                    self.button_refs[self.selected_button_label], self.selected_button_label
                )  # Refresh the panel
                self.remove_unsupported_entry(selected_action_name, self.current_joystick)
                self.update_unsupported_actions_table()
                self.update_control_map()
            else:
                logger.warning(f"Action {selected_action_name} not found.")

    def add_action_to_control_map(
        self,
        control_map: ExportedActionMapsFile,
        joy_action: JoyAction,
    ) -> None:
        target_actionmap = next(
            (
                actionmap
                for actionmap in control_map.actionmap
                if actionmap.name == joy_action.actionmap_section
            ),
            None,
        )
        if target_actionmap is None:
            logger.warning(
                "Action map %s not found for action %s",
                joy_action.actionmap_section,
                joy_action.name,
            )
            return

        existing_action = next(
            (a for a in target_actionmap.action if a.name == joy_action.name), None
        )
        rebind_payload: Dict[str, Any] = {"@input": joy_action.input}
        if joy_action.multitap:
            rebind_payload["@multiTap"] = 2
        new_rebind = Rebind.model_validate(rebind_payload)

        if existing_action:
            prefix = joy_action.input.split("_")[0]
            existing_action.rebind = [
                rb for rb in existing_action.rebind if not rb.input.startswith(prefix)
            ]
            existing_action.rebind.append(new_rebind)
        else:
            target_actionmap.action.append(
                configmap.Action.model_validate({"@name": joy_action.name, "rebind": [new_rebind]})
            )

    def update_control_map(self) -> None:
        if self.control_map_template is None:
            logger.warning("Control map template is not initialised; skipping export update.")
            return

        export_map = copy.deepcopy(self.control_map_template)
        joystick_instances = {
            side: self.get_instance_number_for_side(side) for side in ("left", "right")
        }
        self.clear_joystick_rebinds(
            export_map,
            {instance for instance in joystick_instances.values() if instance is not None},
        )

        desired_profile = self.build_control_profile_snapshot()
        plan = self.binding_planner.plan_from_profile(desired_profile)
        report = self.binding_planner.validate_plan(plan)
        self._log_binding_validation_report(report)

        for binding in plan.to_remove:
            self.remove_binding_from_control_map(export_map, binding)

        for binding in plan.to_add:
            joy_action = self._binding_to_joy_action(binding)
            if joy_action is None:
                continue
            self.add_action_to_control_map(export_map, joy_action)

        self.control_map = export_map
        unparse(export_map)

        self.update_validation_status_indicator(report)

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
                key_item = self.actions_table_widget.item(
                    row, 0
                )  # Key is stored in the first column
                if key_item:
                    key = key_item.data(Qt.ItemDataRole.UserRole)
                    self.current_config.remove_mapping_by_key(key)
            # Remove the rows in reverse order to prevent shifting issues
            for row in reversed(range(selected_range.topRow(), selected_range.bottomRow() + 1)):
                self.actions_table_widget.removeRow(row)
        assert self.selected_button_label
        self.update_button_label(self.selected_button_label)
        self.update_unsupported_actions_table()
        self.update_control_map()

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
            button.setText("\n".join(action.name for action in actions_dict.values()))
        else:
            button.setText(label)
        if self.selected_button_label == label:
            self.apply_button_style(button, action=has_action, selected=True)
        else:
            self.apply_button_style(button, action=has_action)

    def apply_button_style(self, button: QPushButton, action: bool, selected: bool = False) -> None:
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
            QMessageBox.information(self, "Success", "Configuration saved successfully.")
        except Exception as e:
            logger.exception("Failed to save configuration")
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {e}")

    def load_config(self) -> None:
        try:
            if Path(self.CONFIG_FILE).exists():
                with open(self.CONFIG_FILE, "r") as f:
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

    def build_control_profile_snapshot(self) -> ControlProfile:
        left_set = BindingSet(side="left")
        for binding in self._bindings_from_config(self.left_joystick_config):
            left_set.add(binding)

        right_set = BindingSet(side="right")
        for binding in self._bindings_from_config(self.right_joystick_config):
            right_set.add(binding)

        return ControlProfile(
            profile_name="UI Profile",
            left=left_set,
            right=right_set,
            metadata={"install_type": self.install_type},
        )

    def _bindings_from_config(self, config: JoystickConfig) -> List[Binding]:
        bindings: List[Binding] = []
        for joy_action in config.configured_actions.values():
            bindings.append(self._joy_action_to_binding(joy_action, config.side))
        return bindings

    def _joy_action_to_binding(self, joy_action: JoyAction, side: str) -> Binding:
        device_uid = self._resolve_device_uid_for_side(side)
        if device_uid is None:
            device_uid = self._parse_device_uid_from_input(joy_action.input)
        if device_uid is None:
            fallback_instance = (
                self.config.joystick_instance_left
                if side == "left"
                else self.config.joystick_instance_right
            )
            device_uid = f"js{fallback_instance}"

        slot_id = joy_action.button.sc_config_name
        action_identifier = ActionIdentifier(
            name=joy_action.name,
            main_category=joy_action.category or "",
            sub_category=joy_action.sub_category or "",
        )

        slot = InputSlot(device_uid=device_uid, side=side, slot_id=slot_id)

        return Binding(
            action=action_identifier,
            slot=slot,
            modifier=joy_action.modifier,
            hold=joy_action.hold,
            multitap=joy_action.multitap,
            tags={joy_action.button.name, slot_id},
        )

    def _binding_to_joy_action(self, binding: Binding) -> Optional[JoyAction]:
        button = self._get_button_for_binding(binding)
        if button is None:
            logger.warning("No joystick button metadata found for binding %s", binding.key)
            return None

        input_value = self._build_input_from_binding(binding)

        return JoyAction(
            name=binding.action.name,
            input=input_value,
            category=binding.action.main_category,
            sub_category=binding.action.sub_category,
            modifier=binding.modifier,
            hold=binding.hold,
            multitap=binding.multitap,
            button=button,
        )

    def _build_input_from_binding(self, binding: Binding) -> str:
        device_uid = self._resolve_device_uid_for_side(binding.slot.side)
        if device_uid is None:
            device_uid = binding.slot.device_uid
        if not device_uid:
            fallback_instance = (
                self.config.joystick_instance_left
                if binding.slot.side == "left"
                else self.config.joystick_instance_right
            )
            device_uid = f"js{fallback_instance}"

        base = f"{device_uid}_{binding.slot.slot_id}"
        if binding.modifier:
            modifier_prefix = f"{device_uid}_{self.config.modifier_key}"
            return f"{modifier_prefix}+{binding.slot.slot_id}"
        return base

    def _get_button_for_binding(self, binding: Binding) -> Optional[JoyStickButton]:
        button = self.joystick_buttons_by_slot.get(binding.slot.slot_id)
        if button is None and binding.tags:
            for tag in binding.tags:
                candidate = joystick_buttons.get(tag)
                if candidate is not None:
                    button = candidate
                    break
        if button is None:
            return None
        return button.model_copy()

    def _resolve_device_uid_for_side(self, side: str) -> Optional[str]:
        instance = self.get_instance_number_for_side(side)
        if instance is None:
            return None
        return f"js{instance}"

    @staticmethod
    def _parse_device_uid_from_input(binding_input: str) -> Optional[str]:
        if not binding_input:
            return None
        prefix = binding_input.split("_", maxsplit=1)[0]
        if prefix.startswith("js"):
            return prefix
        return None

    def _log_binding_validation_report(self, report: ValidationReport) -> None:
        if not report.issues:
            return
        for issue in report.issues:
            action_name = issue.action.name if issue.action else "(action unknown)"
            slot_id = issue.slot.slot_id if issue.slot else "(slot unknown)"
            message = f"{issue.level.upper()} for {action_name} on {slot_id}: {issue.message}"
            if issue.level.lower() == "error":
                logger.error(message)
            else:
                logger.info(message)

    def remove_binding_from_control_map(
        self,
        control_map: ExportedActionMapsFile,
        binding: Binding,
    ) -> None:
        expected_input = self._build_input_from_binding(binding)

        for actionmap in control_map.actionmap:
            for action in list(actionmap.action):
                if action.name != binding.action.name:
                    continue

                original_count = len(action.rebind)
                action.rebind = [
                    rebind for rebind in action.rebind if rebind.input != expected_input
                ]

                if not action.rebind:
                    actionmap.action.remove(action)
                elif len(action.rebind) != original_count:
                    logger.debug(
                        "Removed rebind %s for action %s", expected_input, binding.action.name
                    )

    def build_binding_input(self, button: JoyStickButton, side: str, modifier: bool) -> str:
        instance = self.get_instance_number_for_side(side)
        if instance is None:
            instance = (
                self.config.joystick_instance_left
                if side == "left"
                else self.config.joystick_instance_right
            )
        base = f"js{instance}_{button.sc_config_name}"
        if modifier:
            modifier_prefix = f"js{instance}_{self.config.modifier_key}"
            return f"{modifier_prefix}+{button.sc_config_name}"
        return base

    def get_instance_number_for_side(self, side: str) -> Optional[int]:
        for instance, mapped_side in self.joystick_sides.items():
            if mapped_side == side:
                return instance
        return None

    def remove_unsupported_entry(self, action_name: str, side: str) -> None:
        self.unsupported_actions = [
            entry
            for entry in self.unsupported_actions
            if not (entry["action_name"] == action_name and entry["side"] == side)
        ]

    def clear_joystick_rebinds(
        self,
        control_map: ExportedActionMapsFile,
        instances: set[int],
    ) -> None:
        if not instances:
            return
        prefixes = tuple(f"js{instance}_" for instance in instances)
        for actionmap in control_map.actionmap:
            for action in actionmap.action:
                if not action.rebind:
                    continue
                action.rebind = [
                    rebind for rebind in action.rebind if not rebind.input.startswith(prefixes)
                ]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ControlMapperApp()
    window.show()
    sys.exit(app.exec())
