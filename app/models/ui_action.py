
# models/action.py
from typing import Dict
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTreeView
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt

from app.globals import APP_PATH
from app.localization import LocalizationFile

from app.models.actions import Action

localization_file = LocalizationFile.from_file(APP_PATH / 'data' / 'Localization' / 'english'/ 'global.ini')

class ActionSelectionDialog(QDialog):
    def __init__(self, actions_objs: Dict[str, Dict[str, Action]], parent: QDialog | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select Action")
        self.action_objs = actions_objs
        self.selected_action = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tree_view = QTreeView(self)
        model = QStandardItemModel()
        root_node = model.invisibleRootItem()

        for category, sub_actions in self.action_objs.items():
            category_item = QStandardItem(localization_file.get_localization_string(category))
            for action_key, action in sub_actions.items():
                action_item = QStandardItem(localization_file.get_localization_string(action.ui_label) if action.ui_label else action.name)
                action_item.setData(action_key, Qt.ItemDataRole.UserRole)
                category_item.appendRow(action_item)
            root_node.appendRow(category_item)

        self.tree_view.setModel(model)
        self.tree_view.expandAll()
        self.tree_view.doubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.tree_view)
        self.tree_view.header().hide()

    def on_item_double_clicked(self, index: int):
        item = self.tree_view.model().itemFromIndex(index)
        if item:
            if item.hasChildren():
                # Expand or collapse the category
                self.tree_view.setExpanded(index, not self.tree_view.isExpanded(index))
            else:
                self.selected_action = item.data(Qt.ItemDataRole.UserRole)
                self.accept()
