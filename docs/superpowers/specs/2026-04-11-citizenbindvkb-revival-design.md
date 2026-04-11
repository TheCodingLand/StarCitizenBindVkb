# CitizenBindVkb Revival Design

## Goal

Revive CitizenBindVkb as a durable offline rebinding tool for Star Citizen that can:

- import exported Star Citizen control profiles,
- match imported joystick bindings to stable physical device identities,
- let the user edit supported bindings visually,
- preserve unknown or unsupported data instead of dropping it,
- export valid profiles that remain usable when joystick ordering changes.

The first milestone targets a generic binding core with VKB-specific adapters and layouts on top.

## Problem Statement

The current project is close to the desired user experience, but the core responsibilities are still mixed together:

- the Qt UI owns import, export, translation, and validation logic,
- there are two overlapping binding models,
- joystick side detection depends on fragile instance-number and name heuristics,
- Star Citizen action data is version-pinned and loaded as global startup data,
- the new domain and service layer exists only partially and is not yet the source of truth.

This makes each Star Citizen update and each device ordering change risky, because game data handling, device identity, and UI state are not cleanly separated.

## Scope

### In Scope For The Revival Foundation

- a headless binding core that owns all editable binding state,
- stable device identity and device-role matching,
- Star Citizen import and export through dedicated repositories and adapters,
- preservation of unknown bindings and unsupported inputs,
- VKB layouts and VKB-focused UI support as the first adapter layer,
- migration of the existing Qt shell to use the new core.

### Out Of Scope For The First Milestone

- broad multi-device support from day one,
- major UI redesign work,
- advanced preset sharing features,
- broad packaging polish before the core engine is stable.

## Approaches Considered

### 1. Generic Core With VKB Adapters First

This approach builds a hardware-agnostic binding engine, then supplies VKB layouts, role matching, and UI affordances as adapter layers.

Pros:

- fixes the architectural root cause,
- keeps the first milestone focused,
- creates a path to future device support without rewriting the core.

Cons:

- slightly slower than a pure VKB-only cleanup,
- requires explicit modeling of device identity and unknown data.

### 2. VKB-Only End To End

This approach would clean up the current app while keeping most assumptions VKB-specific.

Pros:

- faster to get back to a working niche tool,
- lower immediate modeling cost.

Cons:

- leaks hardware assumptions into the core,
- does not solve the longer-term maintainability issue,
- makes future expansion harder.

### 3. Multi-Device From Day One

This approach attempts to generalize the tool for many device families immediately.

Pros:

- ambitious long-term framing,
- could avoid VKB-specific cleanup later.

Cons:

- too broad for a stable first revival milestone,
- high risk of stalling before a usable release,
- increases test surface before the basic architecture is trusted.

### Decision

Choose approach 1: generic core with VKB adapters first.

## Architecture Overview

The revived system should be organized around a single headless core. The UI should become a client of that core rather than the place where parsing, matching, rebinding, and export rules live.

There are three core truths in the system:

1. Game action catalog: what Star Citizen actions exist and how they are identified.
2. Physical device identity and logical layout: what hardware is present and how user-facing roles map to physical devices.
3. Editable binding state: which logical game actions are bound to which logical device inputs.

Only the core owns those truths. Adapters translate between those truths and external formats such as Star Citizen XML, VKB layout metadata, and hardware discovery APIs.

## Domain Model

The long-term source of truth should be the domain model, not the current UI-centric joystick model.

### Game Concepts

- `GameActionId`: stable identifier for a Star Citizen action.
- `GameActionDefinition`: action metadata, labels, categories, supported trigger modes, and version provenance.
- `GameCatalogVersion`: identifies the imported action-map source version.

### Device Concepts

- `DeviceIdentity`: stable description of a physical controller, based on hardware-level identifiers such as GUID, product information, and normalized metadata.
- `DeviceRole`: user-facing role such as `left_stick`, `right_stick`, `throttle`, or `aux`.
- `DeviceLayout`: logical slots available for a given device family or role, for example `button1`, `hat1_up`, or axis inputs.
- `SlotId`: logical input slot name independent of Star Citizen instance numbering.

### Binding Concepts

- `TriggerMode`: normalized trigger semantics instead of separate UI booleans. This should represent plain press, modifier, hold, multitap, and future extensions cleanly.
- `Binding`: one action assigned to one device role and one logical slot with one trigger mode.
- `WorkingProfile`: editable set of bindings plus metadata about import source, unresolved items, and diagnostics.

### Compatibility Concepts

