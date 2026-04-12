# Joystick Selector And Live Activity M1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a settings-launched joystick selector dialog that detects connected devices, saves left and right assignments into the existing config, and drives shared live VKB control highlighting in both the selector and the main mapper window.

**Architecture:** Introduce one shared `pygame`-backed monitor service with an injectable backend and a small supported-layout catalog that maps raw buttons, hats, and trigger axes onto known VKB slot names. Keep device assignment and preview in a dedicated selector dialog, and render activity with one reusable overlay widget that attaches to both the selector preview and the main mapper's existing joystick image.

**Tech Stack:** Python 3.11+, PyQt6, pygame, pytest, pytest-qt, Ruff, existing `Config`, existing VKB coordinate metadata in `app/models/joystick.py`.

**Execution Notes:** Use @test-driven-development for every task in order. Use @verification-before-completion before claiming the feature is done.

---

## Planned File Structure

**Create**

- `app/models/joystick_layout_support.py` — supported VKB layout metadata, raw-input-to-slot mappings, trigger thresholds, and device-name matching rules kept out of widget code.
- `app/services/joystick_monitor.py` — detected-device model, normalized activity model, backend protocol, snapshot diffing, and the shared Qt timer monitor service.
- `app/components/joystick_activity_overlay.py` — reusable overlay widget and pulse-state model for slot-based live highlights.
- `app/components/joystick_selector_dialog.py` — dedicated selector and live test dialog launched from Settings.
- `tests/test_joystick_monitor.py` — non-Qt tests for device translation, saved-instance derivation, layout detection, and activity normalization.
- `tests/test_joystick_selector_dialog.py` — focused Qt seam tests for selector rendering, validation, and config persistence.
- `tests/test_joystick_activity_overlay.py` — focused Qt tests for overlay state, pulse restart behavior, and expiration.
- `docs/superpowers/plans/2026-04-12-joystick-selector-live-activity-m1.md` — this plan file.

**Modify**

- `app/utils/devices.py` — replace the ad-hoc enumeration helper with a small raw `pygame` backend adapter that the monitor can fake in tests, keeping compatibility only if needed by surviving call sites.
- `app/services/__init__.py` — export the new joystick monitor types used by Qt code.
- `app/components/settings_dialog.py` — add the selector launch button, inject the shared monitor service, and refresh manual config fields after selector saves.
- `app/ui.py` — own the shared monitor lifecycle, attach the overlay to the existing joystick image, subscribe to activity for assigned devices, and pass the monitor into Settings.
- `tests/test_ui.py` — add the smallest possible main-window live-highlight seam coverage without expanding unrelated Qt behavior.

**Do Not Touch In This Plan**

- `app/services/ui_session_controller.py` and related session-flow files — this feature is orthogonal to the recently completed controller-backed binding work.
- `app/dev_tools/export_configmap.py` — device selection and live testing only.
- `app/models/joystick.py` layout coordinates unless a tiny read-only helper is unavoidable — prefer new layout-support code over adding more responsibility to the existing large data file.
- top-level `main.py` — it is not part of the packaged app entry path.

## Chunk 1: Runtime Device Catalog And Activity Monitor

### Task 1: Add Red Tests For Device Translation And Activity Normalization

**Files:**
- Create: `tests/test_joystick_monitor.py`

- [ ] **Step 1: Write failing tests for the richer detected-device model**

Create tests that lock down the one-based saved instance rule, supported-layout detection, and device-name matching.

Start the file with explicit test-only helpers so the red lane is runnable:

```python
@dataclass
class FakeJoystickBackend:
    devices: list[RawJoystickDevice]
    snapshots: list[dict[int, DeviceSnapshot]] = field(default_factory=list)
    failure: Exception | None = None

    def list_devices(self) -> list[RawJoystickDevice]:
        if self.failure is not None:
            raise self.failure
        return list(self.devices)

    def read_snapshots(self) -> dict[int, DeviceSnapshot]:
        if self.failure is not None:
            raise self.failure
        if not self.snapshots:
            return {}
        return self.snapshots.pop(0)


def build_monitor_with_layout(backend: FakeJoystickBackend) -> JoystickMonitorService:
    return JoystickMonitorService(backend=backend, interval_ms=16)
```

```python
def test_detected_device_uses_one_based_saved_instance_and_layout_match() -> None:
    backend = FakeJoystickBackend(
        devices=[
            RawJoystickDevice(
                pygame_index=0,
                product_name="VKBsim Gladiator EVO L",
                product_guid="guid-left",
                num_axes=8,
                num_buttons=32,
            )
        ]
    )

    devices = list_detected_devices(backend, SUPPORTED_LAYOUTS)

    assert devices == [
        DetectedJoystickDevice(
            display_name="VKBsim Gladiator EVO L",
            product_name="VKBsim Gladiator EVO L",
            product_guid="guid-left",
            pygame_index=0,
            saved_instance=1,
            num_axes=8,
            num_buttons=32,
            layout_key="vkb_default",
        )
    ]
```

- [ ] **Step 2: Extend the same file with red normalization tests**

Add tests for edge-triggered button events, hat direction changes, trigger threshold activation, and ignored unsupported axes.

