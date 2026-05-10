# neviri-cli

Official command-line interface for the [Neviri Cloud Platform](https://neviri.com).

> **Status:** Internal alpha (`0.1.0a1`). Phase 1 of the architecture proposal is complete: compute and networking workflows are usable end-to-end against a Neviri backend. **Not for external use.** No backwards-compatibility guarantees on commands, output schemas, or exit codes until 1.0.0.

## What works today

- Auth: `neviri auth login` (password OR API token), `whoami`, `logout`
- Profiles: `neviri config get/set/list/use-context`, multi-profile via `--profile`
- Compute: `neviri vm list/get/create/delete/start/stop/reboot/resize/console/flavors/images`
- Block storage: `neviri volume list/get/create/delete/attach/detach/snapshot...`
- Networking: `neviri network`, `neviri subnet`, `neviri floating-ip`
- Output: `--output {table,json,yaml}`, `--no-color`, deterministic JSON
- Documented exit codes (`0`/`1`/`2`/`3`/`4`/`5`)

## What's coming

See the [CHANGELOG](CHANGELOG.md) "Known limitations" section. Phase 2 adds
managed databases, object storage, load balancers, app/deploy commands, and
proper OpenAPI codegen. Phase 3 ships standalone binaries, Homebrew, and
self-update.

## Install

For the alpha:

```bash
pip install --index-url <private-index-url> "neviri-cli==0.1.0a1"
```

From source:

```bash
git clone https://github.com/ArcLogiQ/neviri-cli.git
cd neviri-cli
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Verify:

```bash
neviri --version
```

## Quick start

```bash
neviri config use-context staging
neviri config set api_url  https://stagingapi.neviri.com
neviri config set auth_url https://stagingauth.neviri.com
neviri auth login --email you@neviri.com
neviri vm list
```

Full walkthrough in [docs/getting-started.md](docs/getting-started.md).

## Development

```bash
pytest                      # tests + 90% coverage gate
ruff check .                # lint
ruff format .               # format
python -m mypy src          # strict type-check
```

CI (`.github/workflows/ci.yml`) runs all four on Linux/macOS/Windows × Python 3.11/3.12/3.13 on every PR.

## Architecture

The CLI is a **pure HTTP client** (architecture proposal §4.1) — no business
logic, no OpenStack SDK calls, no DB connections. Every action goes through
the backend's public REST API. See:

- [docs/decisions/0001-vm-surface.md](docs/decisions/0001-vm-surface.md) — `neviri vm` wraps `/api/v1/compute/servers/*`
- [docs/decisions/0002-phase-1-alpha-cut.md](docs/decisions/0002-phase-1-alpha-cut.md) — Phase 1 scope and deviations

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

## License

Apache 2.0 — see [LICENSE](LICENSE).
