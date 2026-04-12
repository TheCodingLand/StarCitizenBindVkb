from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Protocol

from PyQt6.QtCore import QSignalBlocker, QPoint, QSize, Qt
from PyQt6.QtGui import QPixmap

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.components.joystick_activity_overlay import JoystickActivityOverlay
from app.config import Config
from app.globals import APP_PATH
from app.models.joystick_layout_support import slot_positions_for_layout
from app.services import DetectedJoystickDevice, JoystickActivityEvent


PREVIEW_IMAGE_BY_SIDE = {
    "left": APP_PATH / "data" / "images" / "vkb_default_left.png",
    "right": APP_PATH / "data" / "images" / "vkb_default_right.png",
}
DEFAULT_PREVIEW_SIZE = QSize(760, 365)
DEFAULT_PREVIEW_STATUS = "Preview unavailable until a supported device is selected."


class JoystickSelectorWarningSignal(Protocol):
    def connect(self, slot: Callable[[str], object]) -> object:
        ...


class JoystickSelectorActivitySignal(Protocol):
    def connect(self, slot: Callable[[object], object]) -> object:
        ...


class JoystickSelectorMonitor(Protocol):
    activity: JoystickSelectorActivitySignal
    warning: JoystickSelectorWarningSignal

    def refresh_devices(self) -> list[DetectedJoystickDevice]:
        ...


class JoystickSelectorDialog(QDialog):
    def __init__(
        self,
        config: Config,
        joystick_monitor: JoystickSelectorMonitor,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.joystick_monitor = joystick_monitor
        self.detected_devices: list[DetectedJoystickDevice] = []
        self.selected_preview_device: DetectedJoystickDevice | None = None
        self._build_ui()
        self.refresh_devices()

    def _build_ui(self) -> None:
        self.setWindowTitle("Joystick Selector")
        self.resize(1180, 760)

        layout = QVBoxLayout(self)

        content_row = QHBoxLayout()
        layout.addLayout(content_row)

        selector_panel = QVBoxLayout()
        content_row.addLayout(selector_panel, 2)

        preview_panel = QVBoxLayout()
        content_row.addLayout(preview_panel, 3)

        self.device_list_widget = QListWidget(self)
        selector_panel.addWidget(self.device_list_widget)

        selector_form = QFormLayout()
        self.left_selector = QComboBox(self)
        self.right_selector = QComboBox(self)
        selector_form.addRow("Left Joystick:", self.left_selector)
        selector_form.addRow("Right Joystick:", self.right_selector)
        selector_panel.addLayout(selector_form)

        self.preview_surface = QLabel(self)
        self.preview_image_label = self.preview_surface
        self.preview_surface.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self.preview_surface.setMinimumSize(DEFAULT_PREVIEW_SIZE)
        self.preview_surface.setStyleSheet(
            "background-color: #161616; border: 1px solid #4c4c4c; color: #d0d0d0;"
        )
        preview_panel.addWidget(self.preview_surface, alignment=Qt.AlignmentFlag.AlignTop)

        self.preview_overlay = JoystickActivityOverlay({}, parent=self.preview_surface)
        self.preview_overlay.hide()
        self._clear_preview_surface()

        self.preview_status_label = QLabel(DEFAULT_PREVIEW_STATUS, self)
        self.preview_status_label.setWordWrap(True)
        preview_panel.addWidget(self.preview_status_label)

        self.validation_label = QLabel("", self)
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        button_row = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh Devices", self)
        self.save_button = QPushButton("Save Assignments", self)
        button_row.addWidget(self.refresh_button)
        button_row.addStretch()
        button_row.addWidget(self.save_button)
        layout.addLayout(button_row)

        self.left_selector.currentIndexChanged.connect(self._sync_preview_from_selectors)
        self.right_selector.currentIndexChanged.connect(self._sync_preview_from_selectors)
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.save_button.clicked.connect(self.save_assignments)

        self.joystick_monitor.activity.connect(self._handle_preview_activity)
        self.joystick_monitor.warning.connect(self.preview_status_label.setText)

    def refresh_devices(self) -> None:
        current_left_guid = self.left_selector.currentData() if self.left_selector.count() else None
        current_right_guid = self.right_selector.currentData() if self.right_selector.count() else None

        self.detected_devices = list(self.joystick_monitor.refresh_devices())
        self.device_list_widget.clear()

        left_selector_blocker = QSignalBlocker(self.left_selector)
        right_selector_blocker = QSignalBlocker(self.right_selector)
        self.left_selector.clear()
        self.right_selector.clear()
        self.left_selector.addItem("-- Select Left --", None)
        self.right_selector.addItem("-- Select Right --", None)

        for device in self.detected_devices:
            support_badge = "supported" if device.layout_key else "preview unavailable"
            self.device_list_widget.addItem(f"{device.product_name} - {support_badge}")
            self.left_selector.addItem(device.product_name, device.product_guid)
            self.right_selector.addItem(device.product_name, device.product_guid)

        self._restore_selector_value(self.left_selector, current_left_guid)
        self._restore_selector_value(self.right_selector, current_right_guid)

        del left_selector_blocker
        del right_selector_blocker

        self.validation_label.clear()
        self._sync_preview_from_selectors()

    def current_left_device(self) -> DetectedJoystickDevice | None:
        return self._selected_device(self.left_selector.currentData())

    def current_right_device(self) -> DetectedJoystickDevice | None:
        return self._selected_device(self.right_selector.currentData())

    def _selected_device(self, product_guid: str | None) -> DetectedJoystickDevice | None:
        return next(
            (device for device in self.detected_devices if device.product_guid == product_guid),
            None,
        )

    def _sync_preview_from_selectors(self) -> None:
        preview_device: DetectedJoystickDevice | None = None
        if self.sender() is self.left_selector:
            preview_device = self.current_left_device()
        elif self.sender() is self.right_selector:
            preview_device = self.current_right_device()
        if preview_device is None:
            preview_device = self.current_left_device() or self.current_right_device()

        self.set_preview_device(preview_device)

    def set_preview_device(self, device: DetectedJoystickDevice | None) -> None:
        self.selected_preview_device = device
        if device is None or device.layout_key is None:
            self.preview_status_label.setText(DEFAULT_PREVIEW_STATUS)
            self.preview_overlay.set_slot_positions({})
            self.preview_overlay.hide()
            self._clear_preview_surface()
            return

        preview_side = self._preview_side_for_device(device)
        preview_path = PREVIEW_IMAGE_BY_SIDE[preview_side]
        pixmap = QPixmap(str(preview_path))
        if pixmap.isNull():
            self.preview_status_label.setText("Preview unavailable for this layout.")
            self.preview_overlay.set_slot_positions({})
            self.preview_overlay.hide()
            self._clear_preview_surface()
            return

        scaled_pixmap = pixmap.scaled(
            DEFAULT_PREVIEW_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_surface.setText("")
        self.preview_surface.setPixmap(scaled_pixmap)
        self.preview_surface.setFixedSize(scaled_pixmap.size())

        self.preview_overlay.setGeometry(self.preview_surface.rect())
        self.preview_overlay.set_slot_positions(
            self._scaled_preview_slot_positions(
                device.layout_key,
                preview_side,
                pixmap.size(),
                scaled_pixmap.size(),
            )
        )
        self.preview_overlay.show()
        self.preview_overlay.raise_()
        self.preview_status_label.setText(f"Listening for input from {device.display_name}.")

    def _preview_side_for_device(self, device: DetectedJoystickDevice) -> Literal["left", "right"]:
        right_device = self.current_right_device()
        if right_device is not None and self._same_device(device, right_device):
            return "right"
        return "left"

    def _handle_preview_activity(self, event: JoystickActivityEvent) -> None:
        if self.selected_preview_device is None:
            return
        if not self._event_matches_selected_device(event, self.selected_preview_device):
            return
        self.preview_overlay.record_activity(event)

    def save_assignments(self) -> None:
        left_device = self.current_left_device()
        right_device = self.current_right_device()

        if left_device is None or right_device is None:
            self.validation_label.setText("Select both left and right joysticks before saving.")
            return
        if left_device.product_guid == right_device.product_guid:
            self.validation_label.setText("Left and right must use different devices.")
            return

        self.config.joystick_left_name_filter = left_device.product_name
        self.config.joystick_right_name_filter = right_device.product_name
        self.config.joystick_type_left = self._type_label(left_device)
        self.config.joystick_type_right = self._type_label(right_device)
        self.config.joystick_instance_left = left_device.saved_instance
        self.config.joystick_instance_right = right_device.saved_instance
        self.config.save()
        self.validation_label.clear()
        self.accept()

    @staticmethod
    def _restore_selector_value(selector: QComboBox, product_guid: str | None) -> None:
        if product_guid is None:
            selector.setCurrentIndex(0)
            return

        for index in range(selector.count()):
            if selector.itemData(index) == product_guid:
                selector.setCurrentIndex(index)
                return

        selector.setCurrentIndex(0)

    @staticmethod
    def _type_label(device: DetectedJoystickDevice) -> str:
        return device.display_name or device.product_name

    def _scaled_preview_slot_positions(
        self,
        layout_key: str,
        side: Literal["left", "right"],
        original_size: QSize,
        scaled_size: QSize,
    ) -> dict[str, QPoint]:
        slot_positions = slot_positions_for_layout(layout_key, side)
        if original_size.width() <= 0 or original_size.height() <= 0:
            return slot_positions

        scale_x = scaled_size.width() / original_size.width()
        scale_y = scaled_size.height() / original_size.height()
        return {
            slot_name: QPoint(
                int(round(position.x() * scale_x)),
                int(round(position.y() * scale_y)),
            )
            for slot_name, position in slot_positions.items()
        }

    def _clear_preview_surface(self) -> None:
        self.preview_surface.clear()
        self.preview_surface.setText("Preview unavailable")
        self.preview_surface.setFixedSize(DEFAULT_PREVIEW_SIZE)

    @staticmethod
    def _event_matches_selected_device(
        event: JoystickActivityEvent,
        device: DetectedJoystickDevice,
    ) -> bool:
        return (
            event.product_guid == device.product_guid
            and event.saved_instance == device.saved_instance
        )

    @staticmethod
    def _same_device(left: DetectedJoystickDevice, right: DetectedJoystickDevice) -> bool:
        return (
            left.product_guid == right.product_guid
            and left.saved_instance == right.saved_instance
        )