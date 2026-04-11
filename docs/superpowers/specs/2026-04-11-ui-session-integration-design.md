# CitizenBindVkb UI Session Integration Design

## Goal

Integrate the existing Qt UI with the new headless binding session core so that profile load, edit validation, diagnostics, passthrough conflict detection, and export all run through one authoritative backend while preserving the current button-grid workflow.

## Problem Statement

The headless core now owns the durable import/edit/export model, but [app/ui.py](app/ui.py) still parses Star Citizen XML directly, rebuilds joystick mappings itself, and constructs export XML from widget-owned state. That leaves two competing truths in the application:

- the new session/repository layer,
- the legacy `JoystickConfig` and XML rewrite path inside the window.

As long as the widget owns load and export logic, the UI can diverge from the headless engine, diagnostics are only partially trustworthy, and passthrough conflicts cannot be surfaced reliably.

## Scope

### In Scope

- make the headless binding session the authority for profile load, bind, unbind, validation, conflict detection, and export,
- keep the current Qt button grid and action table as the visible interaction model,
- preserve `JoystickConfig` as a derived render projection only,
- surface session diagnostics and unresolved bindings in the existing UI,
- surface blocked passthrough conflicts in the UI and block export while they remain unresolved,
- keep the current joystick-side heuristic only as a temporary imported-role map input.

### Out Of Scope

- full direct UI rendering from session-native models,
- full passthrough conflict resolution controls such as `replace_passthrough()` and `preserve_passthrough()` buttons,
- stable hardware identity and persisted role assignment,
- major Qt layout redesign,
- expansion of the unstable Windows UI test lane beyond the smallest necessary seam coverage.

## Approaches Considered

### 1. Backend Swap On Load/Export Only

Keep the existing widget-owned edit model and call the headless core only when loading or exporting.

Pros:

- smallest immediate diff,
- low risk of breaking the button grid.

Cons:

- preserves two competing binding models,
- diagnostics and conflicts are not fully authoritative,
- edit behavior can still diverge from export behavior.

### 2. Headless Session As Authority, `JoystickConfig` As Projection

Use the headless session for all profile mutations and export behavior, but rebuild the existing `JoystickConfig` structures from session state so the current UI can keep rendering through the button grid and action table.

Pros:

- creates one authoritative backend path,
- keeps the current UI mostly intact,
- exposes diagnostics and passthrough conflicts immediately,
- keeps the first UI slice bounded.

Cons:

- introduces temporary duplication through projection code,
- requires careful translation between session bindings and legacy UI models.

### 3. Full Session-Native UI Rewrite

Replace the existing `JoystickConfig` rendering path and drive the UI directly from session-native models.

Pros:

- cleanest long-term shape,
- removes the legacy projection layer immediately.

Cons:

- too much surface area for the first integration slice,
- mixes architecture migration with broad UI behavior change,
- increases risk in the already unstable Qt lane.

### Decision

Choose approach 2: make the headless session authoritative while retaining `JoystickConfig` as a projection for the existing UI widgets.

## Architecture Overview

The window should stop owning Star Citizen profile parsing and export document mutation. Instead, it becomes a client of the session service.

The first integration slice introduces three layers inside the Qt shell:

1. Session authority: [app/services/binding_session.py](app/services/binding_session.py) and the repositories own load, bind, unbind, diagnostics, conflict detection, and export.
2. UI projection: a focused adapter translates session bindings and diagnostics into the current `JoystickConfig`, unsupported-actions table rows, validation label state, and export-ready status.
3. Widget rendering: the existing button grid, action panel, combo box, and message boxes render from projected state and invoke session commands.

The key rule is simple: `JoystickConfig` is no longer edited as the primary source of truth. After each user action, the UI re-projects from the current session.

The one temporary exception is joystick-side inference for imported `jsN` tokens, but that logic must move behind a helper/controller seam outside the widget. The window may request an imported role map for a profile path, but it should not parse XML directly to derive that mapping.

The no-active-session state is also explicit for this slice:

- startup begins with no active session,
- projected joystick configs are empty until `open_profile()` succeeds,
- add, remove, save, and export actions are disabled until a session is active,
- the existing widget-side default binding seeding and post-load default overlay are removed from editable state for this slice rather than being kept as a second mutable truth.

