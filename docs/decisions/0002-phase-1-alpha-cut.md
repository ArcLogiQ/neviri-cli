# ADR 0002: Phase 1 alpha cut (`0.1.0a1`)

- **Date:** 2026-05-10
- **Status:** Accepted
- **Phase:** 1 → exit gate

## Context

Phase 1 of the [architecture proposal](../../) targeted an internal alpha that
3 users (1 SRE + 2 backend devs) can drive end-to-end for compute and
networking workflows without using the web UI. This ADR records the scope
delivered and the explicit deviations from the original plan.

## Decision

Cut `0.1.0a1` and publish it to the private index. Run a one-week dogfood
against staging. Hold the go/no-go review with the engineering manager at
the end of week 4.

## What's in `0.1.0a1`

| Capability | Status |
|---|---|
| Repo scaffold + cross-OS CI | shipped (Story 1) |
| Auth + config (24h JWT, API token, multi-profile, keyring) | shipped (Story 3) |
| `neviri vm` (compute lifecycle + console URL) | shipped (Story 4) |
| `neviri volume` (block storage + snapshots) | shipped (Story 5) |
| `neviri network`, `subnet`, `floating-ip` | shipped (Story 5) |
| Output formatters (table/JSON/YAML/tree) | shipped (Story 6) |
| Typed exit codes 0-5 | shipped (Story 6) |
| Phase 1 E2E happy-path test | shipped (Story 5.4) |
| `release.yml` for tag-driven publish | shipped (Story 7.1) |
| Coverage ≥ 90% sustained | shipped (98%+) |

## What we deliberately deferred or removed

The original task list listed items we determined were not Phase-1-blocking.
Each is recorded here so reviewers can sign off on the deviation.

| Original AC | Decision | Rationale |
|---|---|---|
| Story 2: OpenAPI codegen pipeline + parity test | Deferred to Phase 2 | Backend has 75 of 192 endpoints without `response_model`. Codegen would produce mostly `Any` types or fail mypy --strict. Hand-written client modules are honest and small for the Phase 1 surface. We'll revisit when the backend OpenAPI spec is complete. |
| Story 3: transparent refresh-token handling | Deferred to Phase 2 | The auth service supports refresh tokens (we built that), but Phase 1 alpha users are 3 humans who can re-login daily. Refresh logic is best added under user feedback pressure, not speculatively. |
| Story 3: `neviri auth token create/list/delete` | Deferred to Phase 2 | API tokens are *consumed* in Phase 1 (env var, `--api-token`); CLI-side CRUD lands when external customers need it. |
| Story 4.5: console proxies VNC/SSH | Reduced to URL-print | Backend exposes only a noVNC URL (no serial / no SSH proxy). See [ADR 0001](0001-vm-surface.md). |
| Story 5: `neviri volume resize` | Removed | Backend doesn't expose `/volumes/{id}/resize`. Better to omit than ship a fake. |

We have a strict rule from this point on: **no changes to `neviri-backend/`
or `neviri_auth_service_backend/` unless the CLI literally cannot be built
without them.** The deviations above honour that rule.

## Phase-1 exit criteria

From the architecture proposal §5:

- [ ] Published as `pip install neviri-cli==0.1.0a1` from the private index
- [ ] 3 internal users (1 SRE + 2 backend devs) drive staging compute + network workflows without using the UI
- [ ] Combined unit + integration coverage ≥ 90% (currently **98.54%**)
- [ ] Demo recorded; go/no-go review held with engineering manager

The first and last items happen outside this repo: tag the release, point
the dogfooders at [getting-started.md](../getting-started.md), record the
demo, hold the meeting.

## Risks for the go/no-go review

| Risk | Severity | Plan |
|---|---|---|
| Backend OpenAPI spec is incomplete (75 endpoints lack `response_model`) | High for Phase 2 | Phase 2 starts with a backend cleanup story before Story 8 (db) lands. |
| 24h re-login is annoying for SRE workflows | Medium | If alpha feedback flags this, fast-track refresh-token wiring at start of Phase 2. The auth service is ready. |
| Coverage gate is 90%, not 97% | Low | Lift to 97% before Phase 2 GA, before adding the `db`/`object`/`lb` surfaces. |
| Backend-side response wrapper drifts wire format from spec | Low for CLI | CLI compensates in `client/base.py`. Phase 2 backend cleanup removes the wrapper. |

## Decision review

Go/no-go on Phase 2 happens at the end of week 4 of the alpha dogfood.
"Yes" means proceed to Story 8 (managed databases) on schedule. "No" means
extend Phase 1 with whatever fix the dogfood feedback surfaces.
