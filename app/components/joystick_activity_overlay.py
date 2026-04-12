from __future__ import annotations

from dataclasses import dataclass
import time

from PyQt6.QtCore import QPoint, QRect, QSize, QTimer, Qt
from PyQt6.QtGui import QColor, QPaintEvent, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from app.services import JoystickActivityEvent


DEFAULT_SLOT_SIZE = QSize(155, 35)


@dataclass
class ActivePulse:
    slot_name: str
    rect: QRect
    started_at: float
    active: bool = True
    sustained: bool = False


class JoystickActivityOverlay(QWidget):
    def __init__(
        self,
        slot_positions: dict[str, QPoint] | None = None,
        slot_size: QSize | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.slot_positions: dict[str, QPoint] = dict(slot_positions or {})
        self.slot_size = QSize(slot_size or DEFAULT_SLOT_SIZE)
        self.active_pulses: dict[str, ActivePulse] = {}
        self._pulse_duration_ms = 450
        self._expire_timer = QTimer(self)
        self._expire_timer.setInterval(16)
        self._expire_timer.timeout.connect(self._expire_stale_pulses)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self._sync_to_parent()

    def set_slot_positions(
        self,
        slot_positions: dict[str, QPoint],
        slot_size: QSize | None = None,
    ) -> None:
        self.slot_positions = dict(slot_positions)
        if slot_size is not None:
            self.slot_size = QSize(slot_size)
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

        sustained = event.input_kind == "axis"

        self.active_pulses[event.slot_name] = ActivePulse(
            slot_name=event.slot_name,
            rect=self._slot_rect(center),
            started_at=event.timestamp,
            sustained=sustained,
        )
        self._sync_to_parent()
        self.raise_()
        if not sustained and not self._expire_timer.isActive():
            self._expire_timer.start()
        self.update()

    def _expire_stale_pulses(self, now_ms: float | None = None) -> None:
        if now_ms is None:
            now_ms = time.monotonic() * 1000

        self.active_pulses = {
            slot_name: pulse
            for slot_name, pulse in self.active_pulses.items()
            if pulse.sustained or now_ms - pulse.started_at < self._pulse_duration_ms
        }
        if not self._has_timed_pulses():
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
            border_rect = pulse.rect.adjusted(-4, -4, 4, 4)
            if pulse.sustained:
                painter.setBrush(QColor(255, 28, 28, 40))
                painter.setPen(QPen(QColor(235, 20, 20, 235), 4))
                painter.drawRoundedRect(border_rect, 8, 8)

                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(255, 130, 130, 140), 2))
                painter.drawRoundedRect(border_rect.adjusted(-3, -3, 3, 3), 10, 10)
                continue

            progress = min(max((now_ms - pulse.started_at) / self._pulse_duration_ms, 0.0), 1.0)
            expansion = 3 + int(progress * 10)
            pulse_rect = border_rect.adjusted(-expansion, -expansion, expansion, expansion)
            fill_alpha = max(0, int(56 * (1.0 - progress)))
            border_alpha = max(0, int(255 * (1.0 - progress)))
            glow_alpha = max(0, int(140 * (1.0 - progress)))

            painter.setBrush(QColor(255, 36, 36, fill_alpha))
            painter.setPen(QPen(QColor(255, 28, 28, border_alpha), 4))
            painter.drawRoundedRect(pulse_rect, 8, 8)

            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(255, 140, 140, glow_alpha), 2))
            painter.drawRoundedRect(pulse_rect.adjusted(-3, -3, 3, 3), 10, 10)

        painter.end()

    def _slot_rect(self, top_left: QPoint) -> QRect:
        return QRect(top_left, self.slot_size)

    def _has_timed_pulses(self) -> bool:
        return any(not pulse.sustained for pulse in self.active_pulses.values())

    def _sync_to_parent(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())


__all__ = ["ActivePulse", "DEFAULT_SLOT_SIZE", "JoystickActivityOverlay"]