## Components

### Session-Backed UI Controller

The window needs a small internal controller boundary responsible for:

- resolving the temporary imported role map for a profile path,
- opening a selected profile through the session service,
- storing the active `BindingSession`,
- exposing projected renderable binding rows that carry backing session identity,
- exposing identity-aware row edit commands to the widget,
- returning explicit command outcomes for UI-triggered edits,
- requesting dry-run export state after edits,
- exposing a current export document only when export is unblocked.

This can live initially inside [app/ui.py](app/ui.py) if kept focused, but the logic should be written as a distinct cluster of methods rather than spread across existing XML helpers.

For testing, this controller boundary must be injectable. The widget should be able to run against a fake or stubbed controller/service so UI tests do not need to drive real XML parsing and repository state through Qt just to verify status rendering.

The controller result contract is explicit for this slice:

- `mutated`: session state changed and a fresh dry-run export is required,
- `rejected`: session state did not change and the command produced command diagnostics,
- `noop`: session state did not change and the command produced no new command diagnostics.

The UI-to-controller edit surface is row-identity-aware in this slice. Renderable rows are edited through controller commands equivalent to:

- `remove_binding(binding_ref)`,
- `move_binding(binding_ref, target_slot)`.

Those may be implemented by new service methods or by a focused controller layer on top of the current service surface, but the widget contract is identity-aware either way.

Opening a profile also captures the exact catalog snapshot or catalog version key used for that session. The action picker must be derived from that session-bound catalog view rather than any global action table.

That session-bound catalog view must be explicit for this slice. It exposes entries keyed by `(action_name, actionmap_name_or_none)` and each entry provides at least:

- `action_name`,
- `actionmap_name`,
- `category`,
- `subcategory`,
- `supports_joystick`,
- `supported_trigger_modes`,
- `display_label`.

Both picker contents and provenance-aware `JoyAction` metadata projection must use that view instead of name-only inference or legacy global action tables.

### Imported Role Map Resolver

The existing joystick-side heuristic remains acceptable for this slice, but it must become a helper owned by the controller boundary rather than by widget load code.

Requirements:

- input: profile path plus current config heuristics,
- output: imported role map in the shape expected by `open_profile()`,
- partial-match behavior: unmatched or ambiguous joystick tokens must produce a partial role map rather than aborting load so the session can surface `unresolved-device` diagnostics,
- collision rule: only unique token-to-role assignments are kept; any ambiguous token match or role collision is dropped instead of being resolved heuristically,
- hard-failure behavior: malformed profile input, unreadable files, or unexpected resolver exceptions use the same load error path as session startup,
- no widget-local XML mutation or parsing side effects.

### Projection Layer

The projection layer translates the active session into the current UI state shape:

- `BindingEdit` to `JoyAction`,
- grouped left/right `BindingEdit` values to `JoystickConfig`,
- session `Diagnostic` and `UnresolvedBinding` values to unsupported-action rows and status text,
- projection-only problems such as overflowed bindings or non-renderable bindings into a dedicated projection-diagnostics bucket,
- `ExportResult.blocked_conflicts` to a blocked-export state and visible conflict summary.

This projection is intentionally one-way in this slice. The UI does not mutate projected state directly and expect it to be durable.

#### Projection Contract

This slice supports only session roles `left_stick` and `right_stick` for projection into the current joystick UI.

The first-slice projection invariant is also explicit: the legacy button-grid projection supports at most one renderable binding per `(side, action_name, trigger_mode)` combination because the current `JoystickConfig` keying cannot preserve multiple slot placements for the same action and trigger on one side. If the session contains additional bindings that collide under that invariant, the renderable binding is chosen deterministically by sorting the colliding candidates on the normalized binding snapshot tuple and selecting the first sorted entry. Every non-selected binding is surfaced as a non-editable diagnostic row instead of being silently overwritten.

Every renderable button or action-table row must be backed by a projected binding view model that carries the identity needed to address the underlying session binding deterministically. At minimum, that projected row identity includes the same normalized fields used in the binding snapshot contract plus source record identity when available. Remove and move operations must target that projected binding identity rather than only an action name.

Mappings are explicit:

- `left_stick` -> `left` UI side,
- `right_stick` -> `right` UI side,
- `TriggerMode.PLAIN` -> `modifier=False`, `hold=False`, `multitap=False`,
- `TriggerMode.MODIFIER` -> `modifier=True`, `hold=False`, `multitap=False`,
- `TriggerMode.HOLD` -> `modifier=False`, `hold=True`, `multitap=False`,
- `TriggerMode.MULTITAP` -> `modifier=False`, `hold=False`, `multitap=True`.

The reverse mapping from the current three toggle controls back to session trigger mode must also be explicit. The toggles remain visible, but they behave as a single-mode selector in this slice:

- no toggles selected -> `plain`,
- modifier selected -> `modifier`,
- hold selected -> `hold`,
- multitap selected -> `multitap`,
- multiple toggles selected simultaneously are not allowed; enabling one must disable the other two.

The action picker must filter against the active session catalog snapshot:

- only actions that support joystick binding are shown,
- only actions compatible with the currently selected trigger mode are shown when that compatibility can be derived from catalog metadata,
- ambiguous duplicate-name actions are filtered as described below,
- if an invalid action still reaches the controller, the resulting command outcome is `rejected` with command diagnostics rather than a mutation.

The projection layer must recover UI-only metadata as follows:

- action category and subcategory come from the loaded action catalog by the pair of action name and source actionmap provenance when provenance exists,
- button metadata comes from the existing `joystick_buttons_by_slot` lookup already used by the UI,
- if a session binding references a slot that cannot be rendered as a known `JoyStickButton`, the binding is omitted from the projected button grid and surfaced as a diagnostic row instead of failing silently.

If action metadata lookup is still ambiguous or missing even with provenance, the binding is omitted from editable projection and surfaced as an `ambiguous-actionmap` or equivalent diagnostic row instead of guessing.

This keeps validation and export authoritative in the headless core while acknowledging that the current UI still depends on richer VKB button-display metadata than `BindingEdit` carries.

#### Ambiguous Duplicate-Name Actions

Some Star Citizen actions exist in multiple actionmaps and cannot be safely created from action name alone.

Rules for this slice:

- imported bindings that already carry source actionmap provenance remain projectable and visible in the current UI,
- those imported ambiguous bindings are removable in this slice but not movable to a different button because the current add-action and bind surfaces do not carry provenance for a new placement,
- the add-action flow must not create a brand-new binding for an ambiguous duplicate-name action without provenance,
- the action picker is derived from the active session catalog or a controller-owned catalog projection, not from legacy global action tables,
- the simplest allowed UX in this slice is to hide ambiguous duplicate-name actions from the add-action dialog,
- if the UI does expose them, it must do so with actionmap-qualified labels and still refuse creation unless provenance is carried through explicitly.

This keeps the UI aligned with the current headless validation behavior instead of reintroducing unsafe action inference.

### Export State Cache

The current app writes XML eagerly inside `update_control_map()`. That should be replaced with a cached export state built from `BindingSessionService.export()`.

Rules:

- if export succeeds, cache the returned `document` as the current export artifact,
- if export returns blocked conflicts, clear the cached export artifact and surface the conflict state,
- if export returns diagnostics without a document, show the failed state and do not present stale XML as current.

Cache invalidation, conflict refresh, and displayed diagnostic refresh must happen atomically after each edit so the UI never shows a stale export document with fresh errors or vice versa.

## Data Flow

### Load Flow

1. User selects a profile in the combo box.
2. The session-backed controller resolves the imported joystick-instance-to-role map through the temporary heuristic helper.
3. The window opens the profile through [app/services/binding_session.py](app/services/binding_session.py) with that imported role map.
4. The active session is stored on the window.
5. The projection layer rebuilds `left_joystick_config`, `right_joystick_config`, diagnostics, unsupported rows, and status labels from the session.
6. The window refreshes the existing button grid and action panel from the projected state.
7. The window performs a dry-run export and caches the current export document if unblocked.

### Edit Flow

