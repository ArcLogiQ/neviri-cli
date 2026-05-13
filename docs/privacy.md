# Privacy

This page describes exactly what data `neviri` collects, when, and how to
turn it off. It mirrors the implementation in
[`src/neviri_cli/utils/telemetry.py`](https://github.com/ArcLogiQ/neviri-cli/blob/master/src/neviri_cli/utils/telemetry.py)
— if you see something here that contradicts the source, the source wins
and the docs are out of date. Please open an issue.

## TL;DR

- **Telemetry is OFF by default.** Nothing is sent until you explicitly
  opt in.
- **No personal data, no command arguments, no IDs from your account.**
  We collect command name, CLI version, OS, and a locally-generated UUID.
- **One flag to disable forever:** `neviri config set telemetry false`,
  or set `NEVIRI_TELEMETRY=disable` in your shell environment.

## What we collect

When telemetry is enabled, every CLI invocation triggers a single POST
with this exact payload:

| Field | Example | Description |
|---|---|---|
| `command` | `"vm"` | The top-level subcommand (one of: `auth`, `config`, `vm`, `volume`, `network`, `subnet`, `floating-ip`, `db`, `object`, `lb`, `app`, `deploy`, `credit`, `payment`, `completion`, `version`). Never arguments, flag values, IDs, or any user-supplied string. |
| `cli_version` | `"1.0.0"` | The release of `neviri` you're running. |
| `os` | `"linux"` / `"darwin"` / `"windows"` | The platform name. No version, no kernel detail. |
| `install_id` | `"7b2f5e1c-3a4d-..."` | A UUIDv4 generated locally when you opted in. It is NOT derived from your account, email, hostname, MAC address, or anything else identifying. It lives in `~/.neviri/config.toml` and you can rotate it by deleting that file. |

## What we never collect

The implementation is short and easy to audit — see
[`make_payload`](https://github.com/ArcLogiQ/neviri-cli/blob/master/src/neviri_cli/utils/telemetry.py)
— but to be explicit, the CLI **never** sends:

- Command arguments or flag values
- Resource IDs, names, IP addresses
- File paths, project names, organization names
- Your email address, name, account ID
- Your auth token, API token, or anything else from your keyring
- Your hostname, MAC address, or other machine identifiers
- Timestamps beyond what the HTTP endpoint already sees from your packet

## When telemetry is always disabled

Even after you opt in, telemetry is silently skipped when any of these
conditions hold:

1. **CI environment**: `CI=true` is set (most CI providers set this).
2. **Non-interactive shell**: stdin or stderr is not a TTY (piped output,
   scheduled job, daemon context).
3. **Explicit env disable**: `NEVIRI_TELEMETRY=disable` (or `off`,
   `false`, `0`, `no`).
4. **Endpoint disabled**: `NEVIRI_TELEMETRY_ENDPOINT=""` (empty string)
   opts out of sending while keeping the config-level setting at `true`
   — useful for offline / air-gapped users who want to keep their answer
   recorded.
5. **Quiet commands at first run**: the first-run prompt is suppressed
   for `version`, `completion`, `config`, and `auth` commands so
   discovery and setup flows aren't interrupted.

## How to opt out

You can opt out in any of three ways. The choice is persisted in
`~/.neviri/config.toml`.

### Permanently, via the CLI

```bash
neviri config set telemetry false
```

This writes `telemetry = false` to your config file. The CLI will never
send a telemetry event again, even if you re-prompt with
`neviri config set telemetry true`.

### Per-shell, via env var

```bash
# bash / zsh
export NEVIRI_TELEMETRY=disable

# PowerShell
$env:NEVIRI_TELEMETRY = "disable"
```

The env var takes precedence over config — set this in your `.bashrc` /
`.zshrc` / `$PROFILE` to disable forever without touching config.

### One-off, via env var

```bash
NEVIRI_TELEMETRY=disable neviri vm list
```

Same as the env-var path, scoped to one invocation.

## How to opt in

By default, the first interactive invocation of a non-trivial command
(anything besides `version`, `completion`, `config`, `auth`) prompts:

```
Help improve neviri by sending anonymous usage stats? We collect: command
name, version, OS, an anonymous install ID — and nothing else. See
https://docs.neviri.com/cli/privacy for details.
Send anonymous usage stats? [y/N]:
```

If you say no (the default), the choice is persisted — you won't be
prompted again. If you say yes, an install ID is generated locally and
written to `~/.neviri/config.toml`.

You can also opt in non-interactively:

```bash
neviri config set telemetry true
```

## Where the data goes

When telemetry is enabled, payloads are POSTed to
`https://telemetry.neviri.com/cli/v1/events` (or whatever you set
`NEVIRI_TELEMETRY_ENDPOINT` to). Sending happens on a background daemon
thread with a 2-second timeout. If the endpoint is unreachable, the
event is dropped silently — we never retry, queue, or batch.

The endpoint stores aggregated counts, not individual events tied to
install IDs. Install IDs are used only to deduplicate "active users" and
are rotated whenever a user reinstalls.

## Auditing the code

Total telemetry surface area in the codebase:

- [`src/neviri_cli/utils/telemetry.py`](https://github.com/ArcLogiQ/neviri-cli/blob/master/src/neviri_cli/utils/telemetry.py)
  — the entire telemetry implementation (~150 lines, one file)
- [`tests/test_telemetry.py`](https://github.com/ArcLogiQ/neviri-cli/blob/master/tests/test_telemetry.py)
  — pins the contract: opt-in default OFF, exact payload fields, non-TTY skip
- Two call sites:
  - `src/neviri_cli/app.py` — `record_command()` in the Typer root callback
  - `src/neviri_cli/commands/config.py` — handles `telemetry` and
    `install_id` keys for `neviri config get/set/list`

If you'd like to see exactly what's sent on your system, run with the
endpoint set to a local capture tool:

```bash
# Terminal 1
nc -l -p 9000

# Terminal 2
NEVIRI_TELEMETRY_ENDPOINT=http://localhost:9000 \
  neviri config set telemetry true
neviri vm list
```

The captured POST body is the entire payload — feel free to copy it into
an issue if you spot anything we shouldn't be sending.

## Debug logging is redacted

`neviri --debug <command>` prints every HTTP request and response to
stderr — useful when filing a bug. Before printing, the CLI passes
headers and bodies through
[`redact()`](https://github.com/ArcLogiQ/neviri-cli/blob/master/src/neviri_cli/utils/redact.py),
which replaces sensitive field values with `***`. Specifically:

- `Authorization`, `Proxy-Authorization`, `Cookie`, `Set-Cookie`,
  `X-Api-Key`, `X-Auth-Token`, `X-Access-Token` headers
- `password`, `current_password`, `new_password`, `old_password`
- `access_token`, `refresh_token`, `id_token`
- Razorpay payment_id / signature
- Database user passwords (`mysql_pass`, `postgres_pass`, `mongo_pass`)
- Card numbers, verification tokens, reset password tokens

Matching is case-insensitive and ignores underscores, hyphens, and
spaces — so `Authorization`, `authorization`, and `AUTHORIZATION` all
match. The bare `token` field is NOT redacted (so `neviri auth token`
keeps working for scripting); only the qualified `access_token` /
`refresh_token` / `id_token` forms are masked.

You can safely paste `neviri --debug ...` output into a GitHub issue.

## Release artifact integrity

Every binary attached to a GitHub Release is signed with
[Sigstore cosign](https://docs.sigstore.dev/) using keyless OIDC
signing — the signer identity is the GitHub Actions workflow that built
it, not a long-lived key checked into the repo. Each artifact has a
matching `<artifact>.sig` (signature) and `<artifact>.crt` (certificate)
file. Verify with:

```bash
cosign verify-blob \
  --certificate neviri-linux-x86_64.crt \
  --signature   neviri-linux-x86_64.sig \
  --certificate-identity-regexp "https://github.com/ArcLogiQ/neviri-cli" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  neviri-linux-x86_64
```

Each release also ships a CycloneDX SBOM (`neviri-cli-sbom.json`)
listing every transitive dependency in the wheel.

## Changes to this page

Material changes to telemetry (new fields, changed endpoint, removed
opt-out paths) ship with a major version bump and are called out at the
top of `CHANGELOG.md`. We do not silently expand the payload between
patch versions.
