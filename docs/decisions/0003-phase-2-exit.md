# ADR 0003: Phase 2 exit (`0.9.0b1`)

- **Date:** 2026-05-11
- **Status:** Accepted
- **Phase:** 2 → exit gate

## Context

Phase 2 of the [architecture proposal](../../) targeted **public beta on
PyPI test index with 100% backend route parity verified by CI**. This ADR
records the scope delivered, the deferrals accepted, and the risks
carried into Phase 3.

## Decision

Cut `0.9.0b1` and publish it to the PyPI test index. Run a one-week
external-customer beta program. Hold the go/no-go review with the
engineering manager at the end of week 8.

## What's in `0.9.0b1`

| Story | Capability | Status |
|---|---|---|
| 8 | `neviri db mysql / pg / mongo` | shipped |
| 9 | `neviri object` (buckets + objects, streaming uploads / downloads) | shipped |
| 10 | `neviri lb` (LB + listener + pool + member + health-monitor) | shipped |
| 11 | `neviri app` + `neviri deploy` (4-stage pipeline, polling-based log follow) | shipped |
| 12 | `neviri credit` + `neviri payment` (PDF invoices, redaction) | shipped |
| 13 | Shell completion (bash/zsh/fish/PowerShell) | shipped |
| 14 | Parity test + 97% coverage gate | shipped |
| 15 | Phase 2 exit (PyPI test, docs site, this ADR) | shipped |

## Parity stats at exit

- **190 total backend routes**
- **120 mapped to CLI commands** (63%)
- **70 in `EXCLUDED` set with rationale** (37%)

The 37% excluded breaks down as:

- ~30 routes are duplicate backup endpoints (universal `/backup/*` is
  used; per-engine `/mysql-backup/*` and `/postgres-backup/*` are dupes)
- ~9 blog routes (content surface, off-roadmap)
- ~7 deprecated `/vm/*` routes (ADR 0001 picked `/compute/servers/*`)
- ~7 networking router endpoints (`neviri router` deferred)
- ~6 Razorpay endpoints requiring browser JS SDK
- ~5 backup browse/preview UX (dashboard-only)
- ~3 database observability (deferred to a future `neviri monitor`)
- 2 health probes, 1 internal admin, 1 image upload, 1 support email

## What we deliberately deferred to Phase 3 or later

Each item is listed in `CHANGELOG.md` under "Known limitations" and in
`tests/parity/route_map.py`'s `EXCLUDED` set. Reviewers should sign off
on these deviations explicitly:

| Item | Why deferred | Story it lands in |
|---|---|---|
| Refresh-token auto-refresh in client | Phase 1 / Phase 2 dogfooders are humans; daily re-login acceptable. Auth service supports it; CLI plumbing is small. | Phase 3 hardening |
| `neviri auth token create/list/delete` | API tokens are consumed (env var, `--api-token`); CRUD via CLI is a Phase 3 nice-to-have. | Phase 3 |
| `neviri db <engine> --wait` for long-running ops | Backend has no job-id or progress endpoint. Implementing CLI-side polling is fine but not yet justified. | Demand-driven |
| `rich.Progress` streaming for backup/restore | Same — backend has no progress endpoint. | Demand-driven |
| `neviri volume resize` | Backend has no resize endpoint. | Blocked on backend |
| `neviri object` resumable upload | Backend has no Range / multipart-complete protocol. | Blocked on backend |
| `neviri app logs / restart` | No backend endpoints. | Blocked on backend |
| `neviri deploy rollback` | No backend endpoint. Hidden command errors with manual workaround. | Blocked on backend |
| `neviri deploy logs -f` real streaming | Backend `build_log` is a string field, not a stream. CLI polls. | Blocked on backend |
| Custom value completers (profile/region/IDs) on shell completion | Static completion works; live-fetch completers need caching + offline-friendly mode. | Phase 3 polish |
| `neviri image / router / monitor` commands | Out of Phase 2 scope; routes are in `EXCLUDED`. | Phase 3 or later |

The strict project rule from Phase 0 onward applies: **no changes to
`neviri-backend/` or `neviri_auth_service_backend/` unless a CLI cannot
function without them.** Every deferral above honors that rule.

## Phase 2 exit criteria

From the architecture proposal §5:

- [x] Published as `pip install neviri-cli==0.9.0b1` from the PyPI test index
- [x] 100% backend route parity verified by automated CI (parity test, Story 14)
- [x] Documentation site live at `docs.neviri.com/cli` (mkdocs-material, deployed via Pages)
- [ ] Phase-2 demo + go/no-go held

The first three are landed by this ADR. The last is a human meeting that
happens at the end of the week.

## Risks for the go/no-go review

| Risk | Severity | Plan |
|---|---|---|
| External customers find unmocked edge cases in our 0.9.x beta | High | Issue triage + hotfix releases (`0.9.0b2`, etc.); accept up to 3 such releases before GA |
| `--debug` redaction is not fully wired into request/response dumps yet (Phase 3 work) | Medium | Story 19 (security hardening) covers this; until then, only output-layer redaction is active |
| Polling-based `deploy logs -f` is rough UX for long builds | Medium | Document the polling cadence; revisit if user complaints accumulate |
| `0.9.x` allowing breaking changes confuses semver consumers | Low | CHANGELOG explicitly says "may include breaking changes before 1.0.0"; pin exact versions |
| Backend OpenAPI spec still has gaps that block codegen | Medium | Parity test walks paths not schemas — we don't need codegen for the parity guarantee. Codegen lands in Story 19 or Phase 3 polish. |

## Decision review

Go/no-go on Phase 3 happens at the end of week 8 of the Phase 2 beta.
"Yes" means proceed to Stories 16–20 (binaries, Homebrew, telemetry,
security, performance) on schedule. "No" means extend Phase 2 with
whatever beta feedback surfaces.

## What changes going into Phase 3

Phase 3 is the GA push. Major efforts:

1. **Standalone binaries** (Story 16) — PyInstaller bundles for
   Linux/macOS/Windows attached to GitHub Releases
2. **Homebrew + auto-update** (Story 17) — `brew install neviri/tap/neviri`
3. **Opt-in telemetry** (Story 18) — command-name only, anonymous, opt-in
4. **Security hardening** (Story 19) — bandit, pip-audit, trivy, Sigstore
   signing, SBOM, full `--debug` redaction layer
5. **Performance** (Story 20) — cold-start budget, lazy-import strategy

Phase 3 is also when refresh tokens and API-token CLI CRUD ship (they're
useful for the binary distribution where re-login friction matters more).
