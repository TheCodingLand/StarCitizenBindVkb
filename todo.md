# CitizenBindVkb Refactor Roadmap

## Tooling and Build
- [x] Exercise the new `uv` workflow (`uv sync`, `uv run`). _Next:_ remove or document `requirements.txt` deprecation.
- [x] Capture locking/release strategy (e.g. `uv lock`) and wire it into CI. `uv.lock` now checked in; add CI step later.
- [ ] Validate the Nuitka build script on Windows and produce a distributable artifact. *(Blocked pending service/domain refactor.)*
- [ ] Decide whether the Nuitka build should be `onefile` or directory based for faster launches.
- [ ] Add packaging docs to `README.md` once the build path is confirmed.

## Codebase Cleanup
- [ ] Stabilize the remaining TODOs in `app/ui.py` (action panel refresh, unsupported actions table, export flow). *Joystick side mapping hardened; action panel refresh auto-syncs; unsupported table counts + styles entries; export work still open.*
- [ ] Extract joystick binding state management into dedicated service modules to trim the QWidget class size.
- [ ] Normalize data flow between `app/models` and `app/utils` (remove circular imports and duplicated helpers).
- [ ] Audit `app/models/exported_configmap_xml.py` for dead fields and tighten type hints.
- [x] Introduce central configuration loading in `app/config.py` with caching/validation. *Config path override + cache tests in place.*
- [x] Decide how to handle control-map slider inputs (current startup logs `slider1` warnings). *Slider inputs now skipped silently during mapping to avoid noisy logs.*

## Testing and Quality
- [ ] Stabilize the Qt UI tests (pytest-qt fixtures, headless execution) and cover regression paths.
- [ ] Introduce unit coverage around XML export/import round-trips.
- [ ] Add type-checking (mypy) and linting (ruff) gates to CI.
- [ ] Set up smoke tests for the Nuitka binary (launch, open dialog, exit).

## Feature Planning
- [ ] Revisit joystick modifier UX (toggle states, visual affordances, persistence).
- [ ] Implement action search/filtering within the UI dialog.
- [ ] Support importing/exporting presets beyond SC default (`app/data/Localization`).
- [ ] Investigate multi-device layouts and dynamic button maps.
- [ ] Collect user feedback to prioritize advanced mapping features.

## Architecture & Data Model
- [x] Introduce `app/domain`, `app/io`, and `app/services` packages with segregated responsibilities.
- [x] Spec and implement core models (`ActionDefinition`, `DeviceLayout`, `Binding`, `BindingSet`, `ControlProfile`).
- [x] Build a `BindingPlanner` service that reconciles XML imports with UI edits and emits `ValidationReport`s.
- [ ] Finish migrating the PyQt layer to consume service APIs (diff removals, targeted refreshes, view models).
- [x] Expand planner validation (modifier conflicts, duplicate slots) and cover it with focused unit tests. *`BindingPlanner.validate_plan` now flags slot duplication/modifier clashes; see `tests/test_binding_planner.py`.*
- [ ] Review validation messaging for additional edge cases (hold/multitap overlaps, device mismatches) once Planner consumers surface new issues.
- [ ] Quieten the Windows `pytest-qt` COM fatal exception (0x8001010d) so test runs exit cleanly.
