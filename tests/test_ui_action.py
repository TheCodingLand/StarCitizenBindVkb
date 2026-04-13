from typing import Any

from app.components.ui_action import ActionSelectionDialog
from app.domain import TriggerMode
from app.services import SessionCatalogEntry


def test_action_selection_dialog_localizes_action_labels(qtbot: Any) -> None:
    dialog = ActionSelectionDialog(
        [
            SessionCatalogEntry(
                action_name="view_clear_saved_view",
                actionmap_name="view_director_mode",
                category="@ui_CGAdvanCamControls",
                subcategory="view_director_mode",
                display_label="@ui_CIAdvanCamClearSave",
                supports_joystick=True,
                supported_trigger_modes=(TriggerMode.PLAIN,),
            )
        ]
    )
    qtbot.addWidget(dialog)

    category_item = dialog.model.item(0, 0)
    assert category_item is not None
    action_item = category_item.child(0)
    assert action_item is not None

    assert action_item.text() == "Clear Saved View"