1. User adds or removes an action through the existing button-grid workflow.
2. The window converts that request into identity-aware controller commands such as `remove_binding(binding_ref)` or `move_binding(binding_ref, target_slot)`.
3. The controller returns an explicit command outcome of `mutated`, `rejected`, or `noop` using the snapshot and command-diagnostic rules defined below.
4. The window rebuilds the projected joystick configs and diagnostics from the current session.
5. Only if the command outcome is `mutated` does the window run a dry-run export.
6. If export is valid, the cached export document updates and the validation/conflict state clears.
7. If export is blocked, the cached export document is cleared and the UI reflects the conflict state.
8. If the command outcome is `rejected`, the command-diagnostic bucket updates but the last successful export artifact remains current.
9. If the command outcome is `noop`, the UI preserves the last successful export artifact and does not add new command diagnostics.

Add-action behavior also remains explicit for this slice: when the user selects an action already represented by a renderable projected binding for the same side and trigger mode, the controller performs a move-style replacement against that projected binding identity. The move must be atomic for this slice: the target bind is prevalidated before removing the old binding, and if the bind step is rejected or raises unexpectedly the original binding remains or is restored and the overall command outcome is `rejected`, not `mutated`. Overflowed non-renderable bindings do not participate in this automatic move path. Ambiguous duplicate-name bindings are also excluded from this automatic move path even if they are renderable; in this slice they remain viewable and removable only.

### Export Flow

1. When the user requests export or save, the window uses the cached export state if it exists.
2. If the session is blocked by passthrough conflicts or validation issues, the UI does not write XML and instead shows the blocking details.
3. If export is valid, the compatibility save path can still be used for this slice, but it must write the document produced by the session-backed export path rather than rebuilding XML inside the widget.

## Diagnostics And Conflict UX

### Diagnostics

The existing unsupported-actions table becomes a generalized import and validation summary driven from the session.

It should surface at least:

- unknown actions,
- unknown slots,
- unresolved imported device tokens,
- any other session diagnostics returned after edits or export validation.

The current validation label continues to exist, but its value comes from session/export state rather than only from `BindingPlanner` output generated inside the widget.

#### Diagnostic Lifecycle

Displayed diagnostics must be treated as snapshot state, not an append-only log.

The UI controller should maintain four buckets:

- load diagnostics: captured from `open_profile()` and refreshed only when a new profile is opened; unresolved bindings are part of this bucket,
- command diagnostics: replaced after each bind, unbind, or other edit command,
- validation diagnostics: replaced completely after each dry-run export,
- projection diagnostics: rebuilt from scratch on every projection refresh.

The user-visible diagnostics view is the deduplicated merge of all four buckets. When an edit removes the condition that caused a validation issue or conflict, that issue disappears on the next refresh rather than lingering in the UI.

Because the current backend stores diagnostics in one mutable list, the controller must define bucket extraction explicitly for this slice:

- on load: capture the full initial session diagnostics plus unresolved bindings as the load bucket,
- on edit command: snapshot the diagnostics length before and after the service call and use only the newly appended slice as the command bucket replacement,
- on dry-run export: snapshot the diagnostics length before and after export and use only the newly appended slice as the validation bucket replacement.

Projection diagnostics are not backend-derived. They are rebuilt on every projection refresh from conditions such as:

- overflowed bindings that cannot fit the renderable projection invariant,
- bindings whose slot cannot be rendered as a `JoyStickButton`,
- provenance-aware metadata lookups that remain ambiguous or missing.

This snapshot-diff rule is the required contract unless the backend is extended later to return per-operation result objects directly.

The controller must also compute a `changed` flag for each edit by comparing pre-command and post-command binding snapshots. That flag controls whether a new dry-run export occurs.

The snapshot shape is exact for this slice. Each binding snapshot entry includes:

- `role`,
- `slot_id`,
- `action_name`,
- `trigger_mode`,
- `modifier_token`,
- `source_actionmap_name`,
- `replaced_passthrough_record_id`.

Any difference in that normalized binding snapshot counts as a state change for conditional dry-run export.

Command outcomes derive from that snapshot plus the appended command-diagnostic slice:

- snapshot changed -> `mutated`,
- snapshot unchanged and appended command diagnostics exist -> `rejected`,
- snapshot unchanged and no appended command diagnostics exist -> `noop`.

Update semantics are explicit:

