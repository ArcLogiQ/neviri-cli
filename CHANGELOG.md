# Changelog

All notable changes to `neviri-cli` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0a1]: https://github.com/ArcLogiQ/neviri-cli/releases/tag/v0.1.0a1
