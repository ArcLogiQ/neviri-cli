# Changelog

All notable changes to `neviri-cli` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

_Nothing pending._

## [1.0.0] - 2026-05-13

Phase 3 exit: **General Availability**. Exit codes, output schemas, and
command names are stable from this point on. Breaking changes ship only in a
new major version.

### Added

- **Standalone binaries** (Story 16) — single-file PyInstaller bundles for
  Linux / macOS-x86_64 / macOS-arm64 / Windows-x86_64 built on every tag push
  and attached to the GitHub Release. No Python install required to run.
  Approximate sizes: ~20MB Windows, ~40-60MB Linux/macOS.
  - `[binary]` optional dependency group in `pyproject.toml` pulls in
    PyInstaller for local builds.
  - Smoke test on each built binary verifies `--version`, `--help`, and the
    completion-script branch all work without Python on `PATH`.
- **Homebrew tap + self-update** (Story 17) — `brew install
  ArcLogiQ/tap/neviri` and `neviri version --upgrade`.
  - GitHub Releases API query + version comparison handling
    `a < b < rc < final` ordering.
  - Cross-platform replace: POSIX uses `os.replace`; Windows uses a `.bat`
    helper that swaps the locked `.exe` after the current process exits.
  - Release workflow auto-generates the formula from rendered SHA256s and
    opens a PR on `ArcLogiQ/homebrew-tap` for stable releases only.
- **Opt-in telemetry** (Story 18) — single-file audit surface at
  `src/neviri_cli/utils/telemetry.py`.
  - Default OFF. Prompts on the first interactive non-quiet command, defaults
    to **No**.
  - Exact payload: `command`, `cli_version`, `os`, `install_id` (locally
    generated UUIDv4). Nothing else.
  - Always disabled when `NEVIRI_TELEMETRY=disable`, `CI=true`, or stdin/stderr
    isn't a TTY.
  - Fire-and-forget daemon thread with 2-second timeout; all errors swallowed
    so telemetry can never crash or block the CLI.
  - `neviri config set telemetry false` flips it instantly.
  - Documented in `docs/privacy.md`.
- **Security hardening** (Story 19) — full security pipeline.
  - **bandit** static analysis on `src/`, with `[tool.bandit]` config and
    line-level `# nosec` annotations for the 7 false positives (env var
    names, JSON field names, intentional broad-except for telemetry).
  - **pip-audit** dependency vulnerability scanning on every push + PR +
    weekly cron. Audits the declared runtime deps from `pyproject.toml`.
  - **trivy** filesystem scan with SARIF upload to the GitHub Security tab.
  - **CycloneDX SBOM** generated per release and attached as an artifact
    (`neviri-cli-sbom.json`).
  - **Sigstore cosign keyless signing** for every release artifact via
    GitHub Actions OIDC. Each binary ships with matching `.sig` and `.crt`
    files; verify via `cosign verify-blob ...`.
  - `--debug` request/response logging now redacts auth headers
    (`Authorization`, `Cookie`, `Set-Cookie`, `X-Api-Key`, …), passwords,
    and qualified token fields (`access_token`, `refresh_token`, `id_token`)
    via the existing redaction layer. Safe to share `neviri --debug` output
    in bug reports.
- **Cold-start performance pass** (Story 20) — lazy subcommand loading.
  - 14 subcommand groups + 2 leaf commands resolve on demand via a custom
    `_LazyTyperGroup` subclass — Click only imports the module of the
    subcommand the user actually invoked.
  - `output/__init__.py` defers `_table` / `_yaml` / `_json` imports inside
    `render()`, so `rich` and `PyYAML` no longer load on `import
    neviri_cli.output`.
  - Result: `neviri --version` cold start ~1000ms → ~280ms in dev mode
    (3.5x improvement).
  - Determinism contract pinned by `tests/test_startup_perf.py`: 13 heavy
    modules (httpx, keyring, rich.progress, every heavy `commands/*` module)
    MUST NOT appear in `sys.modules` after `import neviri_cli.app` or after
    `app(['--version'])`.
  - CI runs `hyperfine` with 10 warmups + 50 runs and asserts mean < 500ms.