- `UnresolvedBinding`: imported data that could not be confidently mapped into the editable model.
- `PassthroughRecord`: imported Star Citizen data that must survive export unchanged even if the app cannot interpret it.
- `Diagnostic`: structured issue surfaced to the UI, such as unknown action, unknown slot, ambiguous device match, or export conflict.

### Persistence Concepts

- `DeviceRoleAssignment`: persisted mapping from a stable device identity to a user-facing device role.
- `SessionSnapshot`: persisted non-export state such as the currently opened profile path, unresolved-role choices, and other recovery metadata when needed.

## Service Boundaries

### Binding Session Service

This is the main application service. It should:

- open a profile from imported game data,
- expose current bindings and diagnostics,
- support bind, unbind, move, and replace operations,
- validate conflicts before export,
- produce an export plan or final export artifact.

The Qt application should only render session state and invoke commands on this service.

#### Session Mutation Contract

Milestone 1 does not require event sourcing or undo. The service may mutate an in-memory session object, but all state transitions must happen through explicit command methods so they remain testable.

Required command surface:

- `bind(role, slot, action, trigger_mode)`
- `unbind(role, slot, trigger_mode)`
- `replace_passthrough(conflict_id, replacement_binding)`
- `preserve_passthrough(conflict_id)`
- `discard_pending_edit(conflict_id)`
- `assign_device_role(device_identity, role)`
- `resolve_unmatched_device(imported_device_token, role)`
- `export()`

Each command should return updated diagnostics or an updated session view.

### Device Matching Service

This service should:

- discover currently attached devices,
- normalize their identities,
- match them to stored user roles,
- explain ambiguity instead of silently guessing.

Imported `js1`, `js2`, and similar Star Citizen instance numbers are only temporary input data. They are not the canonical identity model.

#### Matching Algorithm

The matching pass must be deterministic and explicit.

1. Build `ObservedDevice` values from the current hardware discovery layer. Each value should include stable hardware metadata such as GUID, normalized product name, and any other identifiers available from the platform.
2. Load persisted `DeviceRoleAssignment` records.
3. Attempt exact match by stable identity key.
4. If no exact match exists, attempt a constrained fallback match by device family metadata only when there is exactly one unassigned observed device that satisfies the expected role profile.
5. If multiple devices are plausible matches, do not choose automatically. Emit an ambiguity diagnostic and require explicit user assignment.
6. If no plausible match exists, leave the role unresolved and emit a missing-device diagnostic.

Confidence rules:

- exact persisted identity match: confident,
- single unique constrained fallback: conditionally confident and should be recorded as a new assignment only after user confirmation or an explicit product decision,
- multiple plausible matches: not confident,
- no plausible match: not confident.

Example:

- persisted assignment says GUID `{abc}` is `left_stick`,
- current hardware contains device with GUID `{abc}`,
- the service matches it directly to `left_stick` and records no ambiguity.

### Catalog Repository

This repository should load Star Citizen action catalog data as versioned content rather than module-level globals. It should support loading the current bundled catalog and, later, alternate versions.

### Layout Repository

This repository should load device layouts and slot metadata. VKB layouts are the first supported implementation, but the repository contract should not be VKB-specific.

### Star Citizen Profile Repository

This repository should own XML import and export. It should translate between raw Star Citizen control maps and the domain-layer working profile plus passthrough records.

### Persistence Service

This service should own small durable application state that is not itself a Star Citizen export file.

It should persist at least:

- device-role assignments,
- user confirmation for ambiguous matches when explicitly accepted,
- lightweight session metadata where recovery across app restarts is useful.

The first implementation can use a JSON file in the application data directory. SQLite is not required for milestone 1.

Persistence timing rules:

- device-role assignments are persisted immediately after explicit user confirmation,
- session snapshots are persisted on explicit save and may also be checkpointed after important user-confirmed resolution steps,
- Star Citizen export files remain separate from app persistence.

## Data Flow

### Import Flow

1. Load raw Star Citizen profile XML.
2. Load the relevant action catalog version.
3. Extract imported joystick bindings and non-joystick passthrough data.
4. Match imported Star Citizen joystick instances to stable device identities and then to device roles.
5. Convert supported bindings into domain `Binding` objects.
6. Preserve unknown or unsupported data as unresolved bindings or passthrough records.
7. Return a `BindingSession` state with diagnostics.

### Edit Flow

1. UI reads the current binding session state.
2. UI issues commands such as bind, unbind, or swap.
3. Core validates and updates the working profile.
4. UI re-renders from the latest session state.

### Export Flow

