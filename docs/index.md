# neviri-cli

Official command-line interface for the [Neviri Cloud Platform](https://neviri.com).

!!! success "Status: 1.0.0 (stable)"
    Exit codes, output schemas, and command names are stable from 1.0.0
    onward. Breaking changes will only ship in major versions per semver.
    See the [CHANGELOG](changelog.md) for what landed in each release.

## What it does

`neviri` is the canonical CLI / SDK surface for Neviri. Anything you can do
in the dashboard, you can do with `neviri`:

- **Compute** — provision VMs, manage their power state, resize, console URLs
- **Block storage** — volumes, attach/detach, snapshots
- **Networking** — networks, subnets, floating IPs
- **Load balancers** — LBs, listeners, pools, members, health monitors
- **Managed databases** — MongoDB, MySQL, PostgreSQL (with backup / restore)
- **Object storage** — S3-compatible buckets and objects, with streaming uploads
- **Applications** — upload ZIPs, drive the 4-stage deployment pipeline
- **Billing** — credit balance, top-ups, payment history, monthly invoices
- **Shell completion** — bash / zsh / fish / PowerShell

## 30-second start

```bash
pip install neviri-cli
neviri config set api_url https://api.neviri.com
neviri config set auth_url https://iam.neviri.com
neviri auth login --email you@example.com
neviri vm list
```

Full walkthrough: [Getting started](getting-started.md).

## Architecture in one sentence

The CLI is a **pure HTTP client** — no business logic, no OpenStack SDK
calls, no direct DB connections. Every action goes through the backend's
public REST API. See [ADR 0001](decisions/0001-vm-surface.md) and
[ADR 0003](decisions/0003-phase-2-exit.md) for the design decisions and
scope boundaries.

## Backend route parity

`neviri-cli` ships with a CI-enforced parity test that walks the backend's
OpenAPI spec and checks every `(method, path)` tuple has either:

- a corresponding CLI command, or
- an entry in `tests/parity/route_map.py`'s `EXCLUDED` set with a
  one-line rationale (deprecated route, browser-only flow, etc.)

Backend ships a new endpoint → CLI's CI fails until someone wires it up or
explicitly excludes it. This guarantee is part of the project's contract.

## Where to go next

- **[Getting started](getting-started.md)** — install, configure, demo workflow
- **[Decisions](decisions/0001-vm-surface.md)** — design ADRs
- **[Changelog](changelog.md)** — release notes
- **[GitHub](https://github.com/ArcLogiQ/neviri-cli)** — source code, issues
