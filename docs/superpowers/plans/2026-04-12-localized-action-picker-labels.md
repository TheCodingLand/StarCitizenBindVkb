# Localized Action Picker Labels Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show English action names in the add-action picker while keeping raw action identifiers unchanged for binding logic.

**Architecture:** Keep localization at the presentation boundary in the picker dialog. Session/catalog entries continue to carry raw identifiers and raw catalog label keys; the dialog resolves those keys through the existing English localization loader for display and translated-name search.

**Tech Stack:** Python, PyQt6, pytest, pytest-qt

---

### Task 1: Localize picker row text

**Files:**
- Modify: `app/components/ui_action.py`
- Test: `tests/test_ui_action.py`

- [ ] **Step 1: Write the failing test**

```python
def test_action_selection_dialog_localizes_action_labels(qtbot):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ui_action.py::test_action_selection_dialog_localizes_action_labels -v`
Expected: FAIL because the dialog still shows the raw `@ui_...` label.

- [ ] **Step 3: Write minimal implementation**

```python
action_label = localization_file.get_localization_string(entry.display_label or entry.action_name)
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `pytest tests/test_ui_action.py::test_action_selection_dialog_localizes_action_labels -v`
Expected: PASS

- [ ] **Step 5: Run broader UI verification**

Run: `pytest tests/test_ui_action.py tests/test_ui.py -v`
Expected: PASS

### Task 2: Localize controller-backed main UI labels

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_select_control_map_searches_and_renders_localized_display_labels(...):
    ...

def test_select_control_map_uses_localized_button_labels(...):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui.py::test_select_control_map_searches_and_renders_localized_display_labels tests/test_ui.py::test_select_control_map_uses_localized_button_labels -v`
Expected: FAIL because the panel and button captions still use raw/internal labels.

- [ ] **Step 3: Write minimal implementation**

```python
localized_label = localization_file.get_localization_string(row.display_label or row.action_name)
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `pytest tests/test_ui.py::test_select_control_map_searches_and_renders_localized_display_labels tests/test_ui.py::test_select_control_map_uses_localized_button_labels -v`
Expected: PASS

- [ ] **Step 5: Run broader UI verification**

Run: `pytest tests/test_ui_action.py tests/test_ui.py -v`
Expected: PASS

### Task 3: Localize diagnostics and blocked conflict summaries

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_diagnostics_render_localized_actions_when_catalog_metadata_exists(...):
    ...

def test_blocked_conflict_summary_prefers_localized_action_labels(...):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui.py::test_diagnostics_render_in_generalized_table tests/test_ui.py::test_blocked_conflict_summary_disables_save_and_export -v`
Expected: FAIL because those views still show raw action identifiers.

- [ ] **Step 3: Write minimal implementation**

```python
localized = localization_file.get_localization_string(catalog_entry.display_label)
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `pytest tests/test_ui.py::test_diagnostics_render_in_generalized_table tests/test_ui.py::test_blocked_conflict_summary_disables_save_and_export -v`
Expected: PASS

- [ ] **Step 5: Run broader UI verification**

Run: `pytest tests/test_ui_action.py tests/test_ui.py -v`
Expected: PASS