```python
def test_button_press_emits_slot_once_per_transition() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {0: DeviceSnapshot(buttons=(False, False, True), hats=((0, 0),), axes=(0.0, 0.0))},
            {0: DeviceSnapshot(buttons=(False, False, True), hats=((0, 0),), axes=(0.0, 0.0))},
        ],
    )
    monitor = build_monitor_with_layout(backend)
    monitor.refresh_devices()

    first = monitor.poll_once()
    second = monitor.poll_once()

    assert [event.slot_name for event in first] == ["button3"]
    assert second == []


def test_hat_direction_emits_active_and_clear_events() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {0: DeviceSnapshot(buttons=(False,) * 32, hats=((0, 1),), axes=(0.0,) * 8)},
            {0: DeviceSnapshot(buttons=(False,) * 32, hats=((0, 0),), axes=(0.0,) * 8)},
        ],
    )
    monitor = build_monitor_with_layout(backend)
    monitor.refresh_devices()

    first = monitor.poll_once()
    second = monitor.poll_once()

    assert [(event.slot_name, event.active) for event in first] == [("hat1_up", True)]
    assert [(event.slot_name, event.active) for event in second] == [("hat1_up", False)]


def test_trigger_threshold_emits_active_and_clear_events() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {0: DeviceSnapshot(buttons=(False,) * 32, hats=((0, 0),), axes=(0.0, 0.0, 0.82, 0.0, 0.0, 0.0, 0.0, 0.0))},
            {0: DeviceSnapshot(buttons=(False,) * 32, hats=((0, 0),), axes=(0.0, 0.0, 0.15, 0.0, 0.0, 0.0, 0.0, 0.0))},
        ],
    )
    monitor = build_monitor_with_layout(backend)
    monitor.refresh_devices()

    first = monitor.poll_once()
    second = monitor.poll_once()

    assert [(event.slot_name, event.active) for event in first] == [("trigger_left", True)]
    assert [(event.slot_name, event.active) for event in second] == [("trigger_left", False)]


def test_unmapped_axis_motion_is_ignored() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        snapshots=[
            {0: DeviceSnapshot(buttons=(False,) * 32, hats=((0, 0),), axes=(0.0, 0.0, 0.0, 0.0, 0.91, 0.0, 0.0, 0.0))},
        ],
    )
    monitor = build_monitor_with_layout(backend)
    monitor.refresh_devices()

    assert monitor.poll_once() == []


def test_refresh_devices_returns_empty_list_when_backend_has_none() -> None:
    backend = FakeJoystickBackend(devices=[])

    monitor = build_monitor_with_layout(backend)

    assert monitor.refresh_devices() == []


def test_poll_once_emits_warning_and_preserves_state_on_backend_failure() -> None:
    backend = FakeJoystickBackend(
        devices=[RawJoystickDevice(0, "VKBsim Gladiator EVO L", "guid-left", 8, 32)],
        failure=RuntimeError("pygame failure"),
    )
    monitor = build_monitor_with_layout(backend)
    warnings: list[str] = []
    monitor.warning.connect(warnings.append)

    assert monitor.refresh_devices() == []
    assert warnings == ["pygame failure"]
```

- [ ] **Step 3: Run the red non-Qt monitor lane**

Run: `uv run pytest -o addopts= tests/test_joystick_monitor.py -q`

Expected: FAIL because the layout-support module, detected-device model, and monitor service do not exist yet.

- [ ] **Step 4: Commit the red tests**

```bash
git add tests/test_joystick_monitor.py
git commit -m "test: add joystick monitor red tests"
```

### Task 2: Implement Supported Layout Metadata And Raw Backend Adapter

**Files:**
- Create: `app/models/joystick_layout_support.py`
- Modify: `app/utils/devices.py`
- Test: `tests/test_joystick_monitor.py`

- [ ] **Step 1: Create the supported-layout metadata module**

Add a focused layout-support module so device-name matching and raw-input mappings are not buried in widgets.

```python
@dataclass(frozen=True)
class TriggerAxisMapping:
    axis_index: int
    slot_name: str
    activate_at: float
    clear_below: float


@dataclass(frozen=True)
class SupportedJoystickLayout:
    key: str
    display_name: str
    chart_name: str
    product_name_fragments: tuple[str, ...]
    button_slots: dict[int, str]
    hat_slots: dict[tuple[int, int], str]
    trigger_axes: tuple[TriggerAxisMapping, ...]

    def matches(self, product_name: str) -> bool:
        normalized = product_name.casefold()
        return all(fragment.casefold() in normalized for fragment in self.product_name_fragments)


VKB_DEFAULT_BUTTON_SLOTS = {index: f"button{index + 1}" for index in range(19)}
VKB_DEFAULT_HAT_SLOTS = {
    (0, 1): "hat1_up",
    (1, 1): "hat1_up_right",
    (-1, 1): "hat1_up_left",
    (-1, 0): "hat1_left",
    (1, 0): "hat1_right",
    (-1, -1): "hat1_down_left",
    (0, -1): "hat1_down",
    (1, -1): "hat1_down_right",
}
VKB_DEFAULT_TRIGGER_AXES = (
    TriggerAxisMapping(axis_index=2, slot_name="trigger_left", activate_at=0.75, clear_below=0.35),
    TriggerAxisMapping(axis_index=5, slot_name="trigger_right", activate_at=0.75, clear_below=0.35),
)
```

Seed `SUPPORTED_LAYOUTS` with the known VKB default layout and explicit mappings for buttons, hats, and the supported trigger axes only.

The layout module should also expose one helper that resolves slot coordinates lazily from the existing chart data in `app/models/joystick.py` so the new file owns matching rules without duplicating coordinate data.

Use the confirmed existing API name from `app/models/joystick.py`: `get_joystick_buttons("VKB Default")`.

The only coordinate data that should remain local to `joystick_layout_support.py` are the two trigger highlight anchors, because the current `app/models/joystick.py` chart exposes button and hat slots but does not expose trigger slots by those names.

```python
def slot_positions_for_layout(layout_key: str, side: Literal["left", "right"]) -> dict[str, QPoint]:
    buttons = get_joystick_buttons("VKB Default")
    positions = {
        slot_name: QPoint(button.coord_x_left[side], button.coord_y_top)
        for slot_name, button in buttons.items()
    }
    positions.update(
        {
            "trigger_left": QPoint(1540 if side == "left" else 280, 335),
            "trigger_right": QPoint(1540 if side == "left" else 280, 190),
        }
    )
    return positions
```

- [ ] **Step 2: Search for remaining legacy helper call sites**

Run: `rg "get_controller_devices\(" app tests`

Expected: Either no live call sites outside `app/utils/devices.py`, or a small explicit list that justifies keeping a compatibility wrapper.

- [ ] **Step 3: Replace the raw `pygame` helper with a backend adapter**

Reshape `app/utils/devices.py` into small raw-access helpers that the monitor can fake in tests.

```python
@dataclass(frozen=True)
class RawJoystickDevice:
    pygame_index: int
    product_name: str
    product_guid: str
    num_axes: int
    num_buttons: int


@dataclass(frozen=True)
class DeviceSnapshot:
    buttons: tuple[bool, ...]
    hats: tuple[tuple[int, int], ...]
    axes: tuple[float, ...]


class PygameJoystickBackend:
    def list_devices(self) -> list[RawJoystickDevice]:
        ...

    def read_snapshots(self) -> dict[int, DeviceSnapshot]:
        ...
```

Keep a thin compatibility wrapper only if Step 2 finds a surviving call site that still needs `get_controller_devices()`.

If Step 2 finds call sites, create the wrapper in Step 3. If Step 2 finds none, remove the old helper entirely in Step 3.

- [ ] **Step 4: Run the layout-only subset**

Run: `uv run pytest -o addopts= tests/test_joystick_monitor.py -k "saved_instance or layout_match" -q`

Expected: Some tests pass for device translation, while normalization tests remain red because the monitor service still does not exist.

- [ ] **Step 5: Commit the layout and backend scaffolding**

```bash
git add app/models/joystick_layout_support.py app/utils/devices.py tests/test_joystick_monitor.py
git commit -m "feat: add joystick layout metadata and raw device backend"
```

### Task 3: Implement The Shared Joystick Monitor Service

**Files:**
- Create: `app/services/joystick_monitor.py`
- Modify: `app/services/__init__.py`
- Test: `tests/test_joystick_monitor.py`

- [ ] **Step 1: Add the detected-device and activity-event models in the monitor module**

Keep the UI-facing runtime models close to the service that emits them.

```python
@dataclass(frozen=True)
class DetectedJoystickDevice:
    display_name: str
    product_name: str
    product_guid: str
    pygame_index: int
    saved_instance: int
    num_axes: int
    num_buttons: int
    layout_key: str | None = None


@dataclass(frozen=True)
class JoystickActivityEvent:
    product_guid: str
    pygame_index: int
    saved_instance: int
    slot_name: str
    input_kind: Literal["button", "hat", "trigger"]
    active: bool
    value: float
    timestamp: float


def list_detected_devices(
    backend: PygameJoystickBackend,
    supported_layouts: tuple[SupportedJoystickLayout, ...] = SUPPORTED_LAYOUTS,
) -> list[DetectedJoystickDevice]:
    devices: list[DetectedJoystickDevice] = []
    for raw_device in backend.list_devices():
        layout = next((item for item in supported_layouts if item.matches(raw_device.product_name)), None)
        devices.append(
            DetectedJoystickDevice(
                display_name=layout.display_name if layout is not None else raw_device.product_name,
                product_name=raw_device.product_name,
                product_guid=raw_device.product_guid,
                pygame_index=raw_device.pygame_index,
                saved_instance=raw_device.pygame_index + 1,
                num_axes=raw_device.num_axes,
                num_buttons=raw_device.num_buttons,
                layout_key=layout.key if layout is not None else None,
            )
        )
    return devices
```

- [ ] **Step 2: Implement the monitor with a 16 ms polling cadence and edge-triggered diffing**

Use one `QTimer` running at roughly 60 Hz. Repeated held states must not emit duplicate activation events every tick.

```python
class JoystickMonitorService(QObject):
    devices_changed = pyqtSignal(object)
    activity = pyqtSignal(object)
    warning = pyqtSignal(str)

    def __init__(self, backend: PygameJoystickBackend | None = None, interval_ms: int = 16) -> None:
        ...

    def refresh_devices(self) -> list[DetectedJoystickDevice]:
        ...

    def poll_once(self, device_states: dict[int, DeviceSnapshot] | None = None) -> list[JoystickActivityEvent]:
        ...

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...
```

Rules:

- when `backend` is `None`, construct `PygameJoystickBackend()` internally,
- translate `pygame_index` to `saved_instance` as `pygame_index + 1`,
- resolve `layout_key` through `SUPPORTED_LAYOUTS`,
- emit `active=False` clear events for hats returning to neutral and triggers dropping below threshold,
- ignore unmapped axes,
- catch backend exceptions, emit `warning`, and leave prior state consistent.

Use this diffing structure so the stateful behavior is explicit before implementation starts:

```python
def poll_once(self, device_states: dict[int, DeviceSnapshot] | None = None) -> list[JoystickActivityEvent]:
    try:
        current = device_states if device_states is not None else self.backend.read_snapshots()
    except Exception as exc:
        self.warning.emit(str(exc))
        return []
    events: list[JoystickActivityEvent] = []
    for pygame_index, snapshot in current.items():
        previous = self._previous_snapshots.get(pygame_index)
        layout = self._layout_by_index.get(pygame_index)
        if layout is None:
            continue
        events.extend(self._diff_buttons(layout, pygame_index, previous, snapshot))
        events.extend(self._diff_hats(layout, pygame_index, previous, snapshot))
        events.extend(self._diff_triggers(layout, pygame_index, previous, snapshot))
    self._previous_snapshots = {**self._previous_snapshots, **current}
    for event in events:
        self.activity.emit(event)
    return events
```

Each private diff helper returns `list[JoystickActivityEvent]` and owns one edge-transition rule:

- `_diff_buttons(...)` emits `active=True` on press and `active=False` on release for mapped button indices.
- `_diff_hats(...)` emits `active=True` when a mapped direction becomes active and `active=False` when it leaves that direction.
- `_diff_triggers(...)` emits `active=True` when a configured axis crosses `activate_at` and `active=False` when it later drops below `clear_below`.

Minimal helper skeletons:

```python
def _diff_buttons(...) -> list[JoystickActivityEvent]:
    ...


def _diff_hats(...) -> list[JoystickActivityEvent]:
    ...


def _diff_triggers(...) -> list[JoystickActivityEvent]:
    ...
```

- [ ] **Step 3: Run the full non-Qt runtime lane**

Run: `uv run pytest -o addopts= tests/test_joystick_monitor.py -q`

Expected: PASS.

- [ ] **Step 4: Commit the monitor service**

```bash
git add app/services/joystick_monitor.py app/services/__init__.py tests/test_joystick_monitor.py
git commit -m "feat: add shared joystick monitor service"
```

## Chunk 2: Selector Dialog And Settings Persistence

### Task 4: Add Red Qt Tests For The Selector Dialog And Settings Entry Point

**Files:**
- Create: `tests/test_joystick_selector_dialog.py`

- [ ] **Step 1: Write failing tests for launching the selector from Settings**

Use a fake monitor so the dialog tests do not touch real hardware.

Start the file with self-contained test helpers so the selector tests do not depend on fixtures defined in another chunk:

```python
def detected_device(
    product_guid: str,
    product_name: str,
    pygame_index: int,
    layout_key: str | None,
) -> DetectedJoystickDevice:
    return DetectedJoystickDevice(
        display_name=product_name,
        product_name=product_name,
        product_guid=product_guid,
        pygame_index=pygame_index,
        saved_instance=pygame_index + 1,
        num_axes=8,
        num_buttons=32,
        layout_key=layout_key,
    )


class FakeJoystickMonitor(QObject):
    activity = pyqtSignal(object)
    warning = pyqtSignal(str)

    def __init__(self, devices: list[DetectedJoystickDevice]) -> None:
        super().__init__()
        self._devices = devices

    def refresh_devices(self) -> list[DetectedJoystickDevice]:
        return list(self._devices)

    def emit_activity(self, event: JoystickActivityEvent) -> None:
        self.activity.emit(event)
```

```python
def test_settings_dialog_opens_selector_window(qtbot: Any) -> None:
    config = Config()
    monitor = FakeJoystickMonitor(devices=[])
    dialog = SettingsDialog(config, joystick_monitor=monitor)

    qtbot.mouseClick(dialog.joystick_selector_button, Qt.MouseButton.LeftButton)

    assert dialog.selector_dialog is not None
    assert dialog.selector_dialog.isVisible()
```

- [ ] **Step 2: Extend the same file with red selector behavior tests**

Add tests for rendering support state, blocking duplicate left and right assignments, persisting config fields, and showing the unsupported preview warning.

```python
def test_selector_blocks_duplicate_left_and_right_assignment(qtbot: Any) -> None:
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[
            detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default"),
            detected_device("guid-right", "VKBsim Gladiator EVO R", 1, "vkb_default"),
        ]
    )
    dialog = JoystickSelectorDialog(config, monitor)

    dialog.left_selector.setCurrentIndex(1)
    dialog.right_selector.setCurrentIndex(1)
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    assert "different devices" in dialog.validation_label.text().lower()
```

Also add:

- `test_selector_renders_detected_devices_and_support_badges`

```python
def test_selector_renders_detected_devices_and_support_badges(qtbot: Any) -> None:
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[
            detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default"),
            detected_device("guid-generic", "Generic USB Joystick", 1, None),
        ]
    )
    dialog = JoystickSelectorDialog(config, monitor)

    assert dialog.device_list_widget.item(0).text().endswith("supported")
    assert dialog.device_list_widget.item(1).text().endswith("preview unavailable")
```

- `test_selector_save_updates_existing_config_keys`

```python
def test_selector_save_updates_existing_config_keys(qtbot: Any) -> None:
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[
            detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default"),
            detected_device("guid-right", "VKBsim Gladiator EVO R", 1, "vkb_default"),
        ]
    )
    dialog = JoystickSelectorDialog(config, monitor)

    dialog.left_selector.setCurrentIndex(1)
    dialog.right_selector.setCurrentIndex(2)
    qtbot.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)

    assert config.joystick_left_name_filter == "VKBsim Gladiator EVO L"
    assert config.joystick_right_name_filter == "VKBsim Gladiator EVO R"
    assert config.joystick_instance_left == 1
    assert config.joystick_instance_right == 2
```

- `test_selector_marks_unsupported_device_preview_unavailable`

```python
def test_selector_marks_unsupported_device_preview_unavailable(qtbot: Any) -> None:
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[detected_device("guid-generic", "Generic USB Joystick", 0, None)]
    )
    dialog = JoystickSelectorDialog(config, monitor)

    dialog.left_selector.setCurrentIndex(1)

    assert "unavailable" in dialog.preview_status_label.text().lower()
```

- [ ] **Step 3: Run the red selector Qt lane**

Run: `uv run pytest -o addopts= tests/test_joystick_selector_dialog.py -q`

Expected: FAIL because the selector dialog and new Settings entry point do not exist yet.

- [ ] **Step 4: Commit the red Qt tests**

```bash
git add tests/test_joystick_selector_dialog.py
git commit -m "test: add joystick selector dialog red tests"
```

### Task 5: Implement The Selector Dialog

**Files:**
- Create: `app/components/joystick_selector_dialog.py`
- Modify: `app/components/settings_dialog.py`
- Test: `tests/test_joystick_selector_dialog.py`

- [ ] **Step 1: Build the dedicated selector dialog UI**

Create a purpose-built dialog instead of overloading the settings form.

```python
class JoystickSelectorDialog(QDialog):
    def __init__(
        self,
        config: Config,
        joystick_monitor: JoystickMonitorService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.joystick_monitor = joystick_monitor
        self.detected_devices: list[DetectedJoystickDevice] = []
        self.selected_preview_device: DetectedJoystickDevice | None = None
        self._build_ui()
        self.refresh_devices()

    def _build_ui(self) -> None:
        self.device_list_widget = QListWidget(self)
        self.left_selector = QComboBox(self)
        self.right_selector = QComboBox(self)
        self.preview_image_label = QLabel("No preview selected", self)
        self.preview_status_label = QLabel("Select a device to preview", self)
        self.validation_label = QLabel("", self)
        self.refresh_button = QPushButton("Refresh Devices", self)
        self.save_button = QPushButton("Save Assignments", self)
        self.left_selector.currentIndexChanged.connect(self._sync_preview_from_selectors)
        self.right_selector.currentIndexChanged.connect(self._sync_preview_from_selectors)
        self.refresh_button.clicked.connect(self.refresh_devices)
        self.save_button.clicked.connect(self.save_assignments)

    def refresh_devices(self) -> None:
        self.detected_devices = self.joystick_monitor.refresh_devices()
        self.device_list_widget.clear()
        self.left_selector.clear()
        self.right_selector.clear()
        self.left_selector.addItem("-- Select Left --", None)
        self.right_selector.addItem("-- Select Right --", None)
        for device in self.detected_devices:
            suffix = "supported" if device.layout_key else "preview unavailable"
            self.device_list_widget.addItem(f"{device.display_name} ({suffix})")
            self.left_selector.addItem(device.display_name, device.product_guid)
            self.right_selector.addItem(device.display_name, device.product_guid)

    def current_left_device(self) -> DetectedJoystickDevice | None:
        return self._selected_device(self.left_selector.currentData())

    def current_right_device(self) -> DetectedJoystickDevice | None:
        return self._selected_device(self.right_selector.currentData())

    def _selected_device(self, product_guid: str | None) -> DetectedJoystickDevice | None:
        return next((device for device in self.detected_devices if device.product_guid == product_guid), None)

    def _sync_preview_from_selectors(self) -> None:
        preview_device = self.current_left_device() or self.current_right_device()
        self.set_preview_device(preview_device)
```

Include these widgets and names explicitly so tests can target them:

- `device_list_widget`
- `left_selector`
- `right_selector`
- `preview_status_label`
- `validation_label`
- `refresh_button`
- `save_button`

- [ ] **Step 2: Implement save validation and config persistence**

Make both roles mandatory in this slice, and treat the selector as writing the same config keys used by the manual fields.

```python
def save_assignments(self) -> None:
    left_device = self.current_left_device()
    right_device = self.current_right_device()
    if left_device is None or right_device is None:
        self.validation_label.setText("Select both left and right joysticks before saving.")
        return
    if left_device.product_guid == right_device.product_guid:
        self.validation_label.setText("Left and right must use different devices.")
        return

    self.config.joystick_left_name_filter = left_device.product_name
    self.config.joystick_right_name_filter = right_device.product_name
    self.config.joystick_type_left = left_device.display_name
    self.config.joystick_type_right = right_device.display_name
    self.config.joystick_instance_left = left_device.saved_instance
    self.config.joystick_instance_right = right_device.saved_instance
    self.config.save()
    self.accept()
```

Use the detected product name as the fallback type label when no supported layout is available.

- [ ] **Step 3: Add the Settings launcher and field refresh hook**

Modify `SettingsDialog` to accept the shared monitor, open the selector, and repopulate the text and spin-box fields after a successful selector save.

```python
class SettingsDialog(QDialog):
    def __init__(
        self,
        config: Config,
        joystick_monitor: JoystickMonitorService,
        parent: QWidget | None = None,
    ) -> None:
        self.config = config
        self.joystick_monitor = joystick_monitor
        self.selector_dialog = None
        ...

    def init_ui(self) -> None:
        ...
        self.joystick_selector_button = QPushButton("Joystick Selector")
        self.joystick_selector_button.clicked.connect(self.open_joystick_selector)
        self.layout.addWidget(self.joystick_selector_button)

    def open_joystick_selector(self) -> None:
        dialog = JoystickSelectorDialog(self.config, self.joystick_monitor, self)
        self.selector_dialog = dialog
        if dialog.exec():
            self.reload_fields_from_config()

    def reload_fields_from_config(self) -> None:
        self.joystick_left_name_filter_line_edit.setText(self.config.joystick_left_name_filter)
        self.joystick_right_name_filter_line_edit.setText(self.config.joystick_right_name_filter)
        self.joystick_type_left_line_edit.setText(self.config.joystick_type_left)
        self.joystick_type_right_line_edit.setText(self.config.joystick_type_right)
        self.joystick_instance_left_spin_box.setValue(self.config.joystick_instance_left)
        self.joystick_instance_right_spin_box.setValue(self.config.joystick_instance_right)
```

`ControlMapperApp.open_settings_dialog()` is the production call site and must pass the shared monitor instance into `SettingsDialog(...)`.

- [ ] **Step 4: Verify the Settings dialog no longer depends on the legacy direct device helper**

Run: `uv run pytest -o addopts= tests/test_joystick_selector_dialog.py -k "settings_dialog_opens_selector_window" -q`

Expected: PASS, and `app/components/settings_dialog.py` imports no direct `get_controller_devices` helper.

- [ ] **Step 5: Run the selector Qt seam lane and make it green**

Run: `uv run pytest -o addopts= tests/test_joystick_selector_dialog.py -q`

Expected: PASS.

- [ ] **Step 6: Commit the selector workflow**

```bash
git add app/components/joystick_selector_dialog.py app/components/settings_dialog.py tests/test_joystick_selector_dialog.py
git commit -m "feat: add joystick selector dialog and settings integration"
```

## Chunk 3: Shared Overlay And Main-Window Live Highlighting

### Task 6: Add Red Tests For Overlay State And Main-Window Subscription

**Files:**
- Create: `tests/test_joystick_activity_overlay.py`
- Modify: `tests/test_joystick_selector_dialog.py`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Write failing overlay tests for restart-and-expire behavior**

Resolve the animation policy here: repeated activations restart the pulse instead of layering a second burst.

Start `tests/test_joystick_activity_overlay.py` with a small helper so both tests speak in the same activity shape:

```python
def activity_event(
    product_guid: str = "guid-left",
    pygame_index: int = 0,
    slot_name: str = "button3",
    active: bool = True,
    timestamp: float = 1000.0,
) -> JoystickActivityEvent:
    return JoystickActivityEvent(
        product_guid=product_guid,
        pygame_index=pygame_index,
        saved_instance=1,
        slot_name=slot_name,
        input_kind="button",
        active=active,
        value=1.0 if active else 0.0,
        timestamp=timestamp,
    )
```

```python
def test_overlay_restarts_existing_pulse_for_same_slot(qtbot: Any) -> None:
    overlay = JoystickActivityOverlay(slot_positions={"button3": QPoint(100, 120)})

    overlay.record_activity(activity_event(slot_name="button3", active=True, timestamp=1000.0))
    first_started = overlay.active_pulses["button3"].started_at
    overlay.record_activity(activity_event(slot_name="button3", active=True, timestamp=1200.0))

    assert overlay.active_pulses["button3"].started_at > first_started


def test_overlay_expires_stale_pulse_after_timeout(qtbot: Any) -> None:
    overlay = JoystickActivityOverlay(slot_positions={"button3": QPoint(100, 120)})

    overlay.record_activity(activity_event(slot_name="button3", active=True, timestamp=1000.0))
    overlay._expire_stale_pulses(now_ms=1500.0)

    assert overlay.active_pulses == {}
```

- [ ] **Step 2: Add red selector and main-window activity wiring tests**

Extend the selector tests with a live-preview assertion and the main UI tests with one passive highlight assertion.

```python
def test_selector_preview_tracks_activity_for_selected_supported_device(qtbot: Any) -> None:
    config = Config()
    monitor = FakeJoystickMonitor(
        devices=[detected_device("guid-left", "VKBsim Gladiator EVO L", 0, "vkb_default")]
    )
    dialog = JoystickSelectorDialog(config, monitor)

    dialog.left_selector.setCurrentIndex(1)
    dialog.set_preview_device(dialog.current_left_device())
    monitor.emit_activity(activity_event("guid-left", 0, "button3", active=True))

    assert "button3" in dialog.preview_overlay.active_pulses


def test_main_window_highlights_matching_slot_for_assigned_device(main_window: ControlMapperApp) -> None:
    main_window.config.joystick_instance_left = 1
    main_window.current_joystick = "left"
    main_window._refresh_live_activity_assignments()

    event = activity_event("guid-left", 0, "button3", active=True)
    main_window._handle_joystick_activity(event)

    assert "button3" in main_window.joystick_activity_overlay.active_pulses
```

- [ ] **Step 3: Run the red overlay and wiring lane**

Run: `uv run pytest -o addopts= tests/test_joystick_activity_overlay.py tests/test_joystick_selector_dialog.py tests/test_ui.py -k "preview_tracks_activity or restarts_existing_pulse or expires_stale_pulse or highlights_matching_slot" -q`

Expected: FAIL because no overlay widget or shared activity subscriptions exist yet.

- [ ] **Step 4: Commit the red overlay tests**

```bash
git add tests/test_joystick_activity_overlay.py tests/test_joystick_selector_dialog.py tests/test_ui.py
git commit -m "test: add live activity overlay red tests"
```

### Task 7: Implement The Shared Activity Overlay Widget

**Files:**
- Create: `app/components/joystick_activity_overlay.py`
- Test: `tests/test_joystick_activity_overlay.py`

- [ ] **Step 1: Build the overlay state model and widget shell**

Keep the state inspectable so Qt tests can assert behavior without pixel snapshots.

```python
@dataclass
class ActivePulse:
    slot_name: str
    center: QPoint
    started_at: float
    active: bool = True


class JoystickActivityOverlay(QWidget):
    def __init__(self, slot_positions: dict[str, QPoint], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slot_positions = slot_positions
        self.active_pulses: dict[str, ActivePulse] = {}
        self._pulse_duration_ms = 450
        self._expire_timer = QTimer(self)
        self._expire_timer.setInterval(16)
        self._expire_timer.timeout.connect(self._expire_stale_pulses)

    def set_slot_positions(self, slot_positions: dict[str, QPoint]) -> None:
        self.slot_positions = slot_positions
        self.active_pulses = {
            slot_name: pulse
            for slot_name, pulse in self.active_pulses.items()
            if slot_name in slot_positions
        }
        self.update()
```

- [ ] **Step 2: Implement `record_activity()` and `paintEvent()`**

Rules:

- only `active=True` events start or restart a pulse,
- repeated activation for the same slot restarts the existing pulse,
- clear events may remove the pulse early but are not required to paint their own effect,
- the widget must be transparent to mouse interactions.

```python
import time


def record_activity(self, event: JoystickActivityEvent) -> None:
    center = self.slot_positions.get(event.slot_name)
    if center is None:
        return
    if not event.active:
        self.active_pulses.pop(event.slot_name, None)
        self.update()
        return
    self.active_pulses[event.slot_name] = ActivePulse(
        slot_name=event.slot_name,
        center=center,
        started_at=event.timestamp,
    )
    self._expire_timer.start()
    self.update()


def _expire_stale_pulses(self, now_ms: float | None = None) -> None:
    if now_ms is None:
        now_ms = time.monotonic() * 1000
    self.active_pulses = {
        slot_name: pulse
        for slot_name, pulse in self.active_pulses.items()
        if now_ms - pulse.started_at < self._pulse_duration_ms
    }
    if not self.active_pulses:
        self._expire_timer.stop()
    self.update()


def paintEvent(self, event: QPaintEvent | None) -> None:
    if not self.active_pulses:
        return
    painter = QPainter(self)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    now_ms = time.monotonic() * 1000
    for pulse in self.active_pulses.values():
        progress = min((now_ms - pulse.started_at) / self._pulse_duration_ms, 1.0)
        radius = 12 + int(progress * 26)
        alpha = max(0, int(180 * (1.0 - progress)))
        painter.setPen(QPen(QColor(255, 220, 120, alpha), 3))
        painter.setBrush(QColor(255, 240, 180, alpha // 3))
        painter.drawEllipse(pulse.center, radius, radius)
    painter.end()
```

    If the implementation wants direct control in tests, allow `_expire_stale_pulses(now_ms: float | None = None)` and default `now_ms` to `time.monotonic() * 1000` when omitted.

- [ ] **Step 3: Run the focused overlay lane**

Run: `uv run pytest -o addopts= tests/test_joystick_activity_overlay.py -q`

Expected: PASS.

- [ ] **Step 4: Commit the overlay widget**

```bash
git add app/components/joystick_activity_overlay.py tests/test_joystick_activity_overlay.py
git commit -m "feat: add joystick activity overlay widget"
```

### Task 8: Wire Selector Preview And Main Window To The Shared Monitor

**Files:**
- Modify: `app/components/joystick_selector_dialog.py`
- Modify: `app/ui.py`
- Modify: `tests/test_joystick_selector_dialog.py`
- Modify: `tests/test_ui.py`

- [ ] **Step 1: Add the preview image and overlay to the selector dialog**

Attach the overlay to the selector preview only when the current device has a supported layout.

Use the shared helper from `app/models/joystick_layout_support.py` so coordinate lookup is defined in one place:

```python
from app.models.joystick_layout_support import slot_positions_for_layout
from PyQt6.QtGui import QCloseEvent
```

```python
self.preview_overlay = JoystickActivityOverlay({}, parent=self.preview_image_label)
self.preview_overlay.hide()


def set_preview_device(self, device: DetectedJoystickDevice | None) -> None:
    self.selected_preview_device = device
    if device is None or device.layout_key is None:
        self.preview_status_label.setText("Visual preview unavailable for this device.")
        self.preview_overlay.setVisible(False)
        return
    assert device.layout_key is not None
    self.preview_status_label.setText(f"Listening for input from {device.display_name}")
    self.preview_overlay.set_slot_positions(
        slot_positions_for_layout(device.layout_key, self._preview_side_for_device(device))
    )
    self.preview_overlay.setVisible(True)


def _preview_side_for_device(self, device: DetectedJoystickDevice) -> Literal["left", "right"]:
    right_device = self.current_right_device()
    if right_device is not None and right_device.product_guid == device.product_guid:
        return "right"
    return "left"


def _handle_preview_activity(self, event: JoystickActivityEvent) -> None:
    if self.selected_preview_device is None:
        return
    if event.product_guid != self.selected_preview_device.product_guid:
        return
    self.preview_overlay.record_activity(event)
```

Connect the monitor `activity` signal in the dialog initializer so only matching device events reach the preview overlay.

```python
self.joystick_monitor.activity.connect(self._handle_preview_activity)
```

- [ ] **Step 2: Make the main window own one shared monitor instance**

Create the monitor in `ControlMapperApp.__init__`, pass it into `SettingsDialog`, attach a `JoystickActivityOverlay` as a child of `self.background_label`, and subscribe to events for the assigned left and right devices.

`self.background_label` already exists in the current window and remains the parent surface for both the mappable buttons and the new transparent overlay.

```python
self.joystick_monitor = JoystickMonitorService()
self._assigned_saved_instances: dict[str, int] = {}
self.joystick_activity_overlay = JoystickActivityOverlay(
    slot_positions=self._slot_positions_for_side(self.current_joystick),
    parent=self.background_label,
)
self.joystick_monitor.activity.connect(self._handle_joystick_activity)
self.joystick_monitor.start()
self._refresh_live_activity_assignments()
```

Add two explicit helpers so the wiring is not implicit:

```python
def _slot_positions_for_side(self, side: str) -> dict[str, QPoint]:
    return slot_positions_for_layout("vkb_default", "left" if side == "left" else "right")


def _refresh_live_activity_assignments(self) -> None:
    self._assigned_saved_instances = {
        "left": self.config.joystick_instance_left,
        "right": self.config.joystick_instance_right,
    }
    self.joystick_activity_overlay.set_slot_positions(
        self._slot_positions_for_side(self.current_joystick)
    )


def _handle_joystick_activity(self, event: JoystickActivityEvent) -> None:
    current_side = getattr(self, "current_joystick", None)
    if current_side not in {"left", "right"}:
        return
    assigned_side = next(
        (
            side
            for side, saved_instance in self._assigned_saved_instances.items()
            if saved_instance == event.saved_instance
        ),
        None,
    )
    if assigned_side is None or assigned_side != current_side:
        return
    self.joystick_activity_overlay.record_activity(event)


def closeEvent(self, event: QCloseEvent | None) -> None:
    self.joystick_monitor.activity.disconnect(self._handle_joystick_activity)
    self.joystick_monitor.stop()
    super().closeEvent(event)
```

In `_handle_joystick_activity()`:

- ignore devices that are not currently assigned to left or right,
- ignore events for the opposite side when the main window is showing the other joystick image,
- forward matching events to the overlay,
- do not change the selected binding button or action table state.

- [ ] **Step 3: Refresh assignment-aware subscriptions after Settings saves**

When Settings closes successfully, refresh any cached assigned-device lookup so live highlighting follows the new config immediately.

```python
def open_settings_dialog(self) -> None:
    dialog = SettingsDialog(self.config, self.joystick_monitor, parent=self)
    if dialog.exec():
        self.config = Config.get_config(force_reload=True)
        self._refresh_live_activity_assignments()
        self.update_joystick_buttons()
```

- [ ] **Step 4: Run the integrated Qt seam lane**

Run: `uv run pytest -o addopts= tests/test_joystick_selector_dialog.py tests/test_joystick_activity_overlay.py tests/test_ui.py -k "preview_tracks_activity or restarts_existing_pulse or expires_stale_pulse or highlights_matching_slot" -q`

Expected: PASS.

- [ ] **Step 5: Commit the overlay wiring**

```bash
git add app/components/joystick_selector_dialog.py app/ui.py tests/test_joystick_selector_dialog.py tests/test_ui.py
git commit -m "feat: add live joystick highlights to selector and main window"
```

## Chunk 4: Verification And Cleanup

### Task 9: Run The Feature Verification Lane

**Files:**
- Test: `tests/test_joystick_monitor.py`
- Test: `tests/test_joystick_selector_dialog.py`
- Test: `tests/test_joystick_activity_overlay.py`
- Test: `tests/test_ui.py`

- [ ] **Step 1: Run the focused non-Qt runtime lane, including edge cases**

Run: `uv run pytest -o addopts= tests/test_joystick_monitor.py -q`

Expected: PASS.

- [ ] **Step 2: Run the focused selector and overlay Qt lane**

Run: `uv run pytest -o addopts= tests/test_joystick_selector_dialog.py tests/test_joystick_activity_overlay.py -q`

Expected: PASS.

- [ ] **Step 3: Run the focused main-window live-activity seam**

Run: `uv run pytest -o addopts= tests/test_ui.py -k "highlights_matching_slot" -q`

Expected: PASS.

- [ ] **Step 4: Run the broad regression lane**

Run: `uv run pytest -q`

Expected: PASS.

- [ ] **Step 5: Run Ruff on the touched files**

Run: `uv run ruff check app/utils/devices.py app/models/joystick_layout_support.py app/services/joystick_monitor.py app/components/settings_dialog.py app/components/joystick_selector_dialog.py app/components/joystick_activity_overlay.py app/ui.py tests/test_joystick_monitor.py tests/test_joystick_selector_dialog.py tests/test_joystick_activity_overlay.py tests/test_ui.py`

Expected: `All checks passed!`

- [ ] **Step 6: Perform one manual smoke test with real hardware if available**

Run: `uv run citizenbindvkb`

Expected:

- Settings opens the selector dialog.
- `Refresh Devices` shows the connected VKB devices.
- Saving left and right assignments updates the Settings fields.
- Pressing a supported button, hat direction, or trigger causes a visible pulse in the selector preview.
- Closing Settings and pressing the same control causes a visible pulse in the main mapper window.

- [ ] **Step 7: Commit the verified feature slice**

```bash
git add app/utils/devices.py app/models/joystick_layout_support.py app/services/joystick_monitor.py app/services/__init__.py app/components/settings_dialog.py app/components/joystick_selector_dialog.py app/components/joystick_activity_overlay.py app/ui.py tests/test_joystick_monitor.py tests/test_joystick_selector_dialog.py tests/test_joystick_activity_overlay.py tests/test_ui.py
git commit -m "feat: add joystick selector and live activity overlays"
```

`self.current_joystick` is already a pre-existing `ControlMapperApp` field maintained by the current left/right toggle flow, so this task reuses that existing state rather than introducing a new side-selection variable.