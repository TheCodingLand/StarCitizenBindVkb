# Core Binding Engine M1 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first headless core milestone: repository-backed import/edit/export for Star Citizen profiles with an explicit left/right role-mapping seam and lossless passthrough preservation.

**Architecture:** Wrap the current XML, action-catalog, and VKB layout modules behind dedicated repositories, add a session-oriented domain model for working profiles and diagnostics, and keep validation headless inside a binding session service. Full stable hardware identity persistence is deferred to the next plan; this milestone uses an explicit imported-role mapping seam so import, edit, and export can be proven safely first.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, existing Star Citizen XML models, existing VKB layout metadata, existing `BindingPlanner` validation logic as a temporary validation backend.

---

## Planned File Structure

**Create**

- `app/domain/catalog.py` — versioned game-action catalog models used by repositories and session code.
- `app/domain/devices.py` — `DeviceRole`, temporary imported-device token mapping, and layout-facing descriptor types.
- `app/domain/session.py` — `TriggerMode`, `BindingEdit`, `WorkingProfile`, `BindingSession`, `ExportResult`, `PassthroughConflict`, `UnresolvedBinding`, `PassthroughRecord`, and session diagnostics.
- `app/io/action_catalog_repository.py` — adapter over `app/models/full_game_control_options.py` returning catalog domain models.
- `app/io/layout_repository.py` — adapter over existing VKB button metadata returning domain `DeviceLayoutDescriptor` values.
- `app/io/star_citizen_profile_repository.py` — import/export adapter between Star Citizen XML and the new working-profile model.
- `app/services/binding_session.py` — headless session service exposing the approved command surface for bind/unbind/export.
- `tests/fixtures/catalogs/live-sc-alpha-3.24.2.json` — frozen action-catalog fixture copied from repo data.
- `tests/fixtures/profiles/SCBindsDefault.xml` — frozen default-profile fixture copied from repo data.
- `tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml` — frozen real exported-profile fixture copied from repo data.
- `tests/fixtures/profiles/profile_with_unknowns.xml` — minimal fixture that intentionally contains at least one unknown action or slot.
- `tests/test_action_catalog_repository.py` — repository tests for versioned action-catalog loading.
- `tests/test_layout_repository.py` — repository tests for VKB layout adaptation.
- `tests/test_star_citizen_profile_repository.py` — import/export and passthrough-preservation tests.
- `tests/test_binding_session.py` — headless session command and conflict-handling tests.

**Modify**

- `app/domain/__init__.py` — export the new domain types while preserving the current imports used elsewhere.
- `app/io/__init__.py` — export the new repository classes.
- `app/io/repositories.py` — convert this file into a compatibility shim or remove its stubs after the new modules land.
- `app/services/__init__.py` — export `BindingSessionService` alongside the existing planner.

**Do Not Touch In This Plan**

- `app/ui.py` — keep the Qt shell unchanged in this milestone.
- `tests/test_ui.py` — do not expand the unstable Qt lane here.
- `app/utils/devices.py` — stable hardware identity work belongs to the next plan.

## Chunk 1: Contracts And Read Side

### Task 1: Freeze Core Fixtures And Red Tests

**Files:**
- Create: `tests/fixtures/catalogs/live-sc-alpha-3.24.2.json`
- Create: `tests/fixtures/profiles/SCBindsDefault.xml`
- Create: `tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml`
- Create: `tests/test_action_catalog_repository.py`
- Create: `tests/test_layout_repository.py`

- [ ] **Step 1: Validate and copy immutable fixtures from existing repo data**

Copy these source files into `tests/fixtures/` so tests stop depending on mutable app-packaging assets:

```text
app/data/LIVE/sc-alpha-3.24.2-9381373/actionmap.json -> tests/fixtures/catalogs/live-sc-alpha-3.24.2.json
app/data/SCBindsDefault.xml -> tests/fixtures/profiles/SCBindsDefault.xml
app/data/layout_VKB_final_3_22_exported.xml -> tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml
```

Create the target directories first:

```bash
mkdir -p tests/fixtures/catalogs tests/fixtures/profiles
```

Before copying, load each source once with the existing parser/helper so the fixture freeze does not snapshot corrupt input.

Use these exact validation helpers:

- `app/models/full_game_control_options.py:get_all_defined_game_actions(source_path)` for the frozen catalog JSON,
- `app/models/exported_configmap_xml.py:get_action_maps_object(str(source_path))` for the XML profile fixtures.

As part of this validation, confirm that the frozen action-catalog fixture contains `v_emergency_exit` so the later repository test is grounded in a known real action.

- [ ] **Step 2: Write the failing repository tests**

```python
from pathlib import Path

import pytest

from app.io import ActionCatalogRepository, DeviceLayoutRepository


def test_action_catalog_repository_loads_fixture_catalog() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json"))
    catalog = repo.load()

    assert catalog.version_key == "live-sc-alpha-3.24.2"
    assert "v_emergency_exit" in catalog.actions_by_name


def test_layout_repository_loads_vkb_default_left_layout() -> None:
    repo = DeviceLayoutRepository()
    layout = repo.load_layout("VKB Default", "left")

    assert layout is not None
    assert layout.side == "left"
    assert "button1" in layout.slots


def test_action_catalog_repository_raises_for_missing_file() -> None:
    repo = ActionCatalogRepository(Path("tests/fixtures/catalogs/missing.json"))

    with pytest.raises(FileNotFoundError):
        repo.load()


def test_layout_repository_returns_none_for_unknown_layout() -> None:
    repo = DeviceLayoutRepository()

    assert repo.load_layout("Missing Device", "left") is None
```

- [ ] **Step 3: Run tests to verify the red lane**

Run: `uv run pytest tests/test_action_catalog_repository.py tests/test_layout_repository.py -q`

Expected: FAIL with `ImportError`, `AttributeError`, or `NotImplementedError` because the new repositories do not exist yet.

- [ ] **Step 4: Commit the frozen fixtures and red tests**

```bash
git add tests/fixtures/catalogs/live-sc-alpha-3.24.2.json tests/fixtures/profiles/SCBindsDefault.xml tests/fixtures/profiles/layout_VKB_final_3_22_exported.xml tests/test_action_catalog_repository.py tests/test_layout_repository.py
git commit -m "test: add core repository fixtures"
```

### Task 2: Add Session-Oriented Domain Contracts

**Files:**
- Create: `app/domain/catalog.py`
- Create: `app/domain/devices.py`
- Create: `app/domain/session.py`
- Modify: `app/domain/__init__.py`
- Create: `tests/test_binding_session.py`

- [ ] **Step 1: Write the failing domain-model tests**

```python
from app.domain import BindingSession, Diagnostic, ExportResult, PassthroughRecord, TriggerMode, WorkingProfile


def test_working_profile_keeps_bindings_and_passthrough_separate() -> None:
    profile = WorkingProfile(profile_name="fixture")

    profile.passthrough_records.append(
        PassthroughRecord(
            record_id="pt-1",
            action_name="unknown_action",
            device_token="js2",
            slot_token="unknown_button",
            trigger_token="plain",
            raw_payload={"@input": "js2_unknown_button"},
        )
    )

    assert profile.bindings == []
    assert profile.passthrough_records[0].device_token == "js2"


def test_trigger_mode_value_is_stable() -> None:
    assert TriggerMode.PLAIN.value == "plain"


def test_export_result_starts_unblocked() -> None:
    result = ExportResult()

    assert result.blocked_conflicts == []
    assert result.preserved_passthrough_count == 0


def test_binding_session_exposes_profile_and_diagnostics() -> None:
    session = BindingSession(profile=WorkingProfile(profile_name="fixture"))

    assert session.profile.profile_name == "fixture"
    assert session.diagnostics == []
```

- [ ] **Step 2: Run the new test file to verify failure**

Run: `uv run pytest tests/test_binding_session.py -q`

Expected: FAIL because `WorkingProfile`, `PassthroughRecord`, `Diagnostic`, `BindingSession`, `ExportResult`, and `TriggerMode` are not exported yet.

- [ ] **Step 3: Implement the session and repository data contracts**

Use focused files instead of growing `app/domain/models.py` again.

File ownership in this task:

- `app/domain/catalog.py` — `GameCatalog`, `GameCatalogVersion`, and catalog-facing action definitions.
- `app/domain/devices.py` — `DeviceRole`, `LayoutSlot`, `DeviceLayoutDescriptor`, and the temporary imported-device token descriptor.
- `app/domain/session.py` — `TriggerMode`, `BindingEdit`, `WorkingProfile`, `Diagnostic`, `BindingSession`, `PassthroughRecord`, `PassthroughConflict`, and `ExportResult`.

```python
from app.domain.models import ActionDefinition, ActionIdentifier
from app.models.full_game_control_options import GameAction
from app.models.joystick import JoyStickButton


@dataclass(frozen=True)
class GameCatalogVersion:
    key: str


@dataclass
class GameCatalog:
    version: GameCatalogVersion
    actions_by_name: dict[str, list[ActionDefinition]] = field(default_factory=dict)

    @property
    def version_key(self) -> str:
        return self.version.key

    @classmethod
    def from_game_actions(
        cls,
        version_key: str,
        actions: dict[str, list[GameAction]],
    ) -> "GameCatalog":
        return cls(
            version=GameCatalogVersion(key=version_key),
            actions_by_name={
                name: [build_action_definition(item) for item in variants]
                for name, variants in actions.items()
            },
        )


def build_action_definition(item: GameAction) -> ActionDefinition:
    return ActionDefinition(
        identifier=ActionIdentifier(
            name=item.name,
            main_category=item.main_category or "",
            sub_category=item.sub_category or "",
        ),
        activation_modes=tuple(
            value
            for value in [item.activation_mode, item.on_press, item.on_hold, item.on_release]
            if value
        ),
        supports_joystick=item.joystick not in {None, "", " "},
    )


class DeviceRole(str, Enum):
    LEFT_STICK = "left_stick"
    RIGHT_STICK = "right_stick"


@dataclass(frozen=True)
class LayoutSlot:
    slot_id: str
    display_name: str
    sc_input_name: str


@dataclass
class DeviceLayoutDescriptor:
    device_name: str
    side: str
    slots: dict[str, LayoutSlot] = field(default_factory=dict)

class TriggerMode(str, Enum):
    PLAIN = "plain"
    MODIFIER = "modifier"
    HOLD = "hold"
    MULTITAP = "multitap"


@dataclass
class PassthroughRecord:
    record_id: str
    action_name: str
    device_token: str
    slot_token: str
    trigger_token: str
    raw_payload: dict[str, Any]


@dataclass
class Diagnostic:
    code: str
    level: str
    message: str


@dataclass
class BindingEdit:
    role: str
    slot_id: str
    action_name: str
    trigger_mode: TriggerMode
    source_record_id: str | None = None


@dataclass
class WorkingProfile:
    profile_name: str
    bindings: list[BindingEdit] = field(default_factory=list)
    passthrough_records: list[PassthroughRecord] = field(default_factory=list)


@dataclass
class PassthroughConflict:
    conflict_id: str
    record_id: str
    device_token: str
    slot_token: str
    trigger_token: str
    action_name: str


@dataclass
class ExportResult:
    changed_bindings: list[BindingEdit] = field(default_factory=list)
    preserved_passthrough_count: int = 0
    blocked_conflicts: list[PassthroughConflict] = field(default_factory=list)


@dataclass
class BindingSession:
    profile: WorkingProfile
    diagnostics: list[Diagnostic] = field(default_factory=list)
```

Contract notes for implementation:

- `GameCatalog.actions_by_name` intentionally keeps a list per action name because the existing parser returns multiple category-specific variants for the same action identifier.
- `DeviceLayoutDescriptor.slots` is a dictionary keyed by Star Citizen slot token such as `button1` or `hat1_up`; this is what Task 1 and Task 3 tests should assert against.
- `ActionDefinition` and `ActionIdentifier` should be reused from the existing domain module rather than duplicated in `app/domain/catalog.py`.
- `GameAction` comes from `app/models/full_game_control_options.py`; validate its real return type before adding annotations that differ from the parser output.
- The `build_layout()` helper belongs in `app/io/layout_repository.py` for this milestone; keep `app/domain/devices.py` limited to pure data contracts.

- [ ] **Step 4: Run the domain tests to verify they pass**

Run: `uv run pytest tests/test_binding_session.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the new domain contract layer**

```bash
git add app/domain/catalog.py app/domain/devices.py app/domain/session.py app/domain/__init__.py tests/test_binding_session.py
git commit -m "feat: add core session domain models"
```

### Task 3: Implement Catalog And Layout Repositories

**Files:**
- Create: `app/io/action_catalog_repository.py`
- Create: `app/io/layout_repository.py`
- Modify: `app/io/__init__.py`
- Modify: `app/io/repositories.py`
- Test: `tests/test_action_catalog_repository.py`
- Test: `tests/test_layout_repository.py`

- [ ] **Step 1: Re-run the repository red lane**

Run: `uv run pytest tests/test_action_catalog_repository.py tests/test_layout_repository.py -q`

Expected: FAIL because the new repositories are still missing.

- [ ] **Step 2: Implement the action-catalog repository by wrapping existing parser code**

Use the existing parser explicitly from `app/models/full_game_control_options.py:get_all_defined_game_actions` and return the new `GameCatalog` domain object rather than raw parser output.

```python
class ActionCatalogRepository:
    def __init__(self, source_path: Path, version_key: str | None = None) -> None:
        self.source_path = source_path
        self.version_key = version_key or source_path.stem

    def load(self) -> GameCatalog:
        actions = get_all_defined_game_actions(self.source_path)
        return GameCatalog.from_game_actions(self.version_key, actions)
```

- [ ] **Step 3: Implement the layout repository by adapting existing VKB metadata**

Use `app/models/joystick.py:get_joystick_buttons` as the source adapter. Define the `build_layout()` helper inside `app/io/layout_repository.py` in this task; do not assume a pre-existing shared utility.

Because `get_joystick_buttons()` currently raises `ValueError` for unsupported device names, catch that exception inside the repository and convert it to `None` so the repository contract stays narrow and predictable.

```python
class DeviceLayoutRepository:
    SUPPORTED_DEVICE = "VKB Default"

    def load_layout(self, device_name: str, side: str) -> DeviceLayoutDescriptor | None:
        if device_name != self.SUPPORTED_DEVICE:
            return None
        try:
            buttons = get_joystick_buttons(self.SUPPORTED_DEVICE)
        except ValueError:
            return None
        return build_layout(device_name=self.SUPPORTED_DEVICE, side=side, buttons=buttons)
```

- [ ] **Step 4: Run the repository tests to verify the read side passes**

Run: `uv run pytest tests/test_action_catalog_repository.py tests/test_layout_repository.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the repository adapters**

```bash
git add app/io/action_catalog_repository.py app/io/layout_repository.py app/io/__init__.py app/io/repositories.py
git commit -m "feat: add headless catalog and layout repositories"
```

## Chunk 2: Profile Import, Write Side, And Session Service

### Task 4: Add Import-Classification Red Tests

**Files:**
- Create: `tests/fixtures/profiles/profile_with_unknowns.xml`
- Create: `tests/test_star_citizen_profile_repository.py`

- [ ] **Step 1: Create a minimal fixture with at least one unresolved record**

Build `tests/fixtures/profiles/profile_with_unknowns.xml` from a small real control-map sample. Include:

- one known joystick binding that should become an editable binding,
- one unknown action or unknown slot that must survive as passthrough,
- one ordinary non-joystick record that must remain passthrough.

- [ ] **Step 2: Write failing import-classification tests**

```python
from pathlib import Path

from app.io import ActionCatalogRepository, DeviceLayoutRepository, StarCitizenProfileRepository


def test_load_profile_classifies_known_and_unknown_records() -> None:
    repo = StarCitizenProfileRepository(
        catalog_repo=ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json")),
        layout_repo=DeviceLayoutRepository(),
    )

    session = repo.load_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )

    assert session.profile.bindings
    assert session.profile.passthrough_records
    assert any(d.code == "unknown-slot" for d in session.diagnostics)
    assert session.profile.passthrough_records[0].device_token.startswith("js")
```

- [ ] **Step 3: Run the repository import tests to verify failure**

Run: `uv run pytest tests/test_star_citizen_profile_repository.py -q`

Expected: FAIL because `StarCitizenProfileRepository` and the returned session shape do not exist yet.

- [ ] **Step 4: Commit the import red lane**

```bash
git add tests/fixtures/profiles/profile_with_unknowns.xml tests/test_star_citizen_profile_repository.py
git commit -m "test: add profile import classification coverage"
```

### Task 5: Implement Star Citizen Profile Import With Explicit Role Mapping

**Files:**
- Create: `app/io/star_citizen_profile_repository.py`
- Modify: `app/io/__init__.py`
- Modify: `app/domain/session.py`
- Test: `tests/test_star_citizen_profile_repository.py`

- [ ] **Step 1: Implement the repository read path with the temporary explicit role seam**

The `load_profile()` contract for this milestone should accept `imported_role_map: dict[str, str]` so the core can be proven without the full device-matching service.

```python
session = repo.load_profile(
    profile_path,
    imported_role_map={"js1": "left_stick", "js2": "right_stick"},
)
```

- [ ] **Step 2: Classify imported records into editable bindings, unresolved views, and passthrough**

```python
if action_is_known and slot_is_known and role_is_known:
    profile.bindings.append(binding)
else:
    profile.passthrough_records.append(raw_record)
    diagnostics.append(Diagnostic(code="unknown-slot", level="warning", message="..."))
```

- [ ] **Step 3: Run the import tests to verify green**

Run: `uv run pytest tests/test_star_citizen_profile_repository.py -q`

Expected: PASS.

- [ ] **Step 4: Expand the import tests to cover non-destructive preservation**

Add one more assertion that an untouched unknown record is still present in the in-memory passthrough set and retains its imported `jsN` token.

- [ ] **Step 5: Re-run the expanded import test file and commit**

Run: `uv run pytest tests/test_star_citizen_profile_repository.py -q`

Expected: PASS.

```bash
git add app/io/star_citizen_profile_repository.py app/io/__init__.py app/domain/session.py tests/test_star_citizen_profile_repository.py
git commit -m "feat: import star citizen profiles into headless working sessions"
```

### Task 6: Add Export And Session-Service Red Tests

**Files:**
- Modify: `tests/test_binding_session.py`
- Modify: `tests/test_star_citizen_profile_repository.py`

- [ ] **Step 1: Add the failing session-command tests**

Use the exact `ExportResult` and `PassthroughConflict` contract created in Task 2.

```python
from pathlib import Path

from app.io import ActionCatalogRepository, DeviceLayoutRepository, StarCitizenProfileRepository
from app.services import BindingSessionService


def test_bind_and_export_updates_known_binding_without_dropping_passthrough() -> None:
    repo = StarCitizenProfileRepository(
        catalog_repo=ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json")),
        layout_repo=DeviceLayoutRepository(),
    )
    service = BindingSessionService(repo)

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("left_stick", "button1", "v_toggle_power", "plain")

    exported = service.export()

    assert exported.changed_bindings
    assert exported.preserved_passthrough_count >= 1


def test_export_blocks_when_edit_conflicts_with_passthrough() -> None:
    repo = StarCitizenProfileRepository(
        catalog_repo=ActionCatalogRepository(Path("tests/fixtures/catalogs/live-sc-alpha-3.24.2.json")),
        layout_repo=DeviceLayoutRepository(),
    )
    service = BindingSessionService(repo)

    service.open_profile(
        Path("tests/fixtures/profiles/profile_with_unknowns.xml"),
        imported_role_map={"js1": "left_stick", "js2": "right_stick"},
    )
    service.bind("right_stick", "unknown_button", "v_toggle_power", "plain")

    exported = service.export()

    assert exported.blocked_conflicts
    assert exported.blocked_conflicts[0].slot_token == "unknown_button"
```

- [ ] **Step 2: Run the new export/session tests to verify the red lane**

Run: `uv run pytest tests/test_binding_session.py tests/test_star_citizen_profile_repository.py -q`

Expected: FAIL because `BindingSessionService` and export conflict handling do not exist yet.

- [ ] **Step 3: Commit the red session tests**

```bash
git add tests/test_binding_session.py tests/test_star_citizen_profile_repository.py
git commit -m "test: add headless session export coverage"
```

### Task 7: Implement Export Preservation And The Binding Session Service

**Files:**
- Create: `app/services/binding_session.py`
- Modify: `app/services/__init__.py`
- Modify: `app/io/star_citizen_profile_repository.py`
- Test: `tests/test_binding_session.py`
- Test: `tests/test_star_citizen_profile_repository.py`

- [ ] **Step 1: Implement the session command surface exactly as approved in the spec**

Conflict detection timing for this milestone is explicit: `bind()` and `unbind()` update session state but do not reject passthrough overlaps immediately. Overlaps are detected when `export()` assembles the final write set.

Start with these methods only:

```python
class BindingSessionService:
    def open_profile(self, path: Path, imported_role_map: dict[str, str]) -> BindingSession: ...
    def bind(self, role: str, slot: str, action: str, trigger_mode: str) -> BindingSession: ...
    def unbind(self, role: str, slot: str, trigger_mode: str) -> BindingSession: ...
    def replace_passthrough(self, conflict_id: str, replacement_binding: BindingInput) -> BindingSession: ...
    def preserve_passthrough(self, conflict_id: str) -> BindingSession: ...
    def discard_pending_edit(self, conflict_id: str) -> BindingSession: ...
    def export(self) -> ExportResult: ...
```

- [ ] **Step 2: Reuse the current planner as a temporary validation backend**

Translate only editable session bindings into the existing `Binding`/`ControlProfile` shape before export validation so this milestone does not rewrite duplicate-slot detection and import/export logic in the same change.

Detect editable-vs-passthrough conflicts separately inside `BindingSessionService.export()` by comparing `(device_token, slot_token, trigger_token)` keys before planner validation runs.

```python
validation_report = self._planner.validate_plan(
    self._planner.plan_from_profile(self._to_control_profile(self._session.profile))
)
```

- [ ] **Step 3: Implement export so resolved records are rewritten and passthrough records are preserved**

Rules to enforce in code:

- resolved bindings write through the explicit role-to-imported-token seam,
- untouched passthrough records are re-emitted unchanged,
- conflicting passthrough overlaps block export until the caller resolves them,
- export never silently emits both an edited binding and a colliding passthrough record,
- `export()` returns `ExportResult(blocked_conflicts=[...])` instead of throwing when passthrough overlap blocks the write set.

- [ ] **Step 4: Run the headless core tests to verify green**

Run: `uv run pytest tests/test_action_catalog_repository.py tests/test_layout_repository.py tests/test_star_citizen_profile_repository.py tests/test_binding_session.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the first working headless core**

```bash
git add app/services/binding_session.py app/services/__init__.py app/io/star_citizen_profile_repository.py tests/test_binding_session.py tests/test_star_citizen_profile_repository.py
git commit -m "feat: add headless binding session service"
```

### Task 8: Add Compatibility Shims And Run Focused Quality Gates

**Files:**
- Modify: `app/io/repositories.py`
- Modify: `app/io/__init__.py`
- Modify: `app/domain/__init__.py`
- Modify: `app/services/__init__.py`

- [ ] **Step 1: Keep package imports stable while the UI remains unchanged**

If any code still imports from `app.io.repositories`, turn that module into a compatibility shim that re-exports the new repository classes instead of leaving dead stubs behind.

```python
from .action_catalog_repository import ActionCatalogRepository
from .layout_repository import DeviceLayoutRepository
from .star_citizen_profile_repository import StarCitizenProfileRepository
```

- [ ] **Step 2: Run the focused repository and service tests again**

Run: `uv run pytest tests/test_action_catalog_repository.py tests/test_layout_repository.py tests/test_star_citizen_profile_repository.py tests/test_binding_session.py tests/test_binding_planner.py tests/test_config.py -q`

Expected: PASS.

- [ ] **Step 3: Run focused static checks on the new files**

Run: `uv run ruff check app/domain/catalog.py app/domain/devices.py app/domain/session.py app/io/action_catalog_repository.py app/io/layout_repository.py app/io/star_citizen_profile_repository.py app/services/binding_session.py tests/test_action_catalog_repository.py tests/test_layout_repository.py tests/test_star_citizen_profile_repository.py tests/test_binding_session.py`

Expected: PASS.

- [ ] **Step 4: Commit the quality-gated milestone**

```bash
git add app/io/repositories.py app/io/__init__.py app/domain/__init__.py app/services/__init__.py
git commit -m "chore: finalize headless core milestone wiring"
```

## Notes For The Next Plan

- Replace the temporary `imported_role_map` seam with the real stable device matching service and persisted role assignments.
- Move export instance-token assignment from temporary imported-token mapping to actual current-device identity matching.
- Start migrating `app/ui.py` to call `BindingSessionService` instead of owning import/export logic directly.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-11-core-binding-engine-m1.md`. Ready to execute?