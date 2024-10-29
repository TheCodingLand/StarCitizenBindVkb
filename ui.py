from pathlib import Path
import sys
import json
from typing import Literal, Optional, Dict
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QComboBox, QMessageBox
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QRect, Qt, QEvent, QObject
from PyQt6.QtGui import QKeyEvent


import os
from actions import get_all_defined_game_actions, get_all_subcategories_actions
from configmap import ExportedActionMapsFile, Rebind, get_action_maps_object
from globals import get_installation
from joystick import Joystick, get_joystick_buttons
current_path= Path(__file__).parent
left_image_path = current_path / "images/vkb_left.png"
right_image_path = current_path / "images/vkb_right.png"

# Updated list of known Star Citizen actions (example)
actions = {
    "Select Action": {
        "Cockpit": [
            "Launch Missile", "Fire Weapon", "Increase Limiter Speed", "Decrease Limiter Speed"
        ],
        "Camera": [
            "Camera UP", "Camera Down", "Camera Left", "Camera Right"
        ]
    }
}

actions = get_all_subcategories_actions()


width: int = 155
height: int = 35


class ControlMapperApp(QMainWindow):
    def apply_button_style(self, button: QPushButton, action: bool) -> None:
        """Apply the style to the button based on whether an action is set or not."""
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
    CONFIG_FILE = "config.json"

    def __init__(self) -> None:
        super().__init__()
        
        # Load background image and set up the UI
        self.setWindowTitle("VKB Joystick Mapper")
        self.setGeometry(100, 100, 1950, 938)  # Match to image size
        self.background_label: QLabel = QLabel(self)
        self.background_label.setGeometry(0, 0, 1950, 938)

        # Store joystick configurations
        self.left_joystick_config: Joystick = Joystick(side="left", buttons=get_joystick_buttons())
        self.right_joystick_config: Joystick = Joystick(side="right", buttons=get_joystick_buttons())
        self.current_config: Joystick = self.left_joystick_config  # Start with left joystick config
        self.current_joystick: str = "left"
        
        # Modifier state
        self.modifier_enabled: bool = False
        
        # Create a dictionary to hold references to buttons
        self.button_refs: Dict[str, QPushButton] = {}
        
        # Create the combo box for selecting actions
        self.action_combo_box: QComboBox = QComboBox(self)
        self.action_combo_box.setPlaceholderText("--Select Action--")
        self.populate_action_combo_box()
        self.action_combo_box.setVisible(False)
        self.action_combo_box.setMinimumWidth(300)  # Make the drop-down wider
        self.action_combo_box.setMaxVisibleItems(10)  # Set max visible items in the drop-down
        self.action_combo_box.activated.connect(self.select_action)
        self.action_combo_box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.action_combo_box.installEventFilter(self)  # Install an event filter to handle key and focus events

        # Button to switch between left and right joysticks
        self.switch_button: QPushButton = QPushButton("Switch to Right Joystick", self)
        self.switch_button.setGeometry(10, 10, 200, 40)
        self.switch_button.clicked.connect(self.toggle_joystick)

        # Button to toggle the modifier
        self.modifier_button: QPushButton = QPushButton("Enable Modifier", self)
        self.modifier_button.setGeometry(220, 10, 200, 40)
        self.modifier_button.clicked.connect(self.toggle_modifier)

        # Button to save the configuration
        self.save_button: QPushButton = QPushButton("Save Config", self)
        self.save_button.setGeometry(430, 10, 200, 40)
        self.save_button.clicked.connect(self.save_config)

        # Button to load the configuration
        self.load_button: QPushButton = QPushButton("Load Config", self)
        self.load_button.setGeometry(640, 10, 200, 40)
        self.load_button.clicked.connect(self.load_config)

        # Load the initial background image and create buttons for the left joystick
        self.load_background(str(left_image_path))
        self.create_joystick_buttons()

        self.install =  get_installation("LIVE")
        self.exported_control_maps = self.install.exported_control_maps

        # select box for the control maps
        self.control_maps_combo_box: QComboBox = QComboBox(self)
        self.control_maps_combo_box.setPlaceholderText("--Select Control Map--")
        self.control_maps_combo_box.setVisible(True)
        self.control_maps_combo_box.setGeometry(850, 10, 200, 40)
        self.control_maps_combo_box.setMinimumWidth(400)  # Make the drop-down wider
        self.control_maps_combo_box.setMaxVisibleItems(10)  # Set max visible items in the drop-down
        self.control_maps_combo_box.activated.connect(self.select_control_map)
        self.control_maps_combo_box.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.control_maps_combo_box.installEventFilter(self)  # Install an event filter to handle key and focus events
        self.populate_control_maps_combo_box()

    def select_control_map(self, index: int) -> None:
        control_map_file = self.exported_control_maps[index]
        # self.control_map = get_action_maps_object(control_map_file)
        self.control_map = get_action_maps_object(f"{current_path}/data/layout_BK_DualVKB_3-22_exported.xml")

        self.joystick_sides= self.get_joystick_sides(self.control_map)
        for button in self.left_joystick_config.buttons.values():
            button.actions = []
        for button in self.right_joystick_config.buttons.values():
            button.actions = []
        
        for actionmap in self.control_map.actionmap:
            modifier=False
            for action in actionmap.action:
                print(action)
                #print(action.name)
                if isinstance(action.rebinding, Rebind):
                    print(action.rebinding.input)
                    if action.rebinding.input.startswith("js"):
                        joy_command_input_string = action.rebinding.input
                        
                        if "+" in action.rebinding.input:
                            modifier = True
                            joy_modifier, js_button = action.rebinding.input.split("+")
                            joy_command_input_string.replace("js", "")
                            js_str = split_str_action[0]
                        else:
                            split_str_action = joy_command_input_string.split("_")
                            if len(split_str_action) == 2:
                                js_str, js_button = split_str_action
                            elif len(split_str_action) >2:
                                js_str = split_str_action[0]
                                js_button = "_".join(split_str_action[1:])
                            else:
                                print(f"error: splitting joystick input string returned unexpected segments - {action.rebinding.input}")

                        if js_button == " " or js_button == "": # we don't want to map empty buttons
                            continue
                        try:
                            js_number = js_str[2:]
                        except:
                            print(f"error: parsing joystick number from {js_str} - {action.rebinding.input}")
                            continue
                        side = self.joystick_sides[int(js_number)]
                        if side == "left":
                            self.left_joystick_config.set_mapping(js_button, action.name, modifier=modifier)
                        else:
                            self.right_joystick_config.set_mapping(js_button, action.name, modifier=modifier)
        
        default_actions = get_all_defined_game_actions()
        js1 = self.joystick_sides[1]
        
        if js1 == "left":
            default_joystick= self.left_joystick_config
        else:
            default_joystick= self.right_joystick_config
    

        for action in default_actions.values():

            if action.joystick and action.joystick not in [' ', '',None]:
                
                for button in default_joystick.buttons.values():
 
                    if len(button.actions) == 0 and button.name == action.joystick and  action.main_category in [ "@ui_CCSpaceFlight", '@ui_CCVehicle']:
                        default_joystick.set_mapping(button.name, action.name)
                      
        self.update_joystick_buttons()

                    # need to know if js1 is left or right, then we can map the action to the button

    def get_joystick_sides(self, control_map: ExportedActionMapsFile) -> Dict[int, str]:
        instance_options = {} # extra joystick options, we will later display it in the UI
        instance_number_mapping = {}
        for option in control_map.options:
            if option.product is None:
                continue
            if 'VKBsim Gladiator EVO' in option.product and "L" in option.product.split("{")[0]:
                instance_number_mapping[option.instance] = "left"
                instance_options[option.instance] = option.model_extra
            if 'VKBsim Gladiator EVO' in option.product and "R" in option.product.split("{")[0]:
                instance_number_mapping[option.instance] = "right"
                instance_options[option.instance] = option.model_extra
        return instance_number_mapping
    
        
    def populate_control_maps_combo_box(self) -> None:
        """Populate the control maps combo box with the available control maps."""
        self.control_maps_combo_box.clear()
        for control_map in self.exported_control_maps:
            self.control_maps_combo_box.addItem(control_map.split(os.sep)[-1])
        # set the default text to be something other than the first item


    def populate_action_combo_box(self) -> None:
        """Populate the action combo box with hierarchical action categories."""
        self.action_combo_box.setPlaceholderText("--Select Action--")
        self.action_combo_box.clear()
        
        self.action_combo_box.addItem("Clear Action")
        for category, sub_actions in actions.items():
            self.action_combo_box.addItem(category)
        # set the default text to be something other than the first item
        
    def show_action_selector(self, button: QPushButton, label: str) -> None:
        """Show a combo box near the selected button for action selection."""
        self.action_combo_box.move(button.x() + button.width() + 10, button.y())
        self.action_combo_box.setVisible(True)
        self.action_combo_box.raise_()  # Bring the combo box to the front
        self.action_combo_box.setProperty("current_label", label)
        self.action_combo_box.setFocus()
        

    def select_action(self, index: int) -> None:
        """Handle the selection of an action from the combo box."""
        selected_item = self.action_combo_box.currentText().strip()
        label: str = self.action_combo_box.property("current_label")

        # If a category is selected, populate with sub-actions and immediately drop down
        if selected_item in actions:
            self.action_combo_box.clear()
            self.action_combo_box.addItem("Back")
            for action in actions[selected_item]:
                self.action_combo_box.addItem(action)
            self.action_combo_box.showPopup()  # Automatically drop down the menu
        elif selected_item == "Back":
            # Re-populate with top-level categories and immediately drop down
            
            self.populate_action_combo_box()
            self.action_combo_box.showPopup()
        elif label and selected_item == "Clear Action":
            self.current_config.clear_mapping(label, modifier=self.modifier_enabled)
            self.button_refs[label].setText(label)
            self.set_button_style(label)
            self.action_combo_box.setVisible(False)
            self.populate_action_combo_box()
        elif label:
            # Set the action for the button
            self.current_config.set_mapping(label, selected_item, modifier=self.modifier_enabled)
            mapping = self.current_config.get_mapping(label, modifier=self.modifier_enabled)
            self.button_refs[label].setText(f"{mapping}")
            self.action_combo_box.setVisible(False)
            self.set_button_style(label)
            self.action_combo_box.clear()
            self.populate_action_combo_box()

    def set_button_style(self, label: str) -> None:
        """Set the style of the button based on the presence of an action mapping."""
        actions: Optional[str] = self.current_config.get_mapping(label, modifier=self.modifier_enabled)
        button: QPushButton = self.button_refs[label]
        self.apply_button_style(button, action=len(actions)>0)
        button.repaint()


    def eventFilter(self, source: QObject, event: QKeyEvent) -> bool:
        """Event filter to handle escape key and click-away events for the combo box."""
        if source == self.action_combo_box:
            if event.type() == QEvent.Type.KeyPress:
                key_event = event  # Cast to QKeyEvent to access key()
                if key_event.key() == Qt.Key.Key_Escape:
                    self.action_combo_box.setVisible(False)
                    return True
        return super().eventFilter(source, event)

    def toggle_joystick(self) -> None:
        """Toggle between the left and right joystick layouts."""
        # Save current mappings before switching
        self.save_current_mappings()

        if self.current_joystick == "left":
            self.current_joystick = "right"
            self.current_config = self.right_joystick_config
            self.switch_button.setText("Switch to Left Joystick")
            self.load_background(str(right_image_path))  # Replace with the path to the right joystick image
        else:
            self.current_joystick = "left"
            self.current_config = self.left_joystick_config
            self.switch_button.setText("Switch to Right Joystick")
            self.load_background(str(left_image_path))  # Replace with the path to the left joystick image
        
        # Update joystick buttons to reflect the current configuration
        self.update_joystick_buttons()

    def toggle_modifier(self) -> None:
        """Toggle the modifier state and update the button mappings."""
        self.modifier_enabled = not self.modifier_enabled
        self.modifier_button.setText("Disable Modifier" if self.modifier_enabled else "Enable Modifier")
        
        
            
        self.update_joystick_buttons()

    def save_current_mappings(self) -> None:
        """Save the current button mappings to the active config."""
        for label, button in self.button_refs.items():
            action_text = button.text()
            if ": " in action_text:
                label, action = action_text.split(": ", 1)
                self.current_config.set_mapping(label, action, modifier=self.modifier_enabled)

    def load_background(self, image_path: str) -> None:
        """Load the background image."""
        pixmap: QPixmap = QPixmap(image_path)
        self.background_label.setPixmap(pixmap)
        self.background_label.setGeometry(0, 0, pixmap.width(), pixmap.height())

    def create_joystick_buttons(self) -> None:
        """Create buttons based on the current joystick state."""
        

        for button in self.current_config.buttons.values():
            if not button.visible:
                continue
            self.create_mappable_button(button.name, QRect(button.coord_x_left[self.current_config.side], button.coord_y_top, width, height))
        


    def update_joystick_buttons(self) -> None:
        """Update button positions and labels based on the current joystick layout."""
        
        for joy_button in self.current_config.buttons.values():
            label: str = joy_button.name
            geometry: QRect = QRect(joy_button.coord_x_left[self.current_config.side], joy_button.coord_y_top, width, height)
            #if self.current_joystick == "right":
            #    geometry = QRect(1420 + 35 + geometry.x() - width, geometry.y(), width, geometry.height())

            button: QPushButton = self.button_refs[label]
            button.setGeometry(geometry)

            # Update button label based on the current config mapping
            action: Optional[str] = self.current_config.get_mapping(label, modifier=self.modifier_enabled)
            if action:
                button.setText(f"{action}")
            else:
                button.setText(label)
            self.set_button_style(label)

    def create_mappable_button(self, label: str, geometry: QRect) -> None:
        """Create a mappable button with the given label and geometry."""
        button: QPushButton = QPushButton(label, self)
        button.setGeometry(geometry)
        self.apply_button_style(button, action=False)
        button.clicked.connect(lambda: self.show_action_selector(button, label))
        button.show()
        self.button_refs[label] = button

    
    def save_config(self) -> None:
        """Save the current joystick configurations to a config file."""
        self.save_current_mappings()
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump({
                    "left": self.left_joystick_config.model_dump(),
                    "right": self.right_joystick_config.model_dump()
                }, f, indent=4)
            QMessageBox.information(self, "Success", "Configuration saved successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save configuration: {e}")

    def load_config(self) -> None:
        """Load joystick configurations from a config file."""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.left_joystick_config = Joystick.model_validate(data["left"])
                    self.right_joystick_config = Joystick.model_validate(data["right"])
                if self.current_joystick == "left":
                    self.current_config = self.left_joystick_config
                else:
                    self.current_config = self.right_joystick_config
                # Refresh the UI to reflect the loaded configuration
                self.update_joystick_buttons()
                QMessageBox.information(self, "Success", "Configuration loaded successfully.")
            else:
                QMessageBox.warning(self, "Error", "No configuration file found.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load configuration: {e}")

if __name__ == "__main__":
    app: QApplication = QApplication(sys.argv)
    window: ControlMapperApp = ControlMapperApp()
    window.show()
    sys.exit(app.exec())
