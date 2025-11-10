import colorsys
from typing import List, Optional, Tuple

from PyQt6.QtCore import QRect, QSize
from PyQt6.QtGui import QColor, QPaintEvent, QPainter
from PyQt6.QtWidgets import QPushButton, QWidget

from app.models.device_actions import Action
from app.models.joystick import JoyAction


def get_palette_color(n: int) -> List[Tuple[int, int, int]]:
    colors: List[Tuple[int, int, int]] = []
    for i in range(n):
        # Evenly distribute hues across the number of colors
        hue = i / n
        # Use full saturation and brightness for vibrant colors
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        rgb_tuple: Tuple[int, int, int] = (
            int(r * 255),
            int(g * 255),
            int(b * 255),
        )
        colors.append(rgb_tuple)
    return colors


BTN_MODIFIERS = {
    "tap": "purple",
    "mod": "lightgreen",
    "multitap": "lightblue",
    "hold": "lightcoral",
}


def gen_cat_colors(actions: List[Action]) -> dict[str, Tuple[int, int, int]]:
    colors = get_palette_color(len(actions))
    return {action.name: colors[i] for i, action in enumerate(actions)}


class CustomButton(QPushButton):
    def __init__(
        self,
        items: List[JoyAction] | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.items: List[JoyAction] = items or []
        self.setStyleSheet("background-color: transparent;")
        self.setMinimumSize(100, 50)

    def sizeHint(self) -> QSize:  # type: ignore[override]
        font_metrics = self.fontMetrics()
        if not self.items:
            height = font_metrics.height()
            return QSize(100, height)

        height = font_metrics.height() * len(self.items)
        width = max(font_metrics.horizontalAdvance(action.name) for action in self.items)
        if any(self.get_action_colors(action) for action in self.items):
            width += 20
        return QSize(width, height)

    def paintEvent(self, a0: QPaintEvent | None) -> None:  # type: ignore[override]
        painter = QPainter(self)
        font_metrics = painter.fontMetrics()
        y = font_metrics.ascent() + 2

        for action in self.items:
            text_x = 2
            colors = self.get_action_colors(action)
            for color in colors:
                square_size = font_metrics.height() - 4
                rect = QRect(2, y - font_metrics.ascent(), square_size, square_size)
                painter.fillRect(rect, QColor(color))
                text_x = rect.right() + 5

            painter.drawText(text_x, y, action.name)
            y += font_metrics.height()

        painter.end()

    def get_action_colors(self, action: JoyAction) -> List[str]:
        colors: List[str] = []
        for modifier, color in BTN_MODIFIERS.items():
            if getattr(action, modifier, False):
                colors.append(color)
        return colors
