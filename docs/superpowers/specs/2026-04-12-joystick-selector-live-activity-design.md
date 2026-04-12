# CitizenBindVkb Joystick Selector and Live Activity Design

## Goal

Add a joystick selector and live test flow that can detect connected devices, persist left and right joystick assignments through the existing app config, and visually pulse the matching VKB control area in both the selector window and the main mapper window when the user presses a button, hat direction, or supported trigger.

## Problem Statement

The app already stores joystick identity hints in [app/config.py](app/config.py) and can enumerate controllers through [app/utils/devices.py](app/utils/devices.py), but device setup is still a manual text-entry task.

Today the user must guess or type:

- left and right joystick name filters,
- joystick type strings,
- joystick instance numbers,
- side identifiers.

The main mapper in [app/ui.py](app/ui.py) also has no live input feedback. The window shows mapped controls, but it cannot confirm which physical control is currently firing. That makes initial setup, troubleshooting, and profile verification slower than it needs to be.

## Scope

### In Scope

- add a dedicated selector and live test dialog launched from the existing settings flow,
- detect currently connected joystick devices through `pygame`,
- let the user assign one detected device to the saved left role and one to the saved right role,
- persist assignments by updating the existing config fields instead of inventing a separate persistence path,
- monitor live device activity for buttons, hat directions, and supported trigger axes,
- render a short pulse-and-glow highlight over the matching control region for known VKB layouts,
- reuse the same live activity feed in the main mapper window so assigned devices also highlight there,
- keep unsupported devices visible in the selector while clearly marking that visual overlay support is unavailable,
- keep the existing manual config fields as fallback inputs.

### Out Of Scope

- adding or editing button bindings from the selector dialog,
- visualizing arbitrary stick axes or raw motion that does not map to a known VKB slot,
- adding new non-VKB layout authoring tools,
- removing the existing manual joystick fields from the settings dialog,
- redesigning the main mapper layout beyond the minimum needed to host live overlay rendering,
- introducing a custom particle engine or scene graph for effects.

## Approaches Considered

### 1. Extend the Existing Settings Dialog Inline

Add device enumeration, assignment, live polling, and preview directly into [app/components/settings_dialog.py](app/components/settings_dialog.py).

Pros:

- small initial surface area,
- no new top-level Qt window type.

Cons:

- overloads a simple form dialog with runtime monitoring behavior,
- makes the live preview and device list compete with plain config fields,
- makes reuse of the same live highlight behavior in [app/ui.py](app/ui.py) awkward.

### 2. Launch a Dedicated Selector Dialog from Settings

Keep Settings as the entry point, but open a dedicated joystick selector and tester dialog backed by a shared live input monitor.

Pros:

- separates device setup from generic app configuration,
- keeps live input monitoring reusable across multiple windows,
- fits the requested workflow directly,
- keeps the main mapper and settings dialog changes bounded.

Cons:

- adds one more Qt component and a small shared runtime service,
- requires explicit coordination between settings, selector dialog, and main window subscribers.

### 3. Build a General Hardware Abstraction Layer First

Pause on the selector feature and first create a broad abstraction for arbitrary device layouts, raw input models, and runtime identity.

Pros:

- strongest long-term architecture for future hardware families,
- clean separation between layout data and input backends.

Cons:

- too large for the current feature slice,
- delays direct user value,
- increases architecture churn before the current feature is proven.

### Decision

Choose approach 2: keep Settings as the entry point, but open a dedicated selector and test dialog backed by one shared live input monitor and one reusable overlay rendering path.

## Architecture Overview

This feature should add one focused runtime path for device monitoring instead of scattering polling logic across dialogs and windows.

The feature is split into four responsibilities:

1. Device catalog and runtime identity: enumerate connected devices, expose their human-readable names and runtime identifiers, and distinguish between the raw `pygame` device index and the saved Star Citizen-facing instance number used by the current profile-resolution logic.
2. Live activity normalization: translate raw `pygame` state changes into stable slot events such as `button3`, `hat1_up`, or `trigger_left`.
3. Visual overlay rendering: consume normalized slot events and render short-lived pulse-and-glow highlights over known slot coordinates.
4. Qt integration: the selector dialog handles assignment and preview; the main mapper consumes the same live activity stream for passive highlighting only.

The main rule for this slice is that only one component is responsible for polling runtime device state. Qt windows subscribe to activity; they do not each create their own polling loop.

## Components

### Settings Entry Point

[app/components/settings_dialog.py](app/components/settings_dialog.py) remains the existing configuration surface, but gains a single entry button such as `Joystick Selector...`.

Responsibilities:

- open the dedicated selector dialog,
- refresh visible config fields after the selector saves,
- keep manual text and instance fields editable as a fallback path.

The settings dialog does not take on live polling logic itself.

