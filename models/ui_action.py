
# models/action.py
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTreeView, QPushButton
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt

class ActionSelectionDialog(QDialog):
    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Action")
        self.actions = actions
        self.selected_action = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tree_view = QTreeView(self)
        model = QStandardItemModel()
        root_node = model.invisibleRootItem()

        # Add 'Clear Action' option
        clear_item = QStandardItem("Clear Action")
        root_node.appendRow(clear_item)

        for category, sub_actions in self.actions.items():
            category_item = QStandardItem(category)
            for action in sub_actions:
                action_item = QStandardItem(action)
                category_item.appendRow(action_item)
            root_node.appendRow(category_item)

        self.tree_view.setModel(model)
        self.tree_view.expandAll()
        self.tree_view.doubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.tree_view)

    def on_item_double_clicked(self, index):
        item = self.tree_view.model().itemFromIndex(index)
        if item:
            if item.hasChildren():
                # Expand or collapse the category
                self.tree_view.setExpanded(index, not self.tree_view.isExpanded(index))
            else:
                self.selected_action = item.text()
                self.accept()
