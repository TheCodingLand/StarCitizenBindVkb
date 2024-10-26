import sys
import json
from typing import Optional, Dict
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QComboBox, QMessageBox
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QRect, Qt, QEvent, QObject
from PyQt6.QtGui import QKeyEvent
from pydantic import BaseModel, Field
import os

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

VKB_BUTTON_LIST = [
    "Hat Up Left",
    "Hat Up",
    "Hat Up Right",
    "Hat Left",
    "Hat Right",
    "Hat Down Left",
    "Hat Down",
    "Hat Down Right"
]

class ButtonMapping(BaseModel):
    normal: Optional[str] = Field(None, description="Action mapped without modifier")
    modified: Optional[str] = Field(None, description="Action mapped with modifier")

class JoystickConfigModel(BaseModel):
    buttons: Dict[str, ButtonMapping] = Field(default_factory=lambda: {label: ButtonMapping() for label in VKB_BUTTON_LIST})

    def set_mapping(self, label: str, action: str, modifier: bool = False) -> None:
        """Set the action mapping for a specific button."""
        if modifier:
            self.buttons[label].modified = action
        else:
            self.buttons[label].normal = action

    def get_mapping(self, label: str, modifier: bool = False) -> Optional[str]:
        """Get the action mapping for a specific button."""
        return self.buttons[label].modified if modifier else self.buttons[label].normal

    def clear_mappings(self) -> None:
        """Clear all mappings."""
        for mapping in self.buttons.values():
            mapping.normal = None
            mapping.modified = None

    def __repr__(self) -> str:
        return f"JoystickConfigModel(buttons={self.buttons})"

class ControlMapperApp(QMainWindow):
    CONFIG_FILE = "config.json"

    def __init__(self) -> None:
        super().__init__()
        
        # Load background image and set up the UI
        self.setWindowTitle("VKB Joystick Mapper")
        self.setGeometry(100, 100, 1950, 938)  # Match to image size
        self.background_label: QLabel = QLabel(self)
        self.background_label.setGeometry(0, 0, 1950, 938)
        
        # Store joystick configurations
        self.left_joystick_config: JoystickConfigModel = JoystickConfigModel()
        self.right_joystick_config: JoystickConfigModel = JoystickConfigModel()
        self.current_config: JoystickConfigModel = self.left_joystick_config  # Start with left joystick config
        self.current_joystick: str = "left"
        
        # Modifier state
        self.modifier_enabled: bool = False
        
        # Create a dictionary to hold references to buttons
        self.button_refs: Dict[str, QPushButton] = {}
        
        # Create the combo box for selecting actions
        self.action_combo_box: QComboBox = QComboBox(self)
        self.populate_action_combo_box()
        self.action_combo_box.setVisible(False)
        self.action_combo_box.setMinimumWidth(200)  # Make the drop-down wider
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
        self.load_background("vkb_left.png")
        self.create_joystick_buttons()

    def populate_action_combo_box(self) -> None:
        """Populate the action combo box with hierarchical action categories."""
        self.action_combo_box.clear()
        self.action_combo_box.addItem("Select Action")
        for category, sub_actions in actions["Select Action"].items():
            self.action_combo_box.addItem(category)

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
        if selected_item in actions["Select Action"]:
            self.action_combo_box.clear()
            self.action_combo_box.addItem("Back")
            for action in actions["Select Action"][selected_item]:
                self.action_combo_box.addItem(action)
            self.action_combo_box.showPopup()  # Automatically drop down the menu
        elif selected_item == "Back":
            # Re-populate with top-level categories and immediately drop down
            self.populate_action_combo_box()
            self.action_combo_box.showPopup()
        elif label and selected_item != "Select Action":
            # Set the action for the button
            self.current_config.set_mapping(label, selected_item, modifier=self.modifier_enabled)
            self.button_refs[label].setText(f"{selected_item}")
            self.action_combo_box.setVisible(False)

    def eventFilter(self, source: QObject, event: QKeyEvent ) -> bool:
        """Event filter to handle escape key and click-away events for the combo box."""
        if source == self.action_combo_box:
            if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self.action_combo_box.setVisible(False)
                return True
            #elif event.type() == event.Type.F:
            #    self.action_combo_box.setVisible(False)
            #    return True
        return super().eventFilter(source, event)

    def toggle_joystick(self) -> None:
        """Toggle between the left and right joystick layouts."""
        # Save current mappings before switching
        self.save_current_mappings()

        if self.current_joystick == "left":
            self.current_joystick = "right"
            self.current_config = self.right_joystick_config
            self.switch_button.setText("Switch to Left Joystick")
            self.load_background("vkb_right.png")  # Replace with the path to the right joystick image
        else:
            self.current_joystick = "left"
            self.current_config = self.left_joystick_config
            self.switch_button.setText("Switch to Right Joystick")
            self.load_background("vkb_left.png")  # Replace with the path to the left joystick image
        
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
        width: int = 155
        height: int = 35

        col_1_left: int = 71
        col_2_left: int = 265
        col_3_left: int = 453
        row_1_top: int = 52
        row_2_top: int = 52 + height
        row_3_top: int = 52 + height + height

        self.buttons: list[tuple[str, QRect]] = [
            ("Hat Up Left", QRect(col_1_left, row_1_top, width, height)),
            ("Hat Up", QRect(col_2_left, row_1_top, width, height)),
            ("Hat Up Right", QRect(col_3_left, row_1_top, width, height)),
            ("Hat Left", QRect(col_1_left, row_2_top, width, height)),
            ("Hat Right", QRect(col_3_left, row_2_top, width, height)),
            ("Hat Down Left", QRect(col_1_left, row_3_top, width, height)),
            ("Hat Down", QRect(col_2_left, row_3_top, width, height)),
            ("Hat Down Right", QRect(col_3_left, row_3_top, width, height))
        ]

        for label, geometry in self.buttons:
            self.create_mappable_button(label, geometry)

    def update_joystick_buttons(self) -> None:
        """Update button positions and labels based on the current joystick layout."""
        width: int = 155
        for label, geometry in self.buttons:
            if self.current_joystick == "right":
                geometry = QRect(1950 + 35 - geometry.x() - width, geometry.y(), width, geometry.height())
            button: QPushButton = self.button_refs[label]
            button.setGeometry(geometry)

            # Update button label based on the current config mapping
            action: Optional[str] = self.current_config.get_mapping(label, modifier=self.modifier_enabled)
            button.setText(f"{action}" if action else label)
            button.show()

    def create_mappable_button(self, label: str, geometry: QRect) -> None:
        """Create a mappable button with the given label and geometry."""
        button: QPushButton = QPushButton(label, self)
        button.setGeometry(geometry)
        button.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 255);
                color: rgba(0, 0, 0, 255);
                border: 2px solid rgba(255, 255, 255, 0);
            }
            QPushButton:hover {
                background-color: rgba(150, 150, 255, 100);
                color: rgba(255, 255, 255, 255);
                border: 2px solid rgba(255, 255, 255, 180);
            }
        """)
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
                    self.left_joystick_config = JoystickConfigModel.model_validate(data["left"])
                    self.right_joystick_config = JoystickConfigModel.model_validate(data["right"])
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
