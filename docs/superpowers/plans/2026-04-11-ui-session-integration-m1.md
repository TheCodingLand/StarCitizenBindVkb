# UI Session Integration M1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the widget-owned load/edit/export path with a session-backed Qt integration slice that projects `BindingSessionService` state into the existing joystick UI, surfaces diagnostics and blocked conflicts, and keeps the current button-grid workflow intact.

**Architecture:** Extend the headless catalog and session contracts just enough to support a deterministic UI-facing catalog view and row-identity-aware edits, then add a thin controller/projection layer that the widget owns instead of XML mutation logic. Keep `JoystickConfig` as a render projection only; all durable load/edit/export behavior runs through the headless repositories and session service.

**Tech Stack:** Python 3.11+, PyQt6, pytest, existing headless repositories/session service, existing VKB button metadata, existing Star Citizen XML fixtures, focused non-Qt controller/projection tests plus a minimal Qt seam lane.

---

## Planned File Structure

**Create**

- `app/services/ui_models.py` — UI-session dataclasses and enums for catalog entries, projected rows, diagnostic rows, export-state bundle, and command outcomes.
- `app/services/ui_projection.py` — pure projection functions from `BindingSession` and `GameCatalog` into `JoystickConfig`, projected rows, and UI diagnostics.
- `app/services/ui_session_controller.py` — session-backed controller that resolves imported role maps, owns the active session, exposes row-aware create/remove/move commands, and maintains export-state and diagnostic buckets.
- `tests/test_ui_projection.py` — non-Qt tests for catalog-view filtering, trigger-mode mapping, collision precedence, and projection diagnostics.
- `tests/test_ui_session_controller.py` — non-Qt tests for imported-role resolution, picker/catalog snapshot behavior, command outcomes, export-state preservation and clearing, blocked-conflict handling, and atomic move behavior.
- `docs/superpowers/plans/2026-04-11-ui-session-integration-m1.md` — this plan file.

**Modify**

- `app/domain/models.py` — enrich catalog-facing action definitions with the UI metadata needed for session-bound picker entries.
- `app/domain/catalog.py` — expose provenance-aware catalog entries and deterministic lookup helpers for `(action_name, actionmap_name)`.
- `app/domain/session.py` — add a stable binding-reference type for row-aware edits, capture the active catalog snapshot/version used at session open, and export both contracts.
- `app/domain/__init__.py` — export the new session/catalog contracts.
- `app/io/action_catalog_repository.py` — keep repository output aligned with the richer catalog contract.
- `app/services/binding_session.py` — add identity-aware binding removal/move helpers used by the UI controller and keep move semantics atomic.
- `app/services/__init__.py` — export the new UI controller and UI models that the widget imports.
- `app/components/ui_action.py` — populate the action picker from the active session catalog view rather than global action tables.
- `app/ui.py` — replace direct XML parsing/export mutation with controller-driven load/edit/export, remove default editable seeding, update diagnostics/conflicts UI, and refresh projected state from controller results.
- `tests/test_action_catalog_repository.py` — add catalog-view assertions for provenance-aware entries and display metadata.
- `tests/test_binding_session.py` — add row-aware removal/move tests and ambiguity restrictions for duplicate-name bindings.
- `tests/test_ui.py` — convert brittle widget tests to the new no-session startup state and add the smallest possible Qt seam coverage for controller-driven load, picker, projected add/remove flows, diagnostics, and blocked conflicts.

**Do Not Touch In This Plan**

- `app/utils/devices.py` — stable device identity/remapping is the next milestone, not part of this UI slice.
- `app/dev_tools/export_configmap.py` — catalog refresh/extraction UX is follow-on work, not part of this UI slice.
- `tests/test_ui.py` beyond the minimal controller-wiring seam — do not expand the unstable Windows Qt lane beyond startup, picker, add/remove-through-projection, diagnostics, and blocked-conflict coverage.

## Chunk 1: Headless Contracts For The UI Seam

### Task 1: Add Red Tests For Provenance-Aware Catalog View And Session Identity

**Files:**
- Modify: `tests/test_action_catalog_repository.py`
- Modify: `tests/test_binding_session.py`

- [ ] **Step 1: Extend the catalog repository test with provenance-aware expectations**

Add red tests that prove the catalog can expose action entries by both action name and actionmap provenance, including duplicate-name actions.

