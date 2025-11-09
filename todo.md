# CitizenBindVkb Refactor Roadmap

## Tooling and Build
- [x] Exercise the new `uv` workflow (`uv sync`, `uv run`). _Next:_ remove or document `requirements.txt` deprecation.
- [x] Capture locking/release strategy (e.g. `uv lock`) and wire it into CI. `uv.lock` now checked in; add CI step later.
- [ ] Validate the Nuitka build script on Windows and produce a distributable artifact. *(Blocked pending service/domain refactor.)*
- [ ] Decide whether the Nuitka build should be `onefile` or directory based for faster launches.
- [ ] Add packaging docs to `README.md` once the build path is confirmed.

## Codebase Cleanup
- [ ] Stabilize the remaining TODOs in `app/ui.py` (action panel refresh, unsupported actions table, export flow).
- [ ] Extract joystick binding state management into dedicated service modules to trim the QWidget class size.
- [ ] Normalize data flow between `app/models` and `app/utils` (remove circular imports and duplicated helpers).
- [ ] Audit `app/models/exported_configmap_xml.py` for dead fields and tighten type hints.
- [ ] Introduce central configuration loading in `app/config.py` with caching/validation.

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
- [ ] Update PyQt layer to consume service APIs via lightweight view models instead of manipulating XML directly.