### Joystick Device Catalog

The current device enumeration helper in [app/utils/devices.py](app/utils/devices.py) needs a clearer device model.

For this slice, each detected device should expose at least:

- `display_name`,
- `product_name`,
- `product_guid`,
- `pygame_index` as the zero-based runtime device slot used to open the `pygame` joystick,
- `saved_instance` as the one-based Star Citizen-facing instance value written into config,
- `num_buttons`,
- `num_axes`,
- `layout_key_or_none` indicating whether the device matches a visually supported VKB layout.

The critical rule is that config persistence must write `saved_instance`, not the raw zero-based `pygame_index`, because [app/ui.py](app/ui.py) compares saved instance values against Star Citizen profile instance numbers.

The selector dialog uses this catalog to populate the detected device list and the left and right assignment controls.

### Supported Layout Catalog

The current coordinate data in [app/models/joystick.py](app/models/joystick.py) is enough for static button placement, but live input highlighting also needs raw input mapping metadata.

For each visually supported VKB layout, the catalog must provide:

- layout key,
- image asset reference,
- slot coordinate data for overlay placement,
- raw button index to slot name mapping,
- hat direction to slot name mapping,
- supported trigger axis mappings with activation thresholds,
- device-name matching rules used to decide whether a detected device is visually supported.

For this slice, those matching rules live in code beside the supported layout catalog rather than in external data files. Planning can decide the exact module shape, but the rules must be authored and tested as part of the layout-support code path rather than hidden in widget logic.

The first slice only needs known VKB layouts already represented by the current coordinate set. Unsupported devices remain selectable, but do not enable the image overlay preview.

### Joystick Monitor Service

Add a focused runtime monitor service responsible for:

- initializing and shutting down the `pygame` joystick subsystem safely,
- refreshing the detected device list,
- opening live devices by runtime index,
- polling current state on a Qt-friendly cadence,
- comparing state snapshots so it emits semantic changes rather than raw noise,
- publishing normalized activity records to subscribers.

The monitor should be Qt-aware at the signal boundary, but not widget-aware. It should expose subscriber-friendly signals or callbacks for:

- device list changed,
- monitor warning or failure,
- normalized activity event.

The polling contract for this slice is:

- buttons emit activation when their pressed state changes,
- hats emit activation when direction changes to a supported non-neutral direction and emit clear state when returning to neutral,
- triggers emit activation when crossing a configured threshold and emit clear state when dropping back below threshold,
- held inputs do not continuously retrigger the highlight animation every polling tick.

For testability, the monitor should depend on an injectable backend or snapshot provider rather than reading directly from `pygame` at every call site.

### Normalized Activity Event

The overlay and windows should consume one stable activity shape instead of backend-specific event objects.

Each event should carry at least:

- `product_guid`,
- `pygame_index`,
- `saved_instance`,
- `slot_name`,
- `input_kind` such as `button`, `hat`, or `trigger`,
- `active` as a boolean,
- `value` for threshold-aware trigger reporting when needed,
- `timestamp`.

This event model is deliberately small. It exists to tell the UI which known slot became active or inactive, not to expose full raw hardware telemetry.

### Joystick Selector Dialog

Add a new dedicated Qt dialog responsible for assignment and live preview.

The dialog layout for this slice is:

- detected device list with device name, counts, and support state,
- left assignment control,
- right assignment control,
- single preview area that follows the currently selected assignment target or selected device row,
- status strip for the latest live input and monitor warnings,
- `Refresh Devices`, `Save Assignments`, and `Close` actions.

Behavior:

- opening the dialog immediately refreshes devices,
- changing left or right assignment updates the pending selection state,
- selecting a supported device enables the VKB preview image and live overlay,
- selecting an unsupported device shows a clear message that assignment is allowed but visual preview is unavailable,
- saving updates the existing config object and persists it through `Config.save()`.

Save validation rules:

- no save when neither side is assigned,
- no save when one required role is left empty if the dialog is configured to require both roles for this action,
- block saving the same physical detected device as both left and right in this slice,
- surface validation errors inline rather than through silent no-op behavior.

### Shared Activity Overlay

Add a reusable overlay renderer responsible for the pulse-and-glow effect.

Requirements:

- accept normalized activity events plus a supported layout key,
- resolve the event `slot_name` to a visual coordinate,
- animate a short pulse ring, glow burst, and fade-out over the target region,
- restart or layer the pulse cleanly on repeated presses,
- expire stale highlights automatically after a short timeout,
- render without interfering with click handling on the main mapper buttons.

This slice should not implement a full particle system. A lightweight pulse-and-glow animation is the intended effect and is sufficient for the requested “highlight where the button is” behavior.

### Main Mapper Integration

[app/ui.py](app/ui.py) becomes a passive subscriber to the same monitor service.

Responsibilities:

- subscribe to normalized activity only for the assigned left and right devices,
- render live highlights over the current joystick image using the shared overlay,
- keep all existing binding edit behavior unchanged,
- detach safely when the window closes.

The main window must not own a second monitoring loop.

## Data Flow

### Selector Launch Flow

1. User opens Settings.
2. User clicks `Joystick Selector...`.
3. Settings creates the selector dialog, passing the current config and access to the shared or injectable monitor service.
4. The dialog refreshes devices immediately.
5. The device list renders support state for each detected controller.

### Assignment Save Flow

1. User picks a detected device for the left role and one for the right role.
2. The dialog validates that the assignments are complete and not duplicated.
3. The dialog updates existing config fields:
   - `joystick_left_name_filter` and `joystick_right_name_filter` from detected product names,
   - `joystick_type_left` and `joystick_type_right` from the supported layout display name when a known layout matches, otherwise from the detected product name,
   - `joystick_instance_left` and `joystick_instance_right` from the one-based saved instance values.
4. The dialog keeps current side identifiers unless a future slice introduces explicit selector-backed side identifier derivation.
5. The dialog saves the config and closes or remains open depending on the chosen UX.
6. Settings refreshes its visible fields from the updated config.

The selector and the existing manual fields write to the same config keys. The last explicit save wins. This keeps the fallback path simple and avoids inventing a second persistence layer.

### Live Preview Flow

1. The monitor polls runtime device state on a timer.
2. A supported button, hat direction, or trigger changes state.
3. The monitor normalizes that change into an activity event.
4. The selector dialog receives the event for the currently previewed device and forwards it to the overlay.
5. The overlay resolves the slot coordinate and starts the pulse animation.
6. The status strip shows the most recent activity label.

### Main Window Highlight Flow

1. The main window subscribes to normalized activity for assigned left and right devices.
2. A relevant event arrives.
3. The window overlay resolves the slot coordinate for the currently visible joystick side.
4. The overlay animates the matching slot without altering the current binding selection state.

## Error Handling And Edge Cases

### No Devices Found

- selector shows an explicit empty state,
- assignment controls are disabled or empty,
- save is disabled,
- refresh remains available.

### Unsupported Device

- device stays selectable and assignable,
- selector clearly marks `visual preview unavailable`,
- live raw slot preview is suppressed because no stable coordinate mapping exists,
- settings persistence still works.

### Duplicate Left And Right Assignment

- saving is blocked when both roles target the same physical detected device,
- the dialog shows an inline validation message.

### `pygame` Initialization Or Polling Failure

- monitor emits a warning signal,
- selector and main window show a visible status message,
- polling stops cleanly until the user refreshes or reopens monitoring,
- the app does not crash or silently ignore the error.

### Unsupported Motion

- raw stick axes or unmapped trigger axes do not generate overlay events,
- unsupported activity is ignored rather than guessed into a visual slot.

### Hotplug And Reopen Behavior

- device list is refreshed on dialog open and when the user clicks `Refresh Devices`,
- if a previewed device disappears, the dialog clears preview state and shows a warning,
- the first slice does not require fully automatic hotplug rebinding without user refresh.

## Testing Strategy

### Non-Qt Tests

Add unit tests for:

- device enumeration translation from raw backend records to the richer detected-device model,
- one-based saved instance derivation from runtime device indices,
- supported-layout detection,
- raw button, hat, and trigger state normalization into stable activity events,
- duplicate-assignment validation,
- config update logic driven by saved assignments.

These tests should not require real hardware. They should run against fake backend snapshots.

### Qt Seam Tests

Add focused widget tests for:

- launching the selector dialog from Settings,
- rendering detected devices and support badges,
- saving left and right assignments into config,
- blocking duplicate left and right assignments,
- showing the unsupported-device preview warning,
- forwarding a normalized activity event into selector overlay state,
- forwarding a normalized activity event into main-window overlay state.

Qt tests should assert overlay state changes and expiration behavior, not pixel-perfect animation frames.

### Verification Lane

Before claiming completion for this feature slice, run at least:

- focused non-Qt tests for the device catalog and monitor service,
- focused Qt seam tests for settings, selector dialog, and main window overlay integration,
- Ruff on the touched files.

## Rollout Notes

- keep the existing manual joystick config fields visible as fallback,
- ship the selector as the preferred path without removing the manual path,
- keep the shared monitor and overlay boundaries narrow so later hardware families can extend them without rewriting settings or the main mapper.

## Deferred Work

The following are intentionally deferred until this slice proves itself:

- visual treatment for arbitrary stick axes,
- support for authoring new visual layouts,
- automatic hotplug reassignment without user refresh,
- replacing manual side-identifier fields with selector-derived metadata,
- richer runtime telemetry panels.