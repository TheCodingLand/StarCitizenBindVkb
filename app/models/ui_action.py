from typing import Optional
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTreeView, QLineEdit
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, QSortFilterProxyModel, QModelIndex
from pydantic import BaseModel
from app.globals import localization_file
from app.models.actions import AllActionMaps

class WidgetItemRoleData(BaseModel):
    is_category: bool = False
    original_name: str = ""
    translated_name: str = ""


class ActionSelectionDialog(QDialog):
    def __init__(self, actions_objs: AllActionMaps, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.setWindowTitle("Select Action")
        self.action_objs = actions_objs
        self.selected_action: Optional[str] = None
        self.resize(600, 800)  # Adjust the size as needed
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Add a QLineEdit for search input
        self.search_bar = QLineEdit(self)
        self.search_bar.setPlaceholderText("Search actions...")
        layout.addWidget(self.search_bar)

        self.tree_view = QTreeView(self)

        # Original model
        self.model = QStandardItemModel()
        self.root_node = self.model.invisibleRootItem()

        for category, sub_actions in self.action_objs.root.items():
            category_item = QStandardItem(localization_file.get_localization_string(category))
            category_item.setData(WidgetItemRoleData(is_category=True, original_name=category), Qt.ItemDataRole.UserRole)
            

            for action in sub_actions.action:
                action_label = localization_file.get_localization_string(action.ui_label) if action.ui_label else action.name
                action_item = QStandardItem(action_label)
                #action_item.setData(action.name, Qt.ItemDataRole.UserRole)  # Original action name
                #action_item.setData(action_label, Qt.ItemDataRole.DisplayRole)  # Localized label
                action_item.setData(WidgetItemRoleData(original_name=action.name, translated_name=action_label, is_category=False), Qt.ItemDataRole.UserRole)
                category_item.appendRow(action_item)
            self.root_node.appendRow(category_item)

        # Proxy model for filtering with custom logic
        self.proxy_model = ActionFilterProxyModel(self)
        self.proxy_model.setSourceModel(self.model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        self.tree_view.setModel(self.proxy_model)
        self.tree_view.expandAll()
        self.tree_view.doubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.tree_view)
        self.tree_view.header().hide()

        # Connect the search bar text change to the filter function
        self.search_bar.textChanged.connect(self.on_search_text_changed)

    def on_search_text_changed(self, text: str) -> None:
        # Set the filter to match the search text
        self.proxy_model.setSearchText(text)
        self.tree_view.expandAll()  # Expand all to show the search results

    def on_item_double_clicked(self, index: QModelIndex) -> None:
        # Map the proxy index to the source index
        source_index = self.proxy_model.mapToSource(index)
        item = self.model.itemFromIndex(source_index)
        if item:
            if item.hasChildren():
                # Expand or collapse the category
                expanded = self.tree_view.isExpanded(index)
                self.tree_view.setExpanded(index, not expanded)
            else:
                self.selected_action = item.data(Qt.ItemDataRole.UserRole).original_name
                self.accept()


class ActionFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.search_text: str = ""

    def setSearchText(self, text: str) -> None:
        self.search_text = text
        self.invalidateFilter()  # Re-evaluate the filter

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not self.search_text:
            return True  # Show all rows if search text is empty

        # Access the item by row and parent index
        index = self.sourceModel().index(source_row, 0, source_parent)
        item = self.sourceModel().itemFromIndex(index)
        data: Optional[WidgetItemRoleData] = item.data(Qt.ItemDataRole.UserRole)

        # Check if the current item matches
        search_text_lower = self.search_text.lower()
        if data and (
            (not data.is_category and (search_text_lower in data.original_name.lower() or search_text_lower in data.translated_name.lower()))
            or (data.is_category and search_text_lower in data.original_name.lower())
        ):
            return True

        # Recursively check if any children match
        for row in range(item.rowCount()):
            child_index = item.child(row).index()
            if self.filterAcceptsRow(child_index.row(), index):
                return True

        return False