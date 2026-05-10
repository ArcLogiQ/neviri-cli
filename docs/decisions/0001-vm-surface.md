# ADR 0001: `neviri vm` wraps `/api/v1/compute/servers/*`

- **Date:** 2026-05-07
- **Status:** Accepted
- **Phase:** 1
- **Author:** Backend Team

## Context

The Neviri backend exposes two VM-shaped router surfaces:

| Surface | Path prefix | Endpoints | Notes |
|---|---|---|---|
| `vm` router (`app/routers/vm.py`) | `/api/v1/vm/*` | create, list (`/all`), get, start, stop, delete, status — **7 endpoints** | DB-tracked bookkeeping; **no reboot, no resize, no console** |
| `compute` router (`app/routers/compute.py`) | `/api/v1/compute/servers/*` | full CRUD + action (start/stop/reboot/pause/suspend/resume), resize (+ confirm/revert), console, plus `/flavors` and `/images` — **~14 endpoints** | OpenStack-direct |

The proposal's command surface (§4.5) calls for:

```
neviri vm   list | create | get | delete | start | stop | reboot | resize | console
```

These commands cannot all be served by `/api/v1/vm/*` — `reboot`, `resize`, and `console` only exist on the `compute` surface.

## Decision

`neviri vm` wraps **`/api/v1/compute/servers/*`**.

The `/api/v1/vm/*` surface is **not exposed** by the CLI in Phase 1.

## Consequences

**Positive**
- Full command set (reboot, resize, console) works without the CLI proxying or compositing two backends.
- Single source of truth — `neviri vm <action>` always reflects the OpenStack-direct view.
- The `/api/v1/vm/*` router can be deprecated by the backend without breaking the CLI.

**Negative**
- DB-side metadata that `/api/v1/vm/*` tracks (currently used for billing-related bookkeeping) is not surfaced via the CLI in Phase 1. If this becomes a need later, it can ship as a separate `neviri billing` or `neviri vm-record` command without conflict.

## Console behavior

`GET /api/v1/compute/servers/{id}/console` returns a noVNC URL by default (or SPICE/xvpvnc if requested via `?console_type=`). The CLI's `neviri vm console <id>` command:

- Prints the URL to stdout by default (scriptable, pipeable)
- Optionally launches it in the user's default browser via `--launch` (off by default; `webbrowser.open()`)
- Does **not** proxy a serial console or SSH connection — those are not exposed by the backend

## Verb-to-action mapping

The CLI maps verb commands onto the `POST /servers/{id}/action` endpoint as follows:

| CLI command | Backend action |
|---|---|
| `neviri vm start <id>` | `POST /servers/{id}/action` body `{"action":"start"}` |
| `neviri vm stop <id>` | body `{"action":"stop"}` |
| `neviri vm reboot <id> [--soft\|--hard]` | body `{"action":"reboot","reboot_type":"SOFT\|HARD"}` |
| `neviri vm resize <id> --flavor <fid>` | `POST /servers/{id}/resize` body `{"flavor_id":"<fid>"}` |
| `neviri vm resize-confirm <id>` | `POST /servers/{id}/resize/confirm` |
| `neviri vm resize-revert <id>` | `POST /servers/{id}/resize/revert` |

`pause`, `suspend`, `resume`, `unpause` actions exposed by the backend are **not** mapped to top-level CLI commands in Phase 1; they can be added later under `neviri vm <action>` if user demand emerges.

## What this ADR does NOT decide

- Pagination strategy for `neviri vm list` — backend has no pagination today; CLI renders the full list. Pagination contract is a Phase 2 backend story.
- Filtering — backend supports `?status=` and `?name=` query filters; CLI exposes these as `--status` / `--name` flags in Story 4.1.
- Whether `neviri image` and `neviri flavor` get top-level commands or live as `neviri vm flavors` / `neviri vm images`. Decided in Story 4.

## Reference

- Backend router: `neviri-backend/app/routers/compute.py`
- Backend tests: `neviri-backend/tests/{unit,integration}/...compute_*`
- CLI Story: 4 (vm commands)