```python
def test_action_catalog_repository_exposes_provenance_aware_entries() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json"))

    catalog = repo.load()
    entry = catalog.entry_for("v_emergency_exit", "seat_general")

    assert entry is not None
    assert entry.action_name == "v_emergency_exit"
    assert entry.actionmap_name == "seat_general"
    assert entry.category == "Vehicles - Seats and Operator Modes"
    assert entry.subcategory == "Seat"
    assert entry.display_label
    assert entry.supports_joystick is True
    assert TriggerMode.PLAIN in entry.supported_trigger_modes


def test_action_catalog_repository_rejects_ambiguous_name_only_lookup() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json"))

    catalog = repo.load()

    assert catalog.entry_for("v_flightready", None) is None
```

- [ ] **Step 2: Add red service tests for session-bound catalog identity and row-aware edits**

Extend `tests/test_binding_session.py` with tests like:

```python
def test_open_profile_captures_catalog_snapshot_used_for_session() -> None:
    ...


def test_bind_validation_uses_catalog_captured_at_session_open() -> None:
    ...


def test_remove_binding_reference_removes_only_the_target_binding() -> None:
    ...


def test_move_binding_reference_restores_original_on_rejected_target() -> None:
    ...


def test_move_binding_reference_restores_original_on_unexpected_bind_exception() -> None:
    ...


def test_move_binding_reference_rejects_ambiguous_duplicate_name_import() -> None:
    ...


def test_remove_binding_reference_accepts_ambiguous_duplicate_name_import_by_identity() -> None:
    ...


def test_move_binding_reference_preserves_passthrough_replacement_identity() -> None:
    ...
```

- [ ] **Step 3: Run the red headless contract lane**

Run: `uv run pytest -o addopts= tests/test_action_catalog_repository.py tests/test_binding_session.py -q`

Expected: FAIL because the current catalog and session/service contracts do not yet expose provenance-aware catalog entries, a session-bound catalog snapshot, or row-aware binding commands.

- [ ] **Step 4: Commit the red tests**

```bash
git add tests/test_action_catalog_repository.py tests/test_binding_session.py
git commit -m "test: add ui session contract red tests"
```

### Task 2: Extend Catalog And Session Contracts For UI Projection

**Files:**
- Modify: `app/domain/models.py`
- Modify: `app/domain/catalog.py`
- Modify: `app/domain/session.py`
- Modify: `app/domain/__init__.py`
- Modify: `app/io/action_catalog_repository.py`

- [ ] **Step 1: Add the missing catalog metadata to the domain contract**

Extend the action-definition shape so the UI seam does not need to fall back to global action tables for labels, actionmap provenance, and trigger compatibility.

The plan shape is:

```python
@dataclass
class ActionDefinition:
    identifier: ActionIdentifier
    action_name: str
    actionmap_name: str
    category: str
    subcategory: str
    display_label: str
    supported_trigger_modes: tuple[TriggerMode, ...] = ()
    supports_joystick: bool = True
    default_inputs: tuple[str, ...] = ()
```

- [ ] **Step 2: Add provenance-aware lookup helpers to `GameCatalog`**

Add deterministic lookup helpers and explicit entry storage keyed by `(action_name, actionmap_name)`.

```python
@dataclass
class GameCatalog:
    ...
    entries_by_key: dict[tuple[str, str | None], ActionDefinition] = field(default_factory=dict)

    def entry_for(self, action_name: str, actionmap_name: str | None) -> ActionDefinition | None:
        ...
```

Make duplicate-name behavior explicit: name-only lookup is allowed only when there is one unambiguous matching actionmap.

- [ ] **Step 3: Add a binding-reference type and session-bound catalog snapshot to the session domain**

`BindingSessionService` needs a stable way to address one projected row, and the session contract needs to retain the exact catalog snapshot or version used at open time. Add both contracts in `app/domain/session.py`.

```python
@dataclass(frozen=True)
class BindingReference:
    role: str
    slot_id: str
    action_name: str
    trigger_mode: TriggerMode
    modifier_token: str | None = None
    source_record_id: str | None = None
    source_actionmap_name: str | None = None
    replaced_passthrough_record_id: str | None = None


@dataclass(frozen=True)
class SessionCatalogSnapshot:
    version: GameCatalogVersion
    catalog: GameCatalog
```

- [ ] **Step 4: Re-run the headless UI seam tests and make the read-side green**

