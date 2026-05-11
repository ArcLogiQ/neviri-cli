# neviri-cli

Official command-line interface for the [Neviri Cloud Platform](https://neviri.com).

> **Status:** Public beta (`0.9.0b1`). Phase 2 of the architecture proposal is complete — 100% backend route parity verified by CI. **Not for production use.** Exit codes, output schemas, and command names are still subject to change until 1.0.0.

## What it does

| Surface | Commands |
|---|---|
| Auth & profiles | `neviri auth login/logout/whoami/token`, `neviri config get/set/list/use-context` |
| Compute | `neviri vm list/get/create/delete/start/stop/reboot/resize/console/flavors/images` |
| Block storage | `neviri volume list/get/create/delete/attach/detach/snapshot...` |
| Networking | `neviri network`, `neviri subnet`, `neviri floating-ip` |
| Load balancers | `neviri lb`, `neviri lb listener / pool / health-monitor` |
| Databases | `neviri db mysql / pg / mongo` (CRUD + backup + restore + scale) |
| Object storage | `neviri object bucket ...`, `neviri object put/get/list/delete` |
| Apps & deploys | `neviri app upload/env-*`, `neviri deploy run/build/deploy/service/ingress/logs` |
| Billing | `neviri credit balance/history/top-up`, `neviri payment list/receipt/invoice` |
| Shell completion | `neviri completion bash/zsh/fish/powershell` |

Output: `--output {table,json,yaml}`, `--no-color`, deterministic JSON.
Exit codes: 0 success, 1 generic, 2 user error, 3 auth, 4 network, 5 server.

## Install

```bash
pip install --index-url https://test.pypi.org/simple/ "neviri-cli==0.9.0b1"
```

Or from source:

```bash
git clone https://github.com/ArcLogiQ/neviri-cli.git
cd neviri-cli
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Quick start

```bash
neviri config use-context staging
neviri config set api_url  https://stagingapi.neviri.com
neviri config set auth_url https://stagingauth.neviri.com
neviri auth login --email you@neviri.com
neviri vm list
neviri db mysql list
neviri object bucket list
```

Full walkthrough in [docs/getting-started.md](docs/getting-started.md).

## Backend route parity

The CLI carries a hard guarantee — every backend endpoint is either wrapped
by a `neviri` command or explicitly excluded with a one-line rationale. The
parity test in [`tests/parity/`](tests/parity/) walks the backend's
OpenAPI spec on every CI run and fails if drift appears.

To refresh after the backend adds new endpoints:

```bash
python scripts/refresh-openapi-snapshot.py
```

Current stats: **190 backend routes, 120 mapped (63%), 70 excluded (37%)**.

## Development

```bash
pytest                        # tests + 97% coverage gate
ruff check .                  # lint
ruff format .                 # format
python -m mypy src            # strict type-check
mkdocs serve                  # docs site at http://127.0.0.1:8000 (needs `pip install -e ".[docs]"`)
```

CI (`.github/workflows/ci.yml`) runs lint + type-check + tests on Linux/macOS/Windows × Python 3.11/3.12/3.13.

## Architecture

The CLI is a **pure HTTP client** — no business logic, no OpenStack SDK
calls, no DB connections. Every action goes through the backend's public
REST API.

- [ADR 0001](docs/decisions/0001-vm-surface.md): `neviri vm` wraps `/api/v1/compute/servers/*`
- [ADR 0002](docs/decisions/0002-phase-1-alpha-cut.md): Phase 1 alpha scope and deviations
- [ADR 0003](docs/decisions/0003-phase-2-exit.md): Phase 2 exit scope, deferrals, and risks

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR. The parity test
will fail if you add a backend endpoint without wiring up the CLI side (or
adding the route to `EXCLUDED` with rationale).

## License

Apache 2.0 — see [LICENSE](LICENSE).
