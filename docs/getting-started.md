# Getting started with `neviri-cli`

This guide is the alpha dogfood walkthrough for Phase 1. It mirrors the demo
script run during the go/no-go review.

## 1. Install

For the `0.1.0a1` internal alpha you install from the private index:

```bash
pip install --index-url <private-index-url> "neviri-cli==0.1.0a1"
```

Or from a clone of the source repo:

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
# neviri 0.1.0a1
```

## 2. Configure your environment

Pick a profile name and point it at your backend + auth service:

```bash
neviri config use-context staging
neviri config set api_url  https://stagingapi.neviri.com
neviri config set auth_url https://stagingauth.neviri.com
neviri config list
```

`~/.neviri/config.toml` is now populated. Tokens are NEVER written there —
they go to the OS keyring (or `~/.neviri/credentials.json` when
`NEVIRI_TOKEN_STORE=file` is set, e.g. on headless CI).

## 3. Authenticate

Two paths.

**Password login** (issues a 24h JWT — re-login on expiry):

```bash
neviri auth login --email you@neviri.com
# Password: ********
neviri auth whoami
```

**API token** (recommended for scripts and CI):

```bash
echo "$NEVIRI_API_TOKEN" | neviri auth login --api-token -
# or
neviri auth login --api-token nvr_xxxxxxxxxxxxxxxxxxxxxxxx
```

Or skip storage entirely by setting the env var per-invocation:

```bash
NEVIRI_API_TOKEN=nvr_xxx neviri vm list
```

## 4. The Phase 1 demo workflow

Provision a VM end-to-end without touching the dashboard. Replace the
placeholder IDs (`ext-net-id`, `m1.small`, `ubuntu-22.04`, `port-id`) with
real values from your tenant. `neviri vm flavors` and `neviri vm images`
will list valid IDs.

```bash
# 1. List what's available
neviri vm flavors
neviri vm images
neviri network list

# 2. Create the network and subnet
neviri network create demo-net
neviri subnet create demo-sub --network <network-id> --cidr 10.0.0.0/24

# 3. Boot a VM on the network
neviri vm create demo-01 \
    --flavor <flavor-id> \
    --image  <image-id> \
    --network <network-id>

# 4. Attach a 50 GB data volume
neviri volume create demo-data --size 50
neviri volume attach <volume-id> --server <server-id> --device /dev/vdb

# 5. Allocate a floating IP and associate it with the server's port
neviri floating-ip allocate --floating-network <ext-network-id>
neviri floating-ip associate <fip-id> --port <port-id>

# 6. Open the noVNC console
neviri vm console <server-id> --launch
```

## 5. Output for scripts

Default output is a human-readable table. For pipelines:

```bash
neviri vm list --output json | jq '.[] | select(.status == "ACTIVE") | .id'
neviri vm list --output yaml
```

`--output json` is treated as a stable contract — breaking changes to the
JSON schema require a major version bump.

## 6. Cleanup

```bash
neviri floating-ip disassociate <fip-id>
neviri floating-ip release      <fip-id> --yes
neviri volume detach <volume-id> --server <server-id>
neviri volume delete <volume-id> --yes
neviri vm     delete <server-id> --yes
neviri subnet delete <subnet-id> --yes
neviri network delete <network-id> --yes
```

## 7. Logout

```bash
neviri auth logout
```

## Exit codes

Documented contract — scripts can rely on these:

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | generic error |
| 2 | user error (bad input, validation, missing flag) |
| 3 | auth error (401/403, no token, expired) |
| 4 | network error (connection refused, DNS, TLS, timeout) |
| 5 | server error (backend 5xx) |

## Debugging a failure

```bash
neviri --debug vm get <server-id>
```

The `--debug` flag (Phase 1: prints stack traces) gets richer in later
phases — Phase 3 adds full request/response dumps with auth/secret redaction.

## Reporting alpha feedback

Open an issue at <https://github.com/ArcLogiQ/neviri-cli/issues> using the
"Bug report" or "Feature request" templates. Include the output of
`neviri --version` and the failing command.