1. Core validates the working profile.
2. Core rewrites only the records it understands for resolved device roles.
3. For resolved roles, core emits Star Citizen instance numbers from the current device-role assignment table rather than from the imported `jsN` values.
4. Unknown devices, passthrough data, and unresolved sections are preserved unless the user explicitly removes them.
5. If an unresolved or passthrough record would collide with a rewritten resolved-role record on instance token, slot token, and trigger semantics, export must stop with a diagnostic instead of guessing.
4. Export repository emits a valid Star Citizen control profile.

### Instance Number Re-Emission Rules

Resolved editable bindings are exported using the current Star Citizen instance tokens assigned to their matched device roles for this export operation.

Unresolved or passthrough records follow these rules:

- if they belong to an unresolved imported device, they retain their original imported instance token,
- if that original token would collide with a resolved rewritten record, export is blocked until the user resolves the conflict,
- unresolved records must never be silently reassigned to a different instance token,
- passthrough preservation is preferred over silent renumbering.

### Preservation Semantics

The importer must classify raw Star Citizen records into one of three buckets:

1. editable bindings: fully understood and mapped into the domain model,
2. unresolved bindings: partially understood records that the UI can present for user intervention but cannot safely normalize yet,
3. passthrough records: raw records that must be preserved byte-for-byte or field-for-field because the tool cannot safely represent them.

Rules:

- unknown action identifiers default to passthrough records with a linked diagnostic;
- unknown slot encodings default to passthrough records with a linked diagnostic;
- partially understood bindings may also create unresolved views for UX purposes, but passthrough remains the export authority until the user explicitly resolves or replaces the record;
- unresolved views alone are not enough to guarantee round-trip preservation.
- when a previously unknown action becomes fully understood under the currently loaded catalog, import may promote it from passthrough-backed unresolved state into an editable binding only if action identity, slot identity, and trigger semantics are all understood without ambiguity; otherwise it remains passthrough-backed.

### Passthrough Conflict Resolution

Passthrough records must be tracked with enough identity to detect overlap with editable bindings. At minimum, the repository must key them by imported action identifier, imported device instance token, imported slot token, and trigger/modifier encoding.

If a user edits a binding that resolves to the same logical target as an existing passthrough record:

1. the session must mark the overlap as a conflict,
2. the UI must require explicit replacement or explicit preservation,
3. export must never silently emit both records when they target the same logical slot and trigger semantics,
4. if the user chooses replacement, the passthrough record is removed and replaced by the normalized editable binding,
5. if the user chooses preservation, the edit is rejected or kept pending until the conflict is cleared.

Conflict clearing options are explicit:

- replace the passthrough record with the new editable binding,
- discard the pending edit and keep the passthrough record,
- remap the unresolved device or role so the overlap no longer exists,
- explicitly delete the passthrough record if the product allows destructive cleanup in that workflow.

## Error Handling And Compatibility Rules

Unknown game data should not be fatal by default.

If a new Star Citizen patch introduces actions, categories, localization changes, or input patterns the app does not know yet, import should degrade gracefully:

- supported bindings become editable domain bindings,
- unsupported or unrecognized bindings become unresolved items,
- untouched raw records become passthrough records that survive export.

The export rule is strict: normalize only what the tool understands, preserve everything else.

Device mismatches should follow the same rule. When imported joystick instances cannot be confidently matched to the user’s current hardware, the profile should load with explicit diagnostics. The tool must not silently invent left or right assignments beyond one well-defined matching pass.

Unknown actions should survive export through passthrough storage even when they also surface in the UI as unresolved items. If the user never explicitly resolves or replaces those bindings, export must re-emit them unchanged.

Unknown trigger or modifier encodings should be treated the same way. If the tool cannot normalize a trigger combination into a supported `TriggerMode`, the raw record remains passthrough-backed and survives export unless explicitly replaced.

For unmatched devices:

- imported records for that device remain preserved,
- they surface as unresolved items attached to an unresolved device role,
- the user may explicitly remap the unresolved device to a known role,
- unresolved bindings are not edited in place as normalized bindings until the role is resolved,
- the UI should present a resolve-or-replace workflow rather than free-form direct editing of unresolved records,
- until such remapping happens, the exporter keeps those records in passthrough form.

Import failure rules:

- invalid XML or structurally unreadable files are fatal import errors,
- semantic gaps such as unknown actions, unknown slots, unknown triggers, and device ambiguity are non-fatal and produce diagnostics plus passthrough-backed unresolved state,
- partial import is acceptable only after the raw file has been parsed successfully.

## Validation Model

Validation should move out of the widget and into the headless core.

Validation should cover at least:

- duplicate slot assignments,
- trigger-mode conflicts,
- incompatible device-role assignments,
- unknown action references,
- unresolved slot mappings,
- passthrough conflicts with edited bindings,
- ambiguous device matches,
- export-time loss risks.

Diagnostics should be structured and queryable so the UI can present warnings, errors, and unresolved items cleanly.

## UI Responsibilities

The Qt layer should become a presentation shell.

The UI may keep VKB-specific visuals in the first milestone, but it should no longer:

- parse Star Citizen XML,
- translate between old and new binding models,
- infer joystick sides directly,
- own export mutation logic,
- decide which unsupported records to drop.

The UI should instead:

- display device-role layouts,
- show current bindings and diagnostics,
- issue rebinding commands to the binding session service,
- present unresolved items for review,
- trigger save and export operations through the core.

## Migration Strategy

The revival should happen through seam extraction, not a full rewrite of the whole application at once.

### Sub-Project 1: Core Binding Engine And Repositories

Create the headless domain-backed session model and real repository interfaces for catalogs, layouts, and Star Citizen profiles.

Checkpoint:

- import one real Star Citizen profile into a headless session,
- expose editable bindings, passthrough records, unresolved items, and diagnostics,
- export a valid profile without losing unknown records,
- use a temporary explicit device-role mapping seam for profiles that already have known left and right assignments.

### Sub-Project 2: Stable Device Identity And Matching

Introduce stable device identity, persisted device-role mapping, and import-time matching from Star Citizen instance numbers to user roles.

Checkpoint:

- the same profile remains correct when device enumeration order changes,
- user-confirmed role assignments survive app restarts,
- mismatches surface as diagnostics instead of silent remapping,
- unresolved-device bindings can either stay preserved or be explicitly reassigned by the user.

### Sub-Project 3: Star Citizen Compatibility Pipeline

Replace version-pinned startup globals with repository-loaded action catalogs and XML adapters that preserve unresolved content.

Checkpoint:

- updated action catalogs can be introduced as data,
- unknown actions and inputs round-trip without destructive loss.
- newly understood actions may be promoted from passthrough-backed unresolved state only when promotion is unambiguous.

### Sub-Project 4: Qt Shell Migration And Cleanup

Migrate the current UI to consume the new session service, then remove widget-owned import and export logic and retire the old joystick binding model as application state.

Checkpoint:

- the UI can load, edit, validate, and export through the headless core,
- old duplicate binding state is removed,
- startup and packaging use one canonical application entry point.

## Testing Strategy

The most important tests are headless core tests, not widget tests.

### Required Core Tests

- XML import and export round-trip tests using real fixture profiles,
- device matching tests with reordered hardware enumerations,
- device matching disambiguation tests with two plausible identical devices,
- compatibility tests for unknown actions and unknown slots,
- compatibility tests for unknown trigger or modifier encodings,
- validation tests for conflicting bindings and ambiguous mappings,
- passthrough conflict tests where a user edit targets an imported passthrough record,
- multi-step session evolution tests such as import, edit one binding, edit another binding, then export,
- repository tests for versioned action catalog loading.

### UI Tests

Keep a small UI smoke suite for:

- opening a session,
- selecting slots,
- showing diagnostics,
- invoking bind and unbind actions.

Do not rely on Qt tests for the bulk of regression coverage while the Windows `pytest-qt` lane remains unstable.

## Milestone 1 Acceptance Criteria

Milestone 1 is complete when the project can:

- import a real Star Citizen exported profile,
- match left and right VKB devices through stable identity mapping,
- preserve unknown or unsupported records on import,
- preserve unknown actions and unknown trigger encodings through export when untouched,
- edit supported bindings through a headless session service,
- require explicit resolution when an edited binding conflicts with passthrough data,
- export a valid profile that survives joystick renumbering,
- prove the above with repeatable headless tests.

## Risks And Mitigations

### Risk: Star Citizen schema drift

Mitigation: treat action catalogs and XML adapters as versioned data sources, preserve unresolved content, and avoid assuming full schema coverage.

### Risk: Hardware identity remains too weak

Mitigation: model device identity explicitly, persist role assignments, and keep ambiguity visible instead of hidden.

### Risk: UI migration stalls the effort again

Mitigation: require a working headless checkpoint before moving large amounts of Qt code.

### Risk: Existing tests overstate safety

Mitigation: move primary regression confidence to round-trip and matching tests in the core.

## Non-Goals For Now

- broad non-VKB feature parity,
- aggressive UI redesign,
- distribution and release polish before the core is trustworthy,
- solving every existing UI issue before the core migration begins.