- opening a new profile replaces all four buckets,
- a successful edit command clears the previous command-diagnostic bucket unless the command intentionally returns new diagnostics,
- a failed edit command replaces only the command-diagnostic bucket because the session state did not advance,
- only successful mutating commands trigger a fresh dry-run export,
- a dry-run export replaces the validation bucket and blocked-conflict state atomically.

If the current service implementation still appends validation diagnostics into session state internally, the controller layer must isolate the latest validation subset instead of blindly reusing the full accumulated list.

The user-visible diagnostics view is the deduplicated merge of the four buckets. The cached export document remains valid after a failed edit command that did not mutate session state, but it must be cleared immediately on blocked or exceptional export paths.

#### Diagnostic Table Schema

A small schema change to the current unsupported-actions table is allowed in this slice.

The four columns should become:

- `Kind`,
- `Action`,
- `Detail`,
- `Side`.

The backing row model must be normalized explicitly as `UiDiagnosticRow(kind, action, detail, side, record_id)`.

Normalization rules:

- `Diagnostic` rows use `code` as `kind`, the best available structured action context as `action` when available or blank otherwise, the message as `detail`, the inferred UI side when available or `unknown` otherwise, and `record_id` when present,
- `UnresolvedBinding` rows normalize to `kind=reason`, `action=action_name`, `detail` derived from the unresolved token and slot context, `side=unknown`, and `record_id=record_id`,
- when both a `Diagnostic` and an `UnresolvedBinding` refer to the same `record_id`, render only one row using the `Diagnostic` as the primary row and unresolved data only as supplemental context,
- otherwise dedupe by `(record_id)` when available, or by `(kind, action, detail, side)` when no record id exists.

The controller must not parse free-form diagnostic messages to invent missing action or side data. Blank or `unknown` cells are acceptable when the backend does not provide structured context.

Examples:

- `unknown-action | v_unknown_custom_action | action not present in catalog | right`,
- `unknown-slot | v_emergency_exit | slot unknown_button is not renderable | right`,
- `unresolved-device | v_emergency_exit | imported token js2 could not be matched | unknown`.

### Passthrough Conflicts

The first slice should show blocked passthrough conflicts clearly but keep the resolution UX simple.

Behavior:

- conflicting edits are allowed to exist in session state,
- dry-run export exposes `blocked_conflicts`,
- the UI shows a blocked state and a compact list of conflicts,
- export/save is blocked while conflicts remain,
- the only supported first-slice recovery path is to change or remove the editable binding through the normal button-grid workflow,
- no interactive conflict-resolution controls are added in this slice.

This is deliberate scope control: the UI must stop hiding the problem before it starts solving the whole conflict-resolution workflow.

Blocked conflicts should not share the diagnostics table. They should render in a separate read-only summary area so the user can distinguish import/validation problems from export-blocking passthrough collisions.

## Error Handling

Load errors remain user-visible message boxes, but the failure source becomes repository/session startup rather than widget-local parsing.

After a failed load attempt, the UI must reset to a safe empty state:

- clear the active session,
- clear projected joystick configs,
- clear all diagnostic buckets,
- clear blocked-conflict state,
- clear the cached export artifact,
- disable save/export until a successful load completes.

Export errors follow three rules:

- no cached document if export is blocked,
- rejected edit commands update command diagnostics only and leave the last successful export artifact intact because session state did not change,
- no cached document after a blocked or exceptional export attempt,
- visible blocking reason through diagnostics or conflict summaries.

The UI should log detailed backend failures and show a concise user-facing message when startup or export raises an unexpected exception.

## Testing Strategy

### Headless Lane

Do not broaden the headless milestone responsibilities. Existing non-UI tests continue to verify repository and session correctness.

### UI Lane

Add only focused Qt seam tests in [tests/test_ui.py](tests/test_ui.py):

- loading a profile populates projected left/right joystick state from a session-backed load,
- loading with a partial imported role map still opens the session and surfaces unresolved-device diagnostics,
- session diagnostics are reflected in the unsupported-actions UI,
- a conflicting edit produces a blocked export state in the UI rather than a valid export document,
- add/remove action workflows continue to update the button grid through the projection path.