Run: `uv run pytest -o addopts= tests/test_action_catalog_repository.py -q`

Expected: PASS. `tests/test_binding_session.py` should still remain red until Task 3 lands the session/service work.

- [ ] **Step 5: Commit the contract changes**

```bash
git add app/domain/models.py app/domain/catalog.py app/domain/session.py app/domain/__init__.py app/io/action_catalog_repository.py tests/test_action_catalog_repository.py
git commit -m "feat: add ui-facing catalog and binding reference contracts"
```

### Task 3: Add Identity-Aware Session Commands

**Files:**
- Modify: `app/services/binding_session.py`
- Modify: `app/services/__init__.py`
- Test: `tests/test_binding_session.py`

- [ ] **Step 1: Run only the new service red tests**

Run: `uv run pytest -o addopts= tests/test_binding_session.py -k "remove_binding_reference or move_binding_reference" -q`

Expected: FAIL because the service has no row-aware command surface yet.

- [ ] **Step 2: Implement the session-bound open path and identity-aware service methods**

Add methods such as:

```python
def open_profile(...) -> BindingSession:
    ...


def remove_binding(self, binding_ref: BindingReference) -> BindingSession:
    ...


def move_binding(self, binding_ref: BindingReference, target_slot: str) -> BindingSession:
    ...
```

Rules:

- capture and retain the exact catalog snapshot or version used when the session is opened,
- match one binding by full binding reference, not by action name alone,
- keep move atomic by prevalidating the target bind before removing the source binding,
- preserve provenance, modifier-token state, and `replaced_passthrough_record_id` when the move succeeds,
- restore the original binding state if the target bind raises unexpectedly during move-style replacement,
- reject move attempts for ambiguous duplicate-name bindings and leave session state unchanged,
- return the unchanged session on rejected moves.

- [ ] **Step 3: Verify the full Chunk 1 headless lane**

Run: `uv run pytest -o addopts= tests/test_action_catalog_repository.py tests/test_binding_session.py -q`

Expected: PASS.

- [ ] **Step 4: Commit the service extension**

```bash
git add app/services/binding_session.py app/services/__init__.py tests/test_binding_session.py
git commit -m "feat: add row-aware session binding commands"
```

## Chunk 2: Controller And Projection Layer

### Task 4: Implement Pure UI Models And Projection Logic

**Files:**
- Create: `app/services/ui_models.py`
- Create: `app/services/ui_projection.py`
- Modify: `app/services/__init__.py`
- Test: `tests/test_ui_projection.py`

- [ ] **Step 1: Add red non-Qt tests for projection behavior**

Seed `tests/test_ui_projection.py` with small deterministic tests:

```python
def test_project_binding_maps_trigger_mode_to_joy_action_flags() -> None:
    ...


def test_projection_reports_overflowed_duplicate_binding_as_projection_diagnostic() -> None:
    ...


def test_projection_uses_spec_snapshot_order_for_collision_winner() -> None:
    ...


def test_projection_reports_unrenderable_slot_as_projection_diagnostic() -> None:
    ...


def test_projection_reports_missing_or_ambiguous_action_metadata() -> None:
    ...


def test_catalog_view_filters_non_joystick_and_ambiguous_actions() -> None:
    ...


def test_catalog_view_filters_entries_for_selected_trigger_mode() -> None:
    ...
```

Run: `uv run pytest -o addopts= tests/test_ui_projection.py -q`

Expected: FAIL until the projection module exists.

- [ ] **Step 2: Define the UI-session dataclasses and enums**

Create a small shared model module so Qt code and non-Qt tests can talk about the same shapes.

Include at least:

```python
class UiCommandOutcome(str, Enum):
    MUTATED = "mutated"
    REJECTED = "rejected"
    NOOP = "noop"


@dataclass(frozen=True)
class SessionCatalogEntry:
    action_name: str
    actionmap_name: str | None
    category: str
    subcategory: str
    display_label: str
    supports_joystick: bool
    supported_trigger_modes: tuple[TriggerMode, ...]


@dataclass(frozen=True)
class ProjectedBindingRow:
    binding_ref: BindingReference
    side: str
    button_name: str
    slot_id: str
    action_name: str
    display_label: str
    modifier: bool
    hold: bool
    multitap: bool


@dataclass(frozen=True)
class UiDiagnosticRow:
    kind: str
    action: str
    detail: str
    side: str
    record_id: str | None = None


@dataclass
class UiExportState:
    document: Any | None = None
    blocked_conflicts: list[PassthroughConflict] = field(default_factory=list)
    validation_diagnostics: list[UiDiagnosticRow] = field(default_factory=list)
    export_enabled: bool = False
```

