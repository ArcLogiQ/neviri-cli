# IAM profiles and catalog status

IAM is explicitly selected per profile. Existing profiles default to `legacy` and
keep their existing login, environment-variable priority, keyring namespace and
configuration fields. IAM commands never copy or delete legacy credentials.

## Configure a separate profile

```console
neviri --profile team-iam iam configure --iam-url https://iam.neviri.com --api-url https://api.neviri.com
```

For a local stack, HTTP is accepted only on loopback origins such as
`http://localhost:8011` and `http://localhost:8000`. Remote IAM and API origins must
use HTTPS. Paths, embedded credentials, query strings and fragments are rejected.

This creates an explicit `auth_mode = "iam"` profile with nonsecret endpoint and
session options. No credential is written to `config.toml`, and the default profile
does not change. Continue passing `--profile team-iam`, or explicitly select it with
`neviri config use-context team-iam`.

## Sign in

Access-key login prompts for its secret without placing it in command arguments:

```console
neviri --profile team-iam iam login --access-key-id NVIAEXAMPLE
```

Use `--secret-stdin` to read one line from stdin in a controlled script. The public
key ID and secret can also come from `NEVIRI_IAM_ACCESS_KEY_ID` and
`NEVIRI_IAM_SECRET_ACCESS_KEY`; both are required together. Never put a real secret
in a checked-in script or terminal example.

Console login uses a separate IAM username and password:

```console
neviri --profile team-iam iam login --account-id 123 --username developer --mfa
```

The password and, when `--mfa` is given, authenticator code are hidden prompts.
Omit `--mfa` only when the user does not require an authenticator. These credentials
are sent only to the IAM service. Login returns a short-lived session and the CLI
checks its identity using the authenticated `/v1/session` endpoint. The CLI does
not infer authority from unsigned JWT contents or fabricate a legacy numeric user ID.

## Assume a role

```console
neviri --profile team-iam iam assume-role nvr:iam::123:role/ReadOnly --session-name release-check --duration 900
```

Optional flags are `--external-id` and `--session-policy policy.json`. A supplied
JSON policy can only narrow the role session. IAM independently checks caller
permissions, role trust, account scope, MFA and duration. Role chaining is not
enabled in this release.

The profile remembers nonsecret role/session options. With a stored access key,
the CLI exchanges a fresh user session and assumes the role when its cached role
session nears expiry. Console-only sessions cannot be renewed after their source
session expires: sign in again. Re-running `iam configure` clears the remembered
role options; it does not silently repurpose a cached role session as a user session.

## Read identity and catalog status

```console
neviri --profile team-iam iam whoami
neviri --profile team-iam --output json catalog release-status 123
neviri --profile team-iam iam logout
```

`whoami` reads the current IAM session from the server and prints only allow-listed
identity metadata. It never prints access-token or secret fields, even if an
unexpected upstream response includes them. Catalog status calls
`GET /api/v1/catalog/releases/{release_id}/status`. The business backend verifies
the resource's stored account/region and requires an authoritative IAM allow before
reading status. Both account and backend enforcement settings must be enabled for
that operation. Other resource commands may remain unavailable to IAM until their
backend integration is implemented.

The same `catalog release-status` command works with an existing legacy profile;
its original credential resolution path remains unchanged.

## Credential isolation and refresh

IAM secrets use keyring service `neviri-cli-iam`, independent of `neviri-cli`.
`NEVIRI_IAM_TOKEN_STORE=file` selects the optional plaintext headless fallback at
`~/.neviri/iam-credentials.json` or `NEVIRI_IAM_CREDENTIALS`. Existing
`NEVIRI_TOKEN_STORE=file` also selects a file backend for IAM, but still uses that
separate IAM file. POSIX permissions use the existing user-only file-store behavior;
Windows file protection depends on the account's filesystem permissions.

IAM refuses a file path that resolves or aliases to the legacy credentials file or
the config file. Secrets and session tokens do not enter `config.toml`. Credentials
are bound to the configured IAM and business API origins. Changing either origin
requires a fresh login before stored credentials can be reused; an old access-key
secret is never automatically sent to a different issuer.

Cached sessions are used until 30 seconds before expiry. Stored access-key profiles
then obtain a fresh session; role/profile-policy changes also invalidate the cache.
An authorization denial does not trigger a fallback to legacy credentials.

Environment overrides are separate:

- `NEVIRI_IAM_SESSION_TOKEN` takes precedence for IAM profiles and is introspected.
- Otherwise an IAM key pair from the environment is exchanged for a temporary token.
- Otherwise only the selected profile's IAM credential store is consulted.
- `NEVIRI_API_TOKEN` is never used by an IAM profile; legacy profiles keep their
  existing behavior and ignore the new IAM variables.

Environment credentials are never persisted by automatic request resolution. An
environment user session in a role-configured profile is assumed into that role
with its configured narrowing policy. An environment role session must match the
configured role; when a session policy is configured, an already-assumed override
is rejected because introspection cannot prove its policy binding.

Logout revokes and clears the selected profile's **stored** IAM session and keys.
It does not unset or revoke environment credentials supplied by the caller. During
an outage local cleanup still runs and reports that server revocation was not
confirmed. A failed or locked keyring is reported instead of claiming credentials
were cleared. Debug traces redact passwords, MFA codes, secrets, tokens, auth
headers and validation payloads that could echo submitted input.

## Stop an explicitly adopted VM

```console
neviri --profile team-iam --output json vm stop 00000000-0000-4000-8000-000000000123 --idempotency-key release-stop-20261106-001
neviri --profile team-iam --output json iam operation-status 00000000-0000-4000-8000-000000000456
```

IAM STOP requires a canonical lowercase server UUID and an explicit 8–128
character ASCII key matching `[A-Za-z0-9][A-Za-z0-9._:-]*`. Keep that same key
for the same logical request, including after a timeout or uncertain result.
The CLI never retries the mutation automatically or generates a replacement key.
The fixed request is `POST /api/v1/compute/servers/{id}/action` with only
`{"action":"stop"}` and the `Idempotency-Key` header. No owner/account/region
headers are accepted. The STOP request has a 65-second timeout; debug traces
redact the caller's key.

Only explicitly adopted existing servers are eligible. The backend independently
verifies current IAM authorization, approved execution scope, stored resource
ownership and retention rules. The ledger owner and boot-volume billing remain
unchanged. Acceptance does not mean the VM is already stopped: compute billing
closes only after scoped readback confirms `SHUTOFF`.

Errors expose only a validated operation UUID and optional known operation state
when available. Use `iam operation-status` to recover after an uncertain response.
Replaying the same key returns the stored operation and never dispatches STOP
again. A 409 can represent a pending operation, conflict or definite failure;
a 503 can represent an unknown outcome. Preserve the key and inspect the durable
state rather than issuing a replacement request with a new key.

STOP permission is `compute-virtual-machines:stop-server` on
`nvr:compute:<stored-region>:<account>:server_id/<server-UUID>`. Operation lookup
requires the separate `compute-virtual-machines:get-server-operation` permission
on `nvr:compute:<stored-region>:<account>:operation/<operation-UUID>`.

Existing legacy `vm stop SERVER_ID` keeps its original request/auth behavior and
sends no idempotency header. The new `--idempotency-key` option is rejected on
legacy profiles. Other VM mutations are not enabled for IAM by this command.

## Route coverage note

The CLI's pre-existing route snapshot contained 190 operations and no catalog
routes. Catalog status and IAM operation lookup add two exact operations and
their command mappings (192 entries); STOP reuses the existing action route.
This does not claim that the CLI snapshot covers all current
platform routes. Workspace-wide IAM inventory coverage is checked separately.
