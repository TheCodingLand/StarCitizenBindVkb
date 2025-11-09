import colorsys
from typing import List, Tuple
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QPainter, QColor, QPaintEvent

from app.models.device_actions import Action
from app.models.joystick import JoyAction


def get_palette_color(n: int) -> List[Tuple[int, int, int]]:
    colors = []
    for i in range(n):
        # Evenly distribute hues across the number of colors
        hue = i / n
        # Use full saturation and brightness for vibrant colors
        rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        # Convert to 8-bit RGB values
        rgb = tuple(int(channel * 255) for channel in rgb)
        colors.append(rgb)
    return colors


btn_modifiers= {
    "tap": "purple",
    "mod": "lightgreen",
    "multitap": "lightblue",
    "hold": "lightcoral",

}


def gen_cat_colors(actions: List[Action]) -> dict[str, Tuple[int, int, int]]:
    colors = get_palette_color(len(actions))
    return {action.name: colors[i] for i, action in enumerate(actions)}



class CustomButton(QPushButton):
    def __init__(self, items: List[JoyAction] | None = None, parent=None):
        super().__init__(parent)
        self.items : List[JoyAction] = items if items is not None else []  # items is a list of tuples (text, action)
        self.setStyleSheet("background-color: transparent;")
        self.setMinimumSize(100, 50)  # Adjust as needed

    def sizeHint(self):
        # Compute the size based on number of items
        font_metrics = self.fontMetrics()
        height = font_metrics.height() * len(self.items)
        width = max([font_metrics.horizontalAdvance(text) for text, _ in self.items], default=0)
        # Add space for the colored squares
        width += 20  # Adjust as needed
        return QSize(width, height)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        font_metrics = painter.fontMetrics()
        y = font_metrics.ascent() + 2  # Adjust for padding
        text_x = 2
        for action in self.items:
            # Determine if we need to draw a colored square
            if action:
                colors = self.get_action_colors(action)
                for color in colors:
                    
                    # Draw colored square
                    square_size = font_metrics.height() - 4  # Adjust as needed
                    rect = QRect(2, y - font_metrics.ascent(), square_size, square_size)
                    painter.fillRect(rect, QColor(color))
                    text_x = rect.right() + 5
                for category in action.category:
                    if category in modes:
                        color = modes[category]
                        square_size = font_metrics.height() - 4
                    
            else:
                text_x = 2

            # Draw text
            painter.drawText(text_x, y, action.name)

            y += font_metrics.height()

    

    def get_action_colors(self, action: JoyAction) -> List[str]:
        colors = []
        for modifier, color in btn_modifiers.items():
            if getattr(action, modifier):
                colors.append(color)
        
        return colors