# Default Binding Overlay And Search Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show inherited Star Citizen default bindings alongside explicit bindings in the joystick UI, with a visibility toggle and action search, without changing explicit-only export semantics.

**Architecture:** Keep import/export and session state explicit-only. Build an effective projection layer that overlays the active session on top of the bundled default profile from `app/data/SCBindsDefault.xml`, tags rows as explicit or default, and feeds both the joystick occupancy view and the right-side action table.

**Tech Stack:** Python 3.13, PyQt6, existing headless binding/session services, pytest.

---

## Chunk 1: Effective Projection Model

### Task 1: Extend UI projection models for effective rows

**Files:**
- Modify: `app/services/ui_models.py`
- Test: `tests/test_ui_projection.py`

- [ ] **Step 1: Write the failing projection test**
- [ ] **Step 2: Run it to verify it fails**
- [ ] **Step 3: Add row/source metadata needed for explicit vs default rendering**
- [ ] **Step 4: Re-run the projection test and keep it green**

### Task 2: Add default-profile overlay projection

**Files:**
- Modify: `app/services/ui_projection.py`
- Test: `tests/test_ui_projection.py`

- [ ] **Step 1: Write failing tests for overlay precedence and inherited-row tagging**
- [ ] **Step 2: Run the focused test selection to verify red**
- [ ] **Step 3: Implement effective projection that merges explicit bindings over default bindings**
- [ ] **Step 4: Re-run the focused projection tests to verify green**

## Chunk 2: Session Controller Default View State

### Task 3: Load bundled default profile for UI projection only

**Files:**
- Modify: `app/services/ui_session_controller.py`
- Modify: `app/ui.py`
- Test: `tests/test_ui_session_controller.py`

- [ ] **Step 1: Write failing tests for controller-provided default overlay state**
- [ ] **Step 2: Run the focused controller tests to verify red**
- [ ] **Step 3: Thread default-view configuration into controller refresh/projection**
- [ ] **Step 4: Re-run the focused controller tests to verify green**

## Chunk 3: Main Window Search And Toggle

### Task 4: Add default-visibility checkbox and action search input

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Write failing UI tests for the visibility toggle and search filtering**
- [ ] **Step 2: Run the focused UI tests to verify red**
- [ ] **Step 3: Add a `Show Default Bindings` checkbox and search box to the action panel**
- [ ] **Step 4: Wire filtering and row rendering against the effective projected rows**
- [ ] **Step 5: Re-run the focused UI tests to verify green**

### Task 5: Reflect inherited defaults in joystick occupancy/global layout

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Write a failing test proving inherited default axis/button occupancy appears in the joystick view**
- [ ] **Step 2: Run the focused UI test to verify red**
- [ ] **Step 3: Update slot rendering to use the effective projection while keeping inherited rows read-only**
- [ ] **Step 4: Re-run the focused UI test to verify green**

## Chunk 4: Verification

### Task 6: Run affected verification lane

**Files:**
- Test: `tests/test_ui_projection.py`
- Test: `tests/test_ui_session_controller.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Run the focused pytest lane**

Run: `pytest -o addopts= tests/test_ui_projection.py tests/test_ui_session_controller.py tests/test_ui.py`

Expected: all targeted tests pass.

- [ ] **Step 2: Run lint on touched files**

Run: `python -m ruff check app/services/ui_models.py app/services/ui_projection.py app/services/ui_session_controller.py app/ui.py tests/test_ui_projection.py tests/test_ui_session_controller.py tests/test_ui.py`

Expected: no lint errors.