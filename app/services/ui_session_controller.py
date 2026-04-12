from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from pathlib import Path
from typing import TypeAlias

from app.domain import BindingReference, BindingSession, Diagnostic, TriggerMode, UnresolvedBinding
from app.models.joystick import JoyStickButton

from .binding_session import BindingSessionService
from .ui_models import (
    ProjectedSessionView,
    SessionCatalogEntry,
    UiCommandOutcome,
    UiDiagnosticRow,
    UiExportState,
)
from .ui_projection import build_session_catalog_entries, project_session_view


ROLE_TO_SIDE = {
    "left_stick": "left",
    "right_stick": "right",
}

SIDE_TO_ROLE = {
    "left": "left_stick",
    "right": "right_stick",
}

ResolverValue: TypeAlias = str | Iterable[str] | None
ImportedRoleResolver: TypeAlias = Callable[[Path], Mapping[str, ResolverValue]]


class UiSessionController:
    def __init__(
        self,
        *,
        session_service: BindingSessionService,
        imported_role_resolver: ImportedRoleResolver,
        joystick_buttons_by_slot: Mapping[str, JoyStickButton],
        logger: logging.Logger | None = None,
    ) -> None:
        self._session_service = session_service
        self._imported_role_resolver = imported_role_resolver
        self._joystick_buttons_by_slot = dict(joystick_buttons_by_slot)
        self._logger = logger or logging.getLogger(__name__)

        self._session: BindingSession | None = None
        self._projection = ProjectedSessionView()
        self._catalog_entries: list[SessionCatalogEntry] = []
        self._load_diagnostics: list[UiDiagnosticRow] = []
        self._command_diagnostics: list[UiDiagnosticRow] = []
        self._validation_diagnostics: list[UiDiagnosticRow] = []
        self._projection_diagnostics: list[UiDiagnosticRow] = []
        self._export_state = UiExportState()

    @property
    def session(self) -> BindingSession | None:
        return deepcopy(self._session)

    @property
    def left_config(self):
        return self._projection.left_config.model_copy(deep=True)

    @property
    def right_config(self):
        return self._projection.right_config.model_copy(deep=True)

    @property
    def binding_rows(self) -> list:
        return list(self._projection.binding_rows)

    @property
    def catalog_entries(self) -> list[SessionCatalogEntry]:
        return list(self._catalog_entries)

    @property
    def load_diagnostics(self) -> list[UiDiagnosticRow]:
        return list(self._load_diagnostics)

    @property
    def command_diagnostics(self) -> list[UiDiagnosticRow]:
        return list(self._command_diagnostics)

    @property
    def validation_diagnostics(self) -> list[UiDiagnosticRow]:
        return list(self._validation_diagnostics)

    @property
    def projection_diagnostics(self) -> list[UiDiagnosticRow]:
        return list(self._projection_diagnostics)

    @property
    def diagnostics(self) -> list[UiDiagnosticRow]:
        return self._dedupe_diagnostic_rows(
            [
                *self._load_diagnostics,
                *self._command_diagnostics,
                *self._validation_diagnostics,
                *self._projection_diagnostics,
            ]
        )

    @property
    def export_state(self) -> UiExportState:
        return deepcopy(self._export_state)

    def open_profile(self, path: Path) -> bool:
        try:
            imported_role_map = self._normalize_imported_role_map(self._imported_role_resolver(path))
            session = self._session_service.open_profile(path, imported_role_map)
        except Exception:
            self._logger.exception("Failed to open profile %s", path)
            self._reset_state()
            return False

        self._session = session
        self._load_diagnostics = self._normalize_backend_diagnostics(
            session.diagnostics,
            session.profile.unresolved_bindings,
            session.profile.role_device_tokens,
        )
        self._command_diagnostics = []
        self._validation_diagnostics = []
        self._refresh_projection_state()
        self._refresh_export_state()
        return True

    def remove_binding(self, binding_ref: BindingReference) -> UiCommandOutcome:
        if self._session is None:
            self._command_diagnostics = [
                UiDiagnosticRow(
                    kind="no-session",
                    action="",
                    detail="No profile is open.",
                    side="unknown",
                )
            ]
            return UiCommandOutcome.REJECTED
        return self._run_command(lambda: self._session_service.remove_binding(binding_ref))

    def move_binding(self, binding_ref: BindingReference, target_slot: str) -> UiCommandOutcome:
        if self._session is None:
            self._command_diagnostics = [
                UiDiagnosticRow(
                    kind="no-session",
                    action="",
                    detail="No profile is open.",
                    side="unknown",
                )
            ]
            return UiCommandOutcome.REJECTED
        return self._run_command(lambda: self._session_service.move_binding(binding_ref, target_slot))

    def select_action(
        self,
        side: str,
        target_slot: str,
        action_name: str,
        trigger_mode: TriggerMode,
    ) -> UiCommandOutcome:
        if self._session is None:
            self._command_diagnostics = [
                UiDiagnosticRow(
                    kind="no-session",
                    action=action_name,
                    detail="No profile is open.",
                    side=side if side in SIDE_TO_ROLE else "unknown",
                )
            ]
            return UiCommandOutcome.REJECTED

        role = SIDE_TO_ROLE.get(side)
        if role is None:
            self._command_diagnostics = [
                UiDiagnosticRow(
                    kind="unknown-side",
                    action=action_name,
                    detail=f"Side '{side}' cannot be mapped to a controller role.",
                    side="unknown",
                )
            ]
            return UiCommandOutcome.REJECTED

        if not any(
            entry.action_name == action_name
            for entry in build_session_catalog_entries(
                self._session.catalog_snapshot.catalog,
                selected_trigger_mode=trigger_mode,
            )
        ):
            self._command_diagnostics = [self._invalid_action_selection_diagnostic(action_name, side, trigger_mode)]
            return UiCommandOutcome.REJECTED

        renderable_matches = [
            row
            for row in self._projection.binding_rows
            if row.side == side
            and row.action_name == action_name
            and row.binding_ref.trigger_mode is trigger_mode
        ]
        if renderable_matches:
            if len(self._session.catalog_snapshot.catalog.actionmaps_by_name.get(action_name, ())) > 1:
                self._command_diagnostics = [
                    UiDiagnosticRow(
                        kind="ambiguous-actionmap",
                        action=action_name,
                        detail=(
                            f"Action '{action_name}' requires actionmap provenance and cannot be moved through the picker."
                        ),
                        side=side,
                    )
                ]
                return UiCommandOutcome.REJECTED

            row = renderable_matches[0]
            if row.slot_id == target_slot:
                self._command_diagnostics = []
                return UiCommandOutcome.NOOP
            return self.move_binding(row.binding_ref, target_slot)

        return self._run_command(
            lambda: self._session_service.bind(role, target_slot, action_name, trigger_mode.value)
        )

    def _run_command(self, operation: Callable[[], BindingSession]) -> UiCommandOutcome:
        assert self._session is not None

        previous_session = self._session
        before_snapshot = self._binding_snapshot(self._session)
        before_diagnostics = list(self._session.diagnostics)
        try:
            updated_session = operation()
        except Exception as exc:
            self._logger.exception("Controller command failed")
            self._refresh_projection_state()
            self._command_diagnostics = [
                UiDiagnosticRow(
                    kind="command-error",
                    action="",
                    detail=str(exc),
                    side="unknown",
                )
            ]
            return UiCommandOutcome.REJECTED

        if updated_session is not None:
            self._session = updated_session

        self._refresh_projection_state()
        assert self._session is not None
        if self._session is previous_session or self._session.diagnostics[: len(before_diagnostics)] == before_diagnostics:
            appended = self._session.diagnostics[len(before_diagnostics):]
        else:
            appended = list(self._session.diagnostics)
        self._command_diagnostics = self._normalize_backend_diagnostics(appended)
        after_snapshot = self._binding_snapshot(self._session)

        if after_snapshot != before_snapshot:
            self._refresh_export_state()
            return UiCommandOutcome.MUTATED
        if self._command_diagnostics:
            return UiCommandOutcome.REJECTED
        self._command_diagnostics = []
        return UiCommandOutcome.NOOP

    def _refresh_projection_state(self) -> None:
        if self._session is None:
            self._projection = ProjectedSessionView()
            self._catalog_entries = []
            self._projection_diagnostics = []
            return

        self._projection = project_session_view(
            self._session,
            joystick_buttons_by_slot=self._joystick_buttons_by_slot,
        )
        self._catalog_entries = build_session_catalog_entries(self._session.catalog_snapshot.catalog)
        self._projection_diagnostics = self._dedupe_diagnostic_rows(self._projection.diagnostics)

    def _refresh_export_state(self) -> None:
        if self._session is None:
            self._validation_diagnostics = []
            self._export_state = UiExportState()
            return

        before_diagnostic_count = len(self._session.diagnostics)
        try:
            export_result = self._session_service.export()
        except Exception:
            self._logger.exception("Dry-run export failed")
            self._validation_diagnostics = []
            self._export_state = UiExportState()
            return

        appended = self._session.diagnostics[before_diagnostic_count:]
        self._validation_diagnostics = self._normalize_backend_diagnostics(appended)
        export_enabled = export_result.document is not None and not export_result.blocked_conflicts
        self._export_state = UiExportState(
            document=export_result.document if export_enabled else None,
            blocked_conflicts=list(export_result.blocked_conflicts),
            validation_diagnostics=list(self._validation_diagnostics),
            export_enabled=export_enabled,
        )

    def _invalid_action_selection_diagnostic(
        self,
        action_name: str,
        side: str,
        trigger_mode: TriggerMode,
    ) -> UiDiagnosticRow:
        assert self._session is not None
        catalog = self._session.catalog_snapshot.catalog
        if action_name not in catalog.actions_by_name:
            return UiDiagnosticRow(
                kind="unknown-action",
                action=action_name,
                detail=f"Action '{action_name}' is not present in the active session catalog.",
                side=side,
            )

        if len(catalog.actionmaps_by_name.get(action_name, ())) > 1:
            return UiDiagnosticRow(
                kind="ambiguous-actionmap",
                action=action_name,
                detail=f"Action '{action_name}' requires actionmap provenance and cannot be selected directly.",
                side=side,
            )

        return UiDiagnosticRow(
            kind="unsupported-trigger-mode",
            action=action_name,
            detail=(
                f"Action '{action_name}' does not support trigger mode '{trigger_mode.value}'."
            ),
            side=side,
        )

    @staticmethod
    def _normalize_imported_role_map(
        role_map: Mapping[str, ResolverValue],
    ) -> dict[str, str]:
        resolved: dict[str, str] = {}
        role_to_tokens: dict[str, list[str]] = {}
        for device_token, candidate_roles in role_map.items():
            roles = UiSessionController._normalize_role_candidates(candidate_roles)
            if len(roles) != 1:
                continue
            role = roles[0]
            if role not in ROLE_TO_SIDE:
                continue
            resolved[device_token] = role
            role_to_tokens.setdefault(role, []).append(device_token)

        duplicated_roles = {role for role, tokens in role_to_tokens.items() if len(tokens) > 1}
        return {
            device_token: role
            for device_token, role in resolved.items()
            if role not in duplicated_roles
        }

    @staticmethod
    def _normalize_role_candidates(candidate_roles: ResolverValue) -> tuple[str, ...]:
        if candidate_roles is None:
            return ()
        if isinstance(candidate_roles, str):
            normalized = candidate_roles.strip()
            return (normalized,) if normalized else ()
        if not isinstance(candidate_roles, Iterable):
            return ()
        unique_roles: list[str] = []
        for role in candidate_roles:
            normalized = str(role).strip()
            if normalized and normalized not in unique_roles:
                unique_roles.append(normalized)
        return tuple(unique_roles)

    @staticmethod
    def _binding_snapshot(session: BindingSession) -> list[tuple[str, str, str, TriggerMode, str | None, str | None, str | None]]:
        return sorted(
            (
                binding.role,
                binding.slot_id,
                binding.action_name,
                binding.trigger_mode,
                binding.modifier_token,
                binding.source_actionmap_name,
                binding.replaced_passthrough_record_id,
            )
            for binding in session.profile.bindings
        )

    @classmethod
    def _normalize_backend_diagnostics(
        cls,
        diagnostics: Iterable[Diagnostic],
        unresolved_bindings: Iterable[UnresolvedBinding] = (),
        role_device_tokens: Mapping[str, str] | None = None,
    ) -> list[UiDiagnosticRow]:
        unresolved_by_record_id = {
            unresolved.record_id: unresolved
            for unresolved in unresolved_bindings
            if unresolved.record_id
        }
        device_token_to_side = {
            device_token: ROLE_TO_SIDE.get(role, "unknown")
            for role, device_token in (role_device_tokens or {}).items()
        }
        rows: list[UiDiagnosticRow] = []
        used_record_ids: set[str] = set()

        for diagnostic in diagnostics:
            unresolved = unresolved_by_record_id.get(diagnostic.record_id or "")
            rows.append(
                UiDiagnosticRow(
                    kind=diagnostic.code,
                    action=unresolved.action_name if unresolved is not None else "",
                    detail=diagnostic.message,
                    side=(
                        device_token_to_side.get(unresolved.device_token, "unknown")
                        if unresolved is not None
                        else "unknown"
                    ),
                    record_id=diagnostic.record_id,
                )
            )
            if diagnostic.record_id:
                used_record_ids.add(diagnostic.record_id)

        for unresolved in unresolved_bindings:
            if unresolved.record_id in used_record_ids:
                continue
            rows.append(
                UiDiagnosticRow(
                    kind=unresolved.reason,
                    action=unresolved.action_name,
                    detail=(
                        f"Device token '{unresolved.device_token}' on slot '{unresolved.slot_token}' could not be resolved."
                    ),
                    side="unknown",
                    record_id=unresolved.record_id,
                )
            )

        return cls._dedupe_diagnostic_rows(rows)

    @staticmethod
    def _dedupe_diagnostic_rows(rows: Iterable[UiDiagnosticRow]) -> list[UiDiagnosticRow]:
        deduped: list[UiDiagnosticRow] = []
        seen_record_ids: set[str] = set()
        seen_rows: set[tuple[str, str, str, str]] = set()

        for row in rows:
            if row.record_id is not None:
                if row.record_id in seen_record_ids:
                    continue
                seen_record_ids.add(row.record_id)
                deduped.append(row)
                continue

            key = (row.kind, row.action, row.detail, row.side)
            if key in seen_rows:
                continue
            seen_rows.add(key)
            deduped.append(row)

        return deduped

    def _reset_state(self) -> None:
        self._session = None
        self._projection = ProjectedSessionView()
        self._catalog_entries = []
        self._load_diagnostics = []
        self._command_diagnostics = []
        self._validation_diagnostics = []
        self._projection_diagnostics = []
        self._export_state = UiExportState()