- [ ] **Step 3: Implement the session catalog view and binding-row projection helpers**

`app/services/ui_projection.py` should stay Qt-free. It should:

- build the session-bound catalog view from `GameCatalog`,
- map `BindingEdit` to `ProjectedBindingRow` and `JoyAction`.

- [ ] **Step 4: Implement projection diagnostics and `JoystickConfig` assembly**

Extend the pure projection helpers so they also:

- apply deterministic overflow precedence,
- apply the exact normalized binding-snapshot ordering from the spec when choosing the rendered collision winner,
- emit projection diagnostics for non-renderable, non-selected, or metadata-ambiguous rows,
- build left/right `JoystickConfig` objects from projected rows.

- [ ] **Step 5: Re-run the non-Qt projection tests**

Run: `uv run pytest -o addopts= tests/test_ui_projection.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the UI projection layer**

```bash
git add app/services/ui_models.py app/services/ui_projection.py app/services/__init__.py tests/test_ui_projection.py
git commit -m "feat: add ui session projection layer"
```

### Task 5: Implement The Session-Backed UI Controller

**Files:**
- Create: `app/services/ui_session_controller.py`
- Modify: `app/services/__init__.py`
- Test: `tests/test_ui_session_controller.py`

- [ ] **Step 1: Add red non-Qt tests for the controller seam**

Seed `tests/test_ui_session_controller.py` with controller-focused tests:

```python
def test_open_profile_with_partial_role_map_keeps_load_diagnostics() -> None:
    ...


def test_open_profile_failure_resets_to_safe_empty_state() -> None:
    ...


def test_role_resolver_exception_resets_to_safe_empty_state() -> None:
    ...


def test_imported_role_resolver_drops_ambiguous_or_duplicate_role_matches() -> None:
    ...


def test_open_profile_exposes_binding_references_for_projected_rows() -> None:
    ...


def test_catalog_entries_are_exposed_from_active_session_snapshot() -> None:
    ...


def test_open_profile_runs_dry_run_export_and_caches_only_unblocked_document() -> None:
    ...


def test_invalid_or_stale_action_selection_is_rejected_with_command_diagnostic() -> None:
    ...


def test_rejected_edit_preserves_last_successful_export_state() -> None:
    ...


def test_move_binding_is_atomic_when_target_bind_is_rejected() -> None:
    ...


def test_move_of_ambiguous_duplicate_name_binding_is_rejected_without_mutation() -> None:
    ...


def test_remove_of_ambiguous_duplicate_name_binding_succeeds_by_identity() -> None:
    ...


def test_controller_reports_mutated_rejected_and_noop_outcomes() -> None:
    ...


def test_controller_replaces_diagnostic_buckets_on_refresh() -> None:
    ...


def test_controller_replaces_only_appended_edit_and_export_diagnostic_slices() -> None:
    ...


def test_controller_collapses_diagnostic_rows_by_record_id() -> None:
    ...


def test_controller_dedupes_diagnostics_without_record_id_by_tuple() -> None:
    ...


def test_controller_normalizes_missing_action_and_side_fields() -> None:
    ...


def test_blocked_conflicts_clear_export_bundle_until_next_success() -> None:
    ...


def test_unexpected_export_failure_clears_cached_export_state() -> None:
    ...


def test_export_without_document_clears_stale_cache_and_surfaces_diagnostics() -> None:
    ...
```

Run: `uv run pytest -o addopts= tests/test_ui_session_controller.py -q`

Expected: FAIL until the controller exists.

- [ ] **Step 2: Keep the controller seam injectable from day one**

Define the controller around injected collaborators:

- `BindingSessionService`,
- imported-role resolver callback or helper,
- button metadata lookup,
- optional logger.

This keeps non-Qt tests fast and avoids using real XML parsing in most UI seam tests.

- [ ] **Step 3: Implement load/open behavior and projected read state**

Controller responsibilities for this step:

- open a profile and capture the active catalog snapshot,
- apply the imported-role resolver with the collision-drop rules from the spec,
- reset to a safe empty state on load failure or resolver exceptions,
- expose session-bound catalog entries and projected rows from the captured session state,
- run the initial dry-run export refresh so validation diagnostics, blocked conflicts, and cached export state reflect the opened session immediately.

- [ ] **Step 4: Implement command outcomes and diagnostic normalization**

Controller responsibilities for this step:

- derive and replace the four diagnostic buckets,
- replace only the appended edit/export diagnostic slices after each command,
- collapse `Diagnostic` and `UnresolvedBinding` rows by `record_id` into a deduplicated merged view,
- fall back to dedupe by `(kind, action, detail, side)` when no `record_id` exists,
- normalize missing structured context into the spec-approved blank or `unknown` action/side fields,
- compute command outcomes from binding snapshots plus appended command diagnostics,
- reject invalid or stale action selections with command diagnostics,
- rebuild projected state after each successful mutation,
- perform create-binding through the session-backed catalog entry, and branch to move-style replacement only when the chosen action already has one renderable binding on that side and trigger mode.

- [ ] **Step 5: Implement export-state caching and exceptional-path handling**

Controller responsibilities for this step:

- preserve the previous export-state bundle on `rejected` and `noop`,
- clear the export-state bundle on blocked or exceptional export,
- clear any stale cached document when the explicit export path returns diagnostics without a document,
- keep blocked conflicts separate from the merged diagnostics table.

- [ ] **Step 6: Run the non-Qt controller lane**

Run: `uv run pytest -o addopts= tests/test_ui_session_controller.py -q`

Expected: PASS.

- [ ] **Step 7: Run both non-Qt UI seam files together**

Run: `uv run pytest -o addopts= tests/test_ui_projection.py tests/test_ui_session_controller.py -q`

Expected: PASS.

- [ ] **Step 8: Commit the controller layer**

```bash
git add app/services/ui_session_controller.py app/services/__init__.py tests/test_ui_session_controller.py
git commit -m "feat: add session-backed ui controller"
```

## Chunk 3: Qt Wiring And Minimal Widget Tests

### Task 6: Convert The Action Picker To Session Catalog Entries

**Files:**
- Modify: `app/components/ui_action.py`
- Modify: `app/ui.py`
- Test: `tests/test_ui_session_controller.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Replace the dialog input contract**

Change `ActionSelectionDialog` to accept the controller-owned/session-bound catalog entries instead of `AllActionMaps`.

At the same time, convert the modifier/hold/multitap controls into a single trigger-mode selector for this slice: selecting one mode clears the other two, and no selected toggle maps to plain.

The dialog still needs:

- grouped display by category,
- translated or display-label-friendly names,
- search over both label and raw action name,
- a returned selection object that preserves `action_name` and optional `actionmap_name`.

- [ ] **Step 2: Add focused widget seam tests for projection-driven add and remove wiring**

In `tests/test_ui.py`, add the smallest seam tests that prove the window hands controller-provided session catalog entries into the picker and refreshes the button grid from controller-projected state after both add and remove operations.

Add tests such as:

```python
def test_trigger_mode_selector_keeps_single_active_mode(main_window: ControlMapperApp) -> None:
    ...


def test_no_trigger_toggle_maps_to_plain_mode(main_window: ControlMapperApp) -> None:
    ...


def test_add_action_refreshes_button_grid_from_projection(main_window: ControlMapperApp, monkeypatch) -> None:
    ...


def test_remove_action_refreshes_button_grid_from_projection(main_window: ControlMapperApp, monkeypatch) -> None:
    ...
```

Run: `uv run pytest -o addopts= tests/test_ui.py -k "trigger_mode_selector or plain_mode or add_action_refreshes_button_grid or remove_action_refreshes_button_grid" -q`

Expected: FAIL before the widget wiring lands.

- [ ] **Step 3: Implement the dialog wiring in `app/ui.py`**

`ControlMapperApp.add_action_to_button()` should:

- derive the active trigger mode from the single selector state,
- ask the controller for the active catalog entries matching the current trigger selection,
- open `ActionSelectionDialog` with those entries,
- dispatch a controller create or move command,
- refresh projected state from the controller result instead of mutating `current_config` directly.

`ControlMapperApp.remove_action_from_button()` should use the same projection-driven refresh path rather than mutating local widget state.

- [ ] **Step 4: Re-run the picker seam test**

Run: `uv run pytest -o addopts= tests/test_ui.py -k "trigger_mode_selector or plain_mode or add_action_refreshes_button_grid or remove_action_refreshes_button_grid" -q`

Expected: PASS, subject to the existing Windows Qt instability.

- [ ] **Step 5: Commit the picker migration**

```bash
git add app/components/ui_action.py app/ui.py tests/test_ui.py
git commit -m "feat: drive action picker from session catalog"
```

### Task 7: Replace Widget-Owned Load And Export State

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Remove the editable default-seeding path from startup**

Replace `set_default_bindings()` as startup state with a no-active-session initialization path.

Startup requirements:

- empty projected joystick configs,
- no cached export document,
- disabled add/remove/save/export actions,
- no default editable overlay.

- [ ] **Step 2: Add focused Qt seam tests for startup and projected load state**

Add tests such as:

```python
def test_main_window_starts_without_active_session(main_window: ControlMapperApp) -> None:
    ...


def test_select_control_map_renders_projected_left_and_right_state(main_window: ControlMapperApp, monkeypatch) -> None:
    ...


def test_select_control_map_keeps_session_with_partial_role_map_diagnostics(main_window: ControlMapperApp, monkeypatch) -> None:
    ...


def test_select_control_map_failure_resets_window_to_safe_empty_state(main_window: ControlMapperApp, monkeypatch) -> None:
    ...
```

Run: `uv run pytest -o addopts= tests/test_ui.py -k "starts_without_active_session or renders_projected_left_and_right_state or partial_role_map_diagnostics or failure_resets_window_to_safe_empty_state" -q`

Expected: FAIL before the load wiring changes.

- [ ] **Step 3: Replace direct XML load mutation and startup state in the window**

Remove or sideline the widget-owned XML path:

- `select_control_map()` should call the controller instead of `get_action_maps_object()`,
- `load_joystick_mappings()`, `process_action_map()`, `process_rebind()`, `apply_default_bindings()`, and `update_control_map()` should no longer own the durable import/export path,
- the window should re-render projected left/right `JoystickConfig` state and unresolved-device diagnostics from controller state,
- failed loads should log the backend failure, show a concise message box, clear stale export state, and return the window to the safe empty disabled state.

- [ ] **Step 4: Add a focused Qt seam test for controller-owned export artifacts**

Add a seam test such as:

```python
def test_export_uses_controller_cached_bundle(main_window: ControlMapperApp, monkeypatch) -> None:
    ...


def test_export_failure_shows_message_and_clears_stale_export_state(main_window: ControlMapperApp, monkeypatch) -> None:
    ...
```

Run: `uv run pytest -o addopts= tests/test_ui.py -k "export_uses_controller_cached_bundle or export_failure_shows_message" -q`

Expected: FAIL before the export wiring changes.

- [ ] **Step 5: Replace direct XML save/export mutation in the window**

Save and export should use the controller’s export-state bundle rather than a widget-owned XML rebuild path.

Unexpected export failures should log the backend failure, show a concise message box, and clear stale export output in the UI.

- [ ] **Step 6: Re-run the focused load/startup/export seam tests**

Run: `uv run pytest -o addopts= tests/test_ui.py -k "starts_without_active_session or renders_projected_left_and_right_state or partial_role_map_diagnostics or failure_resets_window_to_safe_empty_state or export_uses_controller_cached_bundle or export_failure_shows_message" -q`

Expected: PASS, subject to Qt stability.

- [ ] **Step 7: Commit the load/export ownership migration**

```bash
git add app/ui.py tests/test_ui.py
git commit -m "feat: route qt load and export through session controller"
```

### Task 8: Surface Diagnostics And Blocked Conflicts In The Widget

**Files:**
- Modify: `app/ui.py`
- Test: `tests/test_ui.py`
- Test: `tests/test_ui_session_controller.py`

- [ ] **Step 1: Update the unsupported-actions table schema and conflict UI**

Change the current four columns to the planned `Kind / Action / Detail / Side` schema.

Add a separate read-only conflict summary area for blocked passthrough conflicts instead of reusing the diagnostics table. Blocked conflicts must disable both save and export from the same controller export-state gate.

- [ ] **Step 2: Add the focused widget seam tests for diagnostics and conflicts**

Add the minimum Qt tests for:

```python
def test_diagnostics_render_in_generalized_table(main_window: ControlMapperApp, monkeypatch) -> None:
    ...


def test_validation_label_reflects_controller_export_state(main_window: ControlMapperApp, monkeypatch) -> None:
    ...


def test_blocked_conflict_summary_disables_save_and_export(main_window: ControlMapperApp, monkeypatch) -> None:
    ...
```

Run: `uv run pytest -o addopts= tests/test_ui.py -k "diagnostics or validation_label or conflict" -q`

Expected: FAIL before the widget wiring is complete.

- [ ] **Step 3: Implement the widget refresh hooks**

The window refresh path should now:

- pull the four diagnostic buckets from controller state,
- render the merged `UiDiagnosticRow` table,
- render blocked conflicts separately,
- update the validation/save-enabled/export-enabled status from the cached export-state bundle,
- preserve the last successful export-state bundle on rejected/noop commands.

- [ ] **Step 4: Run the focused Qt seam slice**

Run: `uv run pytest -o addopts= tests/test_ui.py -k "diagnostics or validation_label or conflict or trigger_mode_selector or plain_mode or add_action_refreshes_button_grid or remove_action_refreshes_button_grid or starts_without_active_session or renders_projected_left_and_right_state or partial_role_map_diagnostics or failure_resets_window_to_safe_empty_state or export_uses_controller_cached_bundle or export_failure_shows_message" -q`

Expected: PASS when Qt cooperates.

- [ ] **Step 5: Commit the diagnostics/conflict UI wiring**

```bash
git add app/ui.py tests/test_ui.py tests/test_ui_session_controller.py
git commit -m "feat: surface session diagnostics and blocked conflicts in ui"
```

### Task 9: Run The Focused Verification Lane

**Files:**
- Modify: none
- Test: `tests/test_action_catalog_repository.py`
- Test: `tests/test_binding_session.py`
- Test: `tests/test_ui_projection.py`
- Test: `tests/test_ui_session_controller.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Run the full non-Qt focused slice**

Run:

```bash
uv run pytest -o addopts= tests/test_action_catalog_repository.py tests/test_binding_session.py tests/test_star_citizen_profile_repository.py tests/test_ui_projection.py tests/test_ui_session_controller.py tests/test_config.py --ignore tests/test_ui.py -q
```

Expected: PASS.

- [ ] **Step 2: Run lint on the touched files**

Run:

```bash
uv run ruff check app/domain/models.py app/domain/catalog.py app/domain/session.py app/domain/__init__.py app/io/action_catalog_repository.py app/services/binding_session.py app/services/__init__.py app/services/ui_models.py app/services/ui_projection.py app/services/ui_session_controller.py app/components/ui_action.py app/ui.py tests/test_action_catalog_repository.py tests/test_binding_session.py tests/test_ui_projection.py tests/test_ui_session_controller.py tests/test_ui.py
```

Expected: PASS.

- [ ] **Step 3: Run the smallest Qt seam lane separately**

Run:

```bash
uv run pytest -o addopts= tests/test_ui.py -k "trigger_mode_selector or plain_mode or add_action_refreshes_button_grid or remove_action_refreshes_button_grid or starts_without_active_session or renders_projected_left_and_right_state or partial_role_map_diagnostics or failure_resets_window_to_safe_empty_state or export_uses_controller_cached_bundle or export_failure_shows_message or diagnostics_render or validation_label or blocked_conflict_summary" -q
```

Expected: PASS when the local Qt lane cooperates. If Windows COM instability still trips, record that the non-Qt lane is green and preserve the known limitation instead of expanding scope.

- [ ] **Step 4: Commit the verified slice**

```bash
git add app/domain/models.py app/domain/catalog.py app/domain/session.py app/domain/__init__.py app/io/action_catalog_repository.py app/services/binding_session.py app/services/__init__.py app/services/ui_models.py app/services/ui_projection.py app/services/ui_session_controller.py app/components/ui_action.py app/ui.py tests/test_action_catalog_repository.py tests/test_binding_session.py tests/test_ui_projection.py tests/test_ui_session_controller.py tests/test_ui.py
git commit -m "feat: integrate qt ui with headless binding session"
```

## Notes For The Next Plan

- Stable device identity remapping remains the next major milestone after this slice. Do not pull persisted role assignment or hardware repair UX into this plan.
- Action-catalog refresh and `scdatatools` integration remain follow-on work. Do not fold catalog extraction tooling into this UI session slice.

## Plan Review Status

- [x] Chunk 1 reviewed
- [x] Chunk 2 reviewed
- [x] Chunk 3 reviewed