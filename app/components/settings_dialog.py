from __future__ import annotations

from PyQt6.QtWidgets import QPushButton, QComboBox, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QSpinBox, QDialogButtonBox

from app.components.joystick_selector_dialog import JoystickSelectorDialog
from app.config import Config
from app.services import JoystickMonitorService


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: Config,
        parent: QWidget | None = None,
        joystick_monitor: JoystickMonitorService | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        monitor = joystick_monitor if joystick_monitor is not None else JoystickMonitorService()
        self.joystick_monitor: JoystickMonitorService = monitor
        self.selector_dialog: JoystickSelectorDialog | None = None
        self.selector_saved = False
        self.init_ui()

    def init_ui(self) -> None:
        self.setWindowTitle("Settings")
        self.layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        # Installation Path
        self.installation_path_line_edit = QLineEdit(self.config.installation_path)
        self.browse_button = QPushButton("Browse")
        browse_layout = QHBoxLayout()
        browse_layout.addWidget(self.installation_path_line_edit)
        browse_layout.addWidget(self.browse_button)
        form_layout.addRow("Installation Path:", browse_layout)
        self.browse_button.clicked.connect(self.browse_installation_path)

        # Install Type
        self.install_type_combo_box = QComboBox()
        self.install_type_combo_box.addItems(["LIVE", "PTU", "EPTU"])
        index = self.install_type_combo_box.findText(self.config.install_type)
        if index >= 0:
            self.install_type_combo_box.setCurrentIndex(index)
        form_layout.addRow("Install Type:", self.install_type_combo_box)

        # Joystick Left Name Filter
        self.joystick_left_name_filter_line_edit = QLineEdit(self.config.joystick_left_name_filter)
        form_layout.addRow("Joystick Left Name Filter:", self.joystick_left_name_filter_line_edit)

        # Joystick Right Name Filter
        self.joystick_right_name_filter_line_edit = QLineEdit(
            self.config.joystick_right_name_filter
        )
        form_layout.addRow("Joystick Right Name Filter:", self.joystick_right_name_filter_line_edit)

        # Joystick Type Left
        self.joystick_type_left_line_edit = QLineEdit(self.config.joystick_type_left)
        form_layout.addRow("Joystick Type Left:", self.joystick_type_left_line_edit)

        # Joystick Type Right
        self.joystick_type_right_line_edit = QLineEdit(self.config.joystick_type_right)
        form_layout.addRow("Joystick Type Right:", self.joystick_type_right_line_edit)

        # Joystick Instance Left
        self.joystick_instance_left_spin_box = QSpinBox()
        self.joystick_instance_left_spin_box.setValue(self.config.joystick_instance_left)
        form_layout.addRow("Joystick Instance Left:", self.joystick_instance_left_spin_box)

        # Joystick Instance Right
        self.joystick_instance_right_spin_box = QSpinBox()
        self.joystick_instance_right_spin_box.setValue(self.config.joystick_instance_right)
        form_layout.addRow("Joystick Instance Right:", self.joystick_instance_right_spin_box)

        self.joystick_side_identifier_left_line_edit = QLineEdit(
            self.config.joystick_side_identifier_left
        )
        form_layout.addRow(
            "Joystick Side Identifier Left:", self.joystick_side_identifier_left_line_edit
        )

        self.joystick_side_identifier_right_line_edit = QLineEdit(
            self.config.joystick_side_identifier_right
        )
        form_layout.addRow(
            "Joystick Side Identifier Right:", self.joystick_side_identifier_right_line_edit
        )

        # Modifier Key
        self.modifier_key_line_edit = QLineEdit(self.config.modifier_key)
        form_layout.addRow("Modifier Key:", self.modifier_key_line_edit)

        self.layout.addLayout(form_layout)

        self.joystick_selector_button = QPushButton("Joystick Selector")
        self.joystick_selector_button.clicked.connect(self.open_joystick_selector)
        self.layout.addWidget(self.joystick_selector_button)

        # OK and Cancel buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)

    def browse_installation_path(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Select Installation Directory", self.installation_path_line_edit.text()
        )
        if directory:
            self.installation_path_line_edit.setText(directory)

    def open_joystick_selector(self) -> None:
        self.selector_dialog = JoystickSelectorDialog(self.config, self.joystick_monitor, self)
        self.selector_dialog.finished.connect(self._handle_selector_dialog_finished)
        self.selector_dialog.open()

    def _handle_selector_dialog_finished(self, result: int) -> None:
        if result == int(QDialog.DialogCode.Accepted):
            self.selector_saved = True
            self.reload_fields_from_config()

    def reload_fields_from_config(self) -> None:
        self.joystick_left_name_filter_line_edit.setText(self.config.joystick_left_name_filter)
        self.joystick_right_name_filter_line_edit.setText(self.config.joystick_right_name_filter)
        self.joystick_type_left_line_edit.setText(self.config.joystick_type_left)
        self.joystick_type_right_line_edit.setText(self.config.joystick_type_right)
        self.joystick_instance_left_spin_box.setValue(self.config.joystick_instance_left)
        self.joystick_instance_right_spin_box.setValue(self.config.joystick_instance_right)

    def accept(self) -> None:
        # Update the config with new values
        self.config.installation_path = self.installation_path_line_edit.text()
        self.config.install_type = self.install_type_combo_box.currentText()
        self.config.joystick_left_name_filter = self.joystick_left_name_filter_line_edit.text()
        self.config.joystick_right_name_filter = self.joystick_right_name_filter_line_edit.text()
        self.config.joystick_type_left = self.joystick_type_left_line_edit.text()
        self.config.joystick_type_right = self.joystick_type_right_line_edit.text()
        self.config.joystick_instance_left = self.joystick_instance_left_spin_box.value()
        self.config.joystick_instance_right = self.joystick_instance_right_spin_box.value()
        self.config.joystick_side_identifier_left = (
            self.joystick_side_identifier_left_line_edit.text()
        )
        self.config.joystick_side_identifier_right = (
            self.joystick_side_identifier_right_line_edit.text()
        )
        self.config.modifier_key = self.modifier_key_line_edit.text()
        self.config.save()
        super().accept()