Because of the known Windows Qt instability, keep the UI lane as small as possible and avoid using it to re-prove repository behavior already covered in headless tests.

Most of the new behavior should be tested outside Qt. The controller and projection boundary must be callable with stubbed `BindingSessionService` responses and canned export results so:

- projection mapping tests can run as non-Qt unit tests,
- projection-overflow behavior for colliding same-action bindings can be tested without a widget,
- deterministic collision precedence for projected bindings can be tested without a widget,
- partial-role-map load behavior can be tested without a widget,
- ambiguous duplicate-name action filtering can be tested without a widget,
- session-catalog-driven picker contents can be tested without a widget,
- diagnostic snapshot behavior can be tested without a widget,
- load failure and resolver exception handling can be tested without a widget,
- unexpected export failure and export-cache clearing can be tested without a widget,
- rejected edit commands can be tested without a widget with assertions for unchanged export cache plus refreshed command diagnostics,
- atomic move-style replacement can be tested without a widget with a rejected target bind,
- blocked-conflict recovery through ordinary unbind or rebind can be tested without a widget,
- picker contents must be tested against the active session catalog rather than static globals,
- Qt tests only need to prove widget wiring, label state, and table rendering.

## Risks And Mitigations

### Risk: Projection Drift

If the projection from session bindings to `JoyAction` diverges from legacy expectations, the button grid can render incorrectly.

Mitigation:

- keep projection logic focused and one-way,
- cover projection-sensitive cases in targeted UI tests,
- do not let the widget mutate projected state directly.

### Risk: Partial Backend Adoption

If some UI actions still mutate XML directly while others use the session service, the app becomes harder to reason about than before.

Mitigation:

- remove or isolate direct XML mutation from the first slice,
- require load, bind, unbind, and export to all go through the session path.

### Risk: Oversized First Slice

Adding interactive conflict resolution now would expand the scope sharply.

Mitigation:

- surface conflicts now,
- defer resolution controls to the next UI slice.

## Follow-On Priorities

Two adjacent areas remain strategically important even though they are outside this first UI-integration slice.

### Stable Device Remapping

This remains a critical next milestone. The current repo can enumerate physical devices and their GUIDs through [app/utils/devices.py](app/utils/devices.py), but the active app and current headless slice still rely on imported `jsN` tokens plus joystick-side heuristics rather than persisted stable identity remapping.

That means the current implementation is not yet good enough for the failure mode where Star Citizen inverts device order or drops one detected device and the user should be able to recover bindings without rebinding everything.

The follow-on implementation should:

- persist stable device-role assignments,
- match imported or observed devices by stable identity before using fallback heuristics,
- surface ambiguity explicitly in the UI,
- let the user repair a broken mapping once instead of rebinding individual actions.

### Action Catalog Extraction And Refresh

The repo already contains a partial developer-side extraction path in [app/dev_tools/export_configmap.py](app/dev_tools/export_configmap.py), which uses `scdatatools.sc` to generate versioned `actionmap.json` files under the app data tree. The new [app/io/action_catalog_repository.py](app/io/action_catalog_repository.py) can load those versioned catalog files once they exist.

What is still missing is productized workflow and UI support:

- `scdatatools` is not currently a managed runtime dependency in [pyproject.toml](pyproject.toml) or [requirements.txt](requirements.txt),
- the extraction flow is not wired into the UI,
- there is no explicit catalog-refresh UX for LIVE/PTU updates,
- there is no user-facing display of which catalog version a session is using.

The follow-on implementation should decide whether catalog refresh is:

- a manual developer CLI,
- an optional advanced in-app import tool,
- or a fuller game-integrated refresh workflow.

Regardless of product choice, the UI should eventually expose the active catalog version and make version refresh safer and more visible when Star Citizen updates.

## Exit Criteria

This design slice is complete when all of the following are true:

- the active profile is opened through the headless session service,
- the button grid and action panel render from a session-derived projection,
- add/remove actions mutate the session rather than the widget-owned XML model,
- diagnostics and unresolved bindings are visible in the UI,
- blocked passthrough conflicts are visible and prevent export,
- the current export artifact comes from the session-backed export path,
- the minimal focused UI tests for the new seam pass outside the known Windows-specific instability constraints.