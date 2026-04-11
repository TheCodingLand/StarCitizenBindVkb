---
name: forge-repo-orientation
description: Use when working in the Forge repository and you need a concise map of subsystem roles, example placement, local run flows, persistence modes, and the verification lanes required before trusting protocol-heavy changes.
---

# Forge Repo Orientation

## Overview

Forge has three main layers: `forge/engine` for execution, `forge/server` for transport and session orchestration, and `studio/src` for the React/Vite frontend. Persistent truth is projects, blueprints, and credentials. Live execution sessions and runtime state are still process-local.

Prefer current code and tests over older analysis docs if they disagree.

## Repo Map

- `forge/engine/`: blueprint model, executor, events, mailboxes, service context, serialization.
- `forge/nodes/`: built-in node library and domain integrations.
- `forge/server/`: FastAPI app factory, REST routes, WebSocket transport, sessions, principals, credentials.
- `forge/db/`: PostgreSQL schema and durable store implementations.
- `forge/providers/`: provider registration and entry-point loading.
- `studio/src/protocol/`: HTTP and WebSocket client boundary.
- `studio/src/projection/`: event normalization and protocol-to-UI projection helpers.
- `studio/src/state/`: app/runtime state machines and shared context.
- `studio/src/graph/`: graph canvas/editor concerns.
- `studio/src/panels/` and `studio/src/app/`: Studio shell and feature panels.
- `examples/`: standalone Python scripts that should run directly.
- `forge/seed.py`: server-seeded demo blueprints that should appear in a running Forge instance.
- `tests/forge/test_e2e.py`: the clearest end-to-end truth for REST -> session -> executor -> WebSocket.

## Where Things Go

- Put standalone developer examples in `examples/`.
- Put server-visible demo blueprints in `forge/seed.py`.
- Put reusable backend behavior under `forge/engine`, `forge/nodes`, `forge/server`, or `forge/db` based on ownership.
- Put Studio transport code in `studio/src/protocol`, projection/state logic in `studio/src/projection` or `studio/src/state`, and screen-level UI in `studio/src/app`, `studio/src/panels`, or `studio/src/graph`.
- Put specs and plans under `docs/superpowers/`; tests are not documentation and demos are not a substitute for tests.

Rule of thumb:
- If it should be runnable as `uv run python examples/...`, it belongs in `examples/`.
- If it should appear inside Studio after seeding, it belongs in `forge/seed.py`.

## Runbook

- Full local dev: `uv run forge-dev`
  - Starts backend on `127.0.0.1:8989` and Studio dev server.
  - Uses `FORGE_DEV_PRINCIPAL`, defaulting to `local-dev`.
- Studio only: `cd studio && npm run dev`
- CLI engine demo: `uv run forge-demo`
- Seed demo blueprints into a running server: `uv run forge-seed-demos --principal local-dev`
- Run a standalone example: `uv run python examples/voice_chatbot.py`

`forge-dev` auto-runs `npm install` for Studio if `studio/node_modules` is missing.

## Persistence

- No `DATABASE_URL`: in-memory project store, blueprint store, and principal-aware credential backend.
- With `DATABASE_URL`: `create_app()` swaps in `PgProjectStore`, `PgBlueprintStore`, and `PgCredentialStore` during lifespan startup.
- Initialize schema with `uv run forge-db-init`.
- Start local persistence infra with `docker compose up -d postgres`.

What is durable in DB mode:
- Projects
- Blueprints
- Credentials

What is not durable:
- Live execution sessions
- Runtime executor state
- WebSocket subscriptions

Important details:
- Projects and blueprints are principal-scoped.
- Blueprints are versioned in PostgreSQL.
- Credentials are encrypted with Fernet; the key comes from `FORGE_CREDENTIAL_KEY` or is stored in `forge_meta`.
- Execution sessions remain in memory and are pruned by terminal-session TTL.

## Verification Discipline

Do not trust unit tests alone for protocol-heavy changes. Forge’s fragile boundary is usually REST/WS/Studio/runtime interaction, not isolated class logic.

Minimum verification by change type:

- Protocol / server / Studio transport changes:
  - `uv run pytest tests/forge/test_wire.py tests/forge/test_ws.py tests/forge/test_e2e.py -v`
  - `npm --prefix studio run test -- src/protocol/client.test.ts src/protocol/ws.test.ts src/app/LiveApp.test.tsx`
  - Run `uv run forge-dev`, seed demos if needed, and exercise the affected flow in Studio.

- Seeded demo changes:
  - `uv run pytest tests/forge/test_seed.py -v`
  - `uv run forge-seed-demos --principal local-dev`
  - Verify the demo from the running app, not just from serialization tests.

- Persistence changes:
  - `docker compose up -d postgres`
  - `uv run forge-db-init`
  - `FORGE_TEST_PG=1 uv run pytest tests/forge/test_pg_store.py -v`

- Voice / audio / end-to-end media changes:
  - Run the relevant backend tests such as `tests/forge/test_audio_loop_e2e.py` or `tests/forge/test_audio_roundtrip.py`
  - Run `uv run python examples/voice_chatbot.py` when the change touches the voice pipeline.

Golden rule:
- If the change crosses backend transport, runtime events, or Studio state, verify it through a real demo or E2E path before declaring success.

## Common Mistakes

- Treating old skeptical-analysis docs as canonical when current code/tests disagree.
- Assuming Studio panels or editor conveniences define backend protocol truth.
- Assuming DB mode makes sessions durable.
- Putting seeded demos in `examples/` or standalone scripts in `forge/seed.py`.
- Declaring protocol work done after unit tests without running a demo or end-to-end path.