### Changed

- Development status classifier promoted from `3 - Alpha` →
  `5 - Production/Stable`.
- Install path simplified: `pip install neviri-cli` from public PyPI; the
  Phase 2 test.pypi.org URL is no longer needed.

## [0.9.0b1] - 2026-05-11

Phase 2 exit: public beta. 100% backend route parity verified by CI. **Not for
production use** — exit codes, output schemas, and command names are still
subject to change until 1.0.0. The 0.9.x series is a beta line that may include
breaking changes before GA.

### Added

- **`neviri db`** — managed database lifecycle for MongoDB / MySQL / PostgreSQL
  - `list / get / status / flavors` (read)
  - `create` with `--password-stdin` for safe DB-admin-password input
  - `delete / scale` with confirmation prompts
  - `backup / backups / backup-delete` (universal `/backup/*` endpoint, dispatches by engine)
  - `restore / restore-status`
- **`neviri object`** — S3-compatible buckets + objects
  - `bucket list / get / create / delete` with `-m KEY=VAL` metadata
  - `list / put / get / delete` with byte-level progress bars via `rich.Progress`
  - Upload streams off disk via httpx multipart; download streams via httpx `iter_bytes`
- **`neviri lb`** — load balancers
  - LB CRUD + `update` with `--admin-up/--admin-down`
  - `listener / pool / health-monitor` subgroups
  - Pool members: `member-list / member-add / member-remove`
  - Protocol and algorithm strings auto-upcased so `--protocol http` works
- **`neviri app`** — application deployment
  - App CRUD + `upload` (ZIP with progress bar)
  - `deployments` lists per-app deployments
  - `env-list / env-set KEY=VAL / env-unset` for environment variables
- **`neviri deploy`** — deployment stages
  - Per-stage triggers: `build / deploy / service / ingress`
  - `run` chains all 4 stages
  - `get / manifests` for status + K8s YAML
  - `logs` with `--follow` (polling) and `--tail N`
- **`neviri credit`** — credit balance, history, status, and Razorpay top-up
  - `top-up --amount N --yes` creates a Razorpay order; user completes in browser
- **`neviri payment`** — payment history, summaries, PDF downloads (receipt / invoice / monthly-invoice)
  - `method status / list / delete` for saved payment method management
  - `method add` errors with a pointer to the web UI (Razorpay JS SDK is browser-only)
- **`neviri completion`** — shell completion script generator
  - Supports `bash / zsh / fish / powershell / pwsh`
  - Install snippets documented in `docs/getting-started.md`
- **Redaction layer** — sensitive fields masked in CLI output
  - Always redacted: `password`, `razorpay_payment_id`, `razorpay_signature`, DB admin passwords, verification tokens
  - Preserved: card brand / last4 / expiry, `razorpay_order_id`, `razorpay_key_id`, email, name
- **Backend parity test** — CI-enforced guarantee
  - 190 backend routes; every one is either mapped to a CLI command (63%) or in `EXCLUDED` with rationale (37%)
  - Drift detection: stale `ROUTE_MAP` / `EXCLUDED` entries fail CI
  - Refresh via `python scripts/refresh-openapi-snapshot.py`
- **Coverage gate raised** from 90% to **97%** (current: 98.73%)
- **Docs site** at `docs.neviri.com/cli` built from `mkdocs-material`

### Changed

- Default coverage gate in `pyproject.toml`: `--cov-fail-under=97`
- Test count: **576 tests** (was 272 at Phase 1 exit)

### Decisions

- [ADR 0003](docs/decisions/0003-phase-2-exit.md): Phase 2 exit scope and deviations from original task list

### Known limitations

These were either deferred by design (per ADR 0003) or are blocked on backend
work we explicitly agreed not to do:

- **Refresh-token auto-refresh** — auth service supports it (built in Phase 0), but CLI uses simple 24h JWT. Add when dogfooders demand it.
- **`neviri auth token create/list/delete`** — API tokens are *consumed* (env var, `--api-token`) but not yet CRUD'd via CLI.
- **`neviri db <engine> --wait` / progress streaming for backup/restore** — backend has no job-id or progress endpoint.
- **`neviri db <engine> resize` validation against source plan** — backend handles plan validation; CLI just surfaces the response.
- **`neviri volume resize`** — no backend endpoint.
- **`neviri object` resumable upload** — backend has no Range / multipart-complete protocol.
- **`neviri app logs / restart`** — no backend endpoints.
- **`neviri deploy rollback`** — no backend endpoint; the hidden command errors with manual-rollback instructions.
- **`neviri deploy logs -f` real streaming** — backend has no streaming endpoint; the CLI polls `build_log` every `--interval` seconds.
- **Custom value completers** (profile/region/IDs) on shell completion — static completion works; live-fetch completers deferred.
- **Image upload, support, blog, network routers** — out of CLI Phase 2 scope (rationale in `tests/parity/route_map.py`).

## [0.1.0a1] - 2026-05-10

First internal alpha. Compute and networking workflows are usable end-to-end
against a Neviri backend. **Not for external use.** No backwards-compatibility
guarantees on commands, output schemas, or exit codes until 1.0.0.

### Added

- **Authentication & profiles**
  - `neviri auth login` (email + password OR `--api-token`, also via stdin and `NEVIRI_API_TOKEN`)
  - `neviri auth logout`, `neviri auth whoami`, `neviri auth token`
  - Token storage via OS keyring with `NEVIRI_TOKEN_STORE=file` fallback for headless CI
  - Multi-profile config at `~/.neviri/config.toml` (overridable via `NEVIRI_CONFIG`)
  - `neviri config get/set/list/use-context`
- **Compute** (wraps `/api/v1/compute/servers/*` per ADR 0001)
  - `neviri vm list / get / create / delete / start / stop / reboot / resize / resize-confirm / resize-revert / console / flavors / images`
  - Console prints (or `--launch`-es) the noVNC URL
- **Block storage**
  - `neviri volume list / get / create / delete / attach / detach`
  - `neviri volume snapshot / snapshots / snapshot-get / snapshot-delete`
- **Networking**
  - `neviri network list / get / create / delete`
  - `neviri subnet list / get / create / delete`
  - `neviri floating-ip list / get / allocate / release / associate / disassociate`
- **Output**
  - Global `--output {table,json,yaml}` (default `table`)
  - `--no-color` for ANSI-free output
  - Deterministic, sorted-key JSON; block-style YAML
- **Error handling**
  - Typed exceptions and documented exit codes (`0` success, `1` generic, `2` user, `3` auth, `4` network, `5` server)
- **Tooling**
  - CI on Linux/macOS/Windows × Python 3.11/3.12/3.13
  - Coverage gate at 90% (raises to 97% before Phase 2 GA)

### Decisions

- [ADR 0001](docs/decisions/0001-vm-surface.md): `neviri vm` wraps `/api/v1/compute/servers/*`
- [ADR 0002](docs/decisions/0002-phase-1-alpha-cut.md): Phase 1 alpha scope and what's intentionally absent

### Known limitations

- No transparent JWT refresh — tokens expire after 24h; re-run `neviri auth login`. Refresh-token integration is Phase 2.
- No `neviri auth token create / list / delete` for managing API tokens through the CLI. The auth service supports the underlying endpoints; CLI commands ship in Phase 2.
- No `neviri volume resize` — backend doesn't expose a resize endpoint yet.
- No pagination on list commands — backend lists are unpaginated; full collections are returned. Pagination contract is a Phase 2 backend story.
- No managed databases (`neviri db ...`), object storage (`neviri object`), load balancers (`neviri lb`), apps (`neviri app`), or deployments (`neviri deploy`) — Phase 2.
- No standalone binaries — Phase 3 ships PyInstaller bundles, Homebrew tap, and self-update.
- No telemetry — opt-in collection lands in Phase 3.

[1.0.0]: https://github.com/ArcLogiQ/neviri-cli/releases/tag/v1.0.0
[0.9.0b1]: https://github.com/ArcLogiQ/neviri-cli/releases/tag/v0.9.0b1
[0.1.0a1]: https://github.com/ArcLogiQ/neviri-cli/releases/tag/v0.1.0a1
