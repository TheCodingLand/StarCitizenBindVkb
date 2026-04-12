from __future__ import annotations

from dataclasses import dataclass
import time

from PyQt6.QtCore import QPoint, QTimer, Qt
from PyQt6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from app.services import JoystickActivityEvent


@dataclass
class ActivePulse:
    slot_name: str
    center: QPoint
    started_at: float
    active: bool = True


class JoystickActivityOverlay(QWidget):
    def __init__(
        self,
        slot_positions: dict[str, QPoint] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slot_positions: dict[str, QPoint] = dict(slot_positions or {})
        self.active_pulses: dict[str, ActivePulse] = {}
        self._pulse_duration_ms = 450
        self._expire_timer = QTimer(self)
        self._expire_timer.setInterval(16)
        self._expire_timer.timeout.connect(self._expire_stale_pulses)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self._sync_to_parent()

    def set_slot_positions(self, slot_positions: dict[str, QPoint]) -> None:
        self.slot_positions = dict(slot_positions)
        self.active_pulses.clear()
        self._expire_timer.stop()
        self._sync_to_parent()
        self.update()

    def record_activity(self, event: JoystickActivityEvent) -> None:
        if not event.active:
            self.active_pulses.pop(event.slot_name, None)
            if not self.active_pulses:
                self._expire_timer.stop()
            self.update()
            return

        center = self.slot_positions.get(event.slot_name)
        if center is None:
            return

        self.active_pulses[event.slot_name] = ActivePulse(
            slot_name=event.slot_name,
            center=QPoint(center),
            started_at=event.timestamp,
        )
        self._sync_to_parent()
        self.raise_()
        if not self._expire_timer.isActive():
            self._expire_timer.start()
        self.update()

    def _expire_stale_pulses(self, now_ms: float | None = None) -> None:
        if now_ms is None:
            now_ms = time.monotonic() * 1000

        self.active_pulses = {
            slot_name: pulse
            for slot_name, pulse in self.active_pulses.items()
            if now_ms - pulse.started_at < self._pulse_duration_ms
        }
        if not self.active_pulses:
            self._expire_timer.stop()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event

        if not self.active_pulses:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        now_ms = time.monotonic() * 1000

        for pulse in self.active_pulses.values():
            progress = min(max((now_ms - pulse.started_at) / self._pulse_duration_ms, 0.0), 1.0)
            glow_radius = 14 + int(progress * 22)
            ring_radius = 10 + int(progress * 30)
            glow_alpha = max(0, int(72 * (1.0 - progress)))
            ring_alpha = max(0, int(220 * (1.0 - progress)))

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 214, 96, glow_alpha))
            painter.drawEllipse(pulse.center, glow_radius, glow_radius)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 239, 180, ring_alpha), 3))
            painter.drawEllipse(pulse.center, ring_radius, ring_radius)

        painter.end()

    def _sync_to_parent(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())


__all__ = ["ActivePulse", "JoystickActivityOverlay"]