"""Explicit IAM profiles and isolated credentials; legacy auth never enters here."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import keyring
import keyring.errors
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from neviri_cli.client.base import BaseClient
from neviri_cli.config import ProfileConfig, get_config_path
from neviri_cli.credentials import FileTokenStore, TokenStore
from neviri_cli.exceptions import AuthError, ServerError, UserError

IAM_SERVICE_NAME = "neviri-cli-iam"
IAM_ENV_TOKEN = "NEVIRI_IAM_SESSION_TOKEN"  # nosec B105 - environment name
IAM_ENV_KEY = "NEVIRI_IAM_ACCESS_KEY_ID"
IAM_ENV_SECRET = "NEVIRI_IAM_SECRET_ACCESS_KEY"  # nosec B105 - environment name


class IAMKeyringStore:
    def get(self, profile: str) -> str | None:
        try:
            return keyring.get_password(IAM_SERVICE_NAME, profile)
        except keyring.errors.KeyringError as exc:
            raise AuthError("IAM credential store is unavailable") from exc

    def set(self, profile: str, token: str) -> None:
        try:
            keyring.set_password(IAM_SERVICE_NAME, profile, token)
        except keyring.errors.KeyringError as exc:
            raise AuthError("IAM credential store is unavailable") from exc

    def delete(self, profile: str) -> None:
        try:
            keyring.delete_password(IAM_SERVICE_NAME, profile)
        except keyring.errors.PasswordDeleteError as exc:
            # The backend does not distinguish missing from a failed delete.
            # Confirm absence before claiming local cleanup succeeded.
            try:
                remaining = keyring.get_password(IAM_SERVICE_NAME, profile)
            except keyring.errors.KeyringError as read_error:
                raise AuthError("IAM credential deletion could not be confirmed") from read_error
            if remaining is not None:
                raise AuthError("IAM credentials remain in the keyring") from exc
        except keyring.errors.KeyringError as exc:
            raise AuthError("IAM credentials could not be cleared from the keyring") from exc


class IAMCredentials(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_key_id: str | None = None
    secret_access_key: str | None = Field(default=None, repr=False)
    access_token: str | None = Field(default=None, repr=False)
    expires_at: datetime | None = None
    principal_arn: str | None = None
    principal_type: str | None = None
    role_arn: str | None = None
    iam_origin: str | None = None
    api_origin: str | None = None
    role_fingerprint: str | None = None
    account_id: int | None = None


def iam_store() -> TokenStore:
    backend = os.environ.get("NEVIRI_IAM_TOKEN_STORE", os.environ.get("NEVIRI_TOKEN_STORE", ""))
    if backend.lower() == "file":
        path = Path(
            os.environ.get(
                "NEVIRI_IAM_CREDENTIALS", str(Path.home() / ".neviri" / "iam-credentials.json")
            )
        )
        legacy_path = Path(
            os.environ.get("NEVIRI_CREDENTIALS", str(Path.home() / ".neviri" / "credentials.json"))
        )
        for protected in (legacy_path, get_config_path()):
            try:
                collision = path.resolve() == protected.resolve() or (
                    path.exists() and protected.exists() and os.path.samefile(path, protected)
                )
            except OSError as exc:
                raise UserError("Unable to validate IAM credential-file isolation") from exc
            if collision:
                raise UserError(
                    "IAM credentials must use a file separate from legacy credentials and config"
                )
        return FileTokenStore(path)
    return IAMKeyringStore()


def load_iam_credentials(profile: str) -> IAMCredentials:
    raw = iam_store().get(profile)
    if raw is None:
        return IAMCredentials()
    try:
        return IAMCredentials.model_validate_json(raw)
    except ValidationError as exc:
        raise AuthError("Stored IAM credentials are invalid; run `neviri iam login` again") from exc


def save_iam_credentials(profile: str, credentials: IAMCredentials) -> None:
    iam_store().set(profile, credentials.model_dump_json())


def validate_iam_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise UserError("Invalid IAM URL") from exc
    if (
        not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
        or parsed.scheme not in ("https", "http")
        or (parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"})
    ):
        raise UserError("IAM credentials require an HTTPS origin, or HTTP on localhost only")
    return value.rstrip("/")


def require_iam_profile(profile: ProfileConfig) -> None:
    if profile.auth_mode != "iam":
        raise UserError("Choose an explicit IAM profile with `neviri iam configure` first")


def _session(iam_url: str, token: str, *, debug: bool) -> dict[str, Any]:
    with BaseClient(
        validate_iam_origin(iam_url), token=token, debug=debug, max_retries=0
    ) as client:
        result = client.get("/v1/session")
    if (
        not isinstance(result, dict)
        or result.get("kind") != "user"
        or result.get("principal_type") not in ("iam_user", "iam_role_session")
        or type(result.get("account_id")) is not int
        or result["account_id"] <= 0
        or not isinstance(result.get("principal_arn"), str)
    ):
        raise ServerError("IAM service returned an invalid session summary")
    fields = (
        "kind",
        "account_id",
        "principal_id",
        "principal_arn",
        "principal_type",
        "session_id",
        "session_name",
        "expires_at",
        "mfa_verified",
        "enforcement_mode",
        "source_principal_arn",
    )
    return {key: result[key] for key in fields if key in result}


def _expiry(value: Any) -> datetime:
    try:
        if not isinstance(value, str):
            raise ValueError()
        expiry = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(UTC):
            raise ValueError()
        return expiry
    except ValueError as exc:
        raise ServerError("IAM service returned an invalid session expiry") from exc


def _result_credentials(
    iam_url: str,
    result: Any,
    previous: IAMCredentials,
    *,
    debug: bool,
    role_arn: str | None,
) -> IAMCredentials:
    if not isinstance(result, dict) or not isinstance(result.get("access_token"), str):
        raise ServerError("IAM service returned no temporary credential")
    token = result["access_token"]
    metadata = _session(iam_url, token, debug=debug)
    expiry = min(_expiry(result.get("expires_at")), _expiry(metadata.get("expires_at")))
    if role_arn is not None and (
        metadata.get("principal_type") != "iam_role_session"
        or metadata["principal_arn"] != role_arn
    ):
        raise ServerError("IAM role session does not match the requested role")
    if role_arn is None and metadata.get("principal_type") != "iam_user":
        raise ServerError("IAM user session was expected")
    return previous.model_copy(
        update={
            "access_token": token,
            "expires_at": expiry,
            "principal_arn": metadata["principal_arn"],
            "principal_type": metadata["principal_type"],
            "role_arn": role_arn,
            "account_id": metadata["account_id"],
        }
    )


def exchange_access_key(
    profile: ProfileConfig,
    credentials: IAMCredentials,
    *,
    debug: bool = False,
) -> IAMCredentials:
    if credentials.iam_origin is not None:
        ensure_bound(profile, credentials)
    if not credentials.access_key_id or not credentials.secret_access_key:
        raise AuthError("Both IAM access-key ID and secret are required")
    if not credentials.access_key_id.startswith("NVIA"):
        raise UserError(
            "IAM access-key IDs start with NVIA; legacy nvr_ tokens use legacy profiles"
        )
    with BaseClient(validate_iam_origin(profile.iam_url), debug=debug, max_retries=0) as client:
        result = client.post(
            "/v1/sts/token",
            json={
                "access_key_id": credentials.access_key_id,
                "secret_access_key": credentials.secret_access_key,
                "session_name": profile.iam_session_name,
            },
        )
    previous = credentials.model_copy(
        update={
            "iam_origin": validate_iam_origin(profile.iam_url),
            "api_origin": validate_iam_origin(profile.api_url),
            "role_fingerprint": None,
        }
    )
    return _result_credentials(profile.iam_url, result, previous, debug=debug, role_arn=None)


def login_console(
    profile: ProfileConfig,
    account_id: int,
    username: str,
    password: str,
    mfa_code: str | None = None,
    *,
    debug: bool = False,
) -> IAMCredentials:
    with BaseClient(validate_iam_origin(profile.iam_url), debug=debug, max_retries=0) as client:
        result = client.post(
            "/v1/console/login",
            json={
                "account_id": account_id,
                "username": username,
                "password": password,
                "session_name": profile.iam_session_name,
                **({"mfa_code": mfa_code} if mfa_code else {}),
            },
        )
    previous = IAMCredentials(
        iam_origin=validate_iam_origin(profile.iam_url),
        api_origin=validate_iam_origin(profile.api_url),
    )
    credentials = _result_credentials(profile.iam_url, result, previous, debug=debug, role_arn=None)
    # The authenticated server summary, not unsigned token claims, binds account.
    if credentials.account_id != account_id:
        raise ServerError("IAM console session belongs to another account")
    return credentials


def assume_role(
    profile: ProfileConfig,
    source: IAMCredentials,
    *,
    debug: bool = False,
) -> IAMCredentials:
    ensure_bound(profile, source)
    if not profile.iam_role_arn or not source.access_token:
        raise UserError("A source IAM user session and role ARN are required")
    if source.principal_type != "iam_user":
        raise AuthError("Role chaining is unavailable; sign in as an IAM user first")
    with BaseClient(
        validate_iam_origin(profile.iam_url), token=source.access_token, debug=debug, max_retries=0
    ) as client:
        result = client.post(
            "/v1/sts/assume-role",
            json={
                "role_arn": profile.iam_role_arn,
                "session_name": profile.iam_session_name,
                "duration_seconds": profile.iam_duration_seconds,
                **({"external_id": profile.iam_external_id} if profile.iam_external_id else {}),
                **(
                    {"session_policy": profile.iam_session_policy}
                    if profile.iam_session_policy is not None
                    else {}
                ),
            },
        )
    issued = _result_credentials(
        profile.iam_url, result, source, debug=debug, role_arn=profile.iam_role_arn
    )
    return issued.model_copy(update={"role_fingerprint": _role_binding(profile)})


def _role_binding(profile: ProfileConfig) -> str:
    document = {
        "role": profile.iam_role_arn,
        "name": profile.iam_session_name,
        "duration": profile.iam_duration_seconds,
        "external": profile.iam_external_id,
        "policy": profile.iam_session_policy,
    }
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def ensure_bound(profile: ProfileConfig, credentials: IAMCredentials) -> None:
    if credentials.iam_origin != validate_iam_origin(
        profile.iam_url
    ) or credentials.api_origin != validate_iam_origin(profile.api_url):
        raise AuthError(
            "IAM endpoints changed; run `neviri iam login` before reusing stored credentials"
        )


def _fresh(credentials: IAMCredentials) -> bool:
    return bool(
        credentials.access_token
        and credentials.expires_at
        and credentials.expires_at.tzinfo
        and credentials.expires_at > datetime.now(UTC) + timedelta(seconds=30)
    )


def resolve_iam_token(profile_name: str, profile: ProfileConfig, *, debug: bool = False) -> str:
    require_iam_profile(profile)
    override = os.environ.get(IAM_ENV_TOKEN)
    if override:
        # IAM's explicit environment override never reads/writes legacy stores.
        summary = _session(profile.iam_url, override, debug=debug)
        expires_at = _expiry(summary.get("expires_at"))
        if profile.iam_role_arn:
            if summary["principal_type"] == "iam_user":
                source = IAMCredentials(
                    access_token=override,
                    expires_at=expires_at,
                    principal_type="iam_user",
                    principal_arn=summary["principal_arn"],
                    iam_origin=validate_iam_origin(profile.iam_url),
                    api_origin=validate_iam_origin(profile.api_url),
                    account_id=summary["account_id"],
                )
                return assume_role(profile, source, debug=debug).access_token or ""
            if (
                summary["principal_arn"] != profile.iam_role_arn
                or profile.iam_session_policy is not None
            ):
                raise AuthError(
                    "IAM session override cannot prove the configured role/session-policy binding"
                )
        return override
    key, secret = os.environ.get(IAM_ENV_KEY), os.environ.get(IAM_ENV_SECRET)
    if bool(key) != bool(secret):
        raise AuthError(
            "Both NEVIRI_IAM_ACCESS_KEY_ID and NEVIRI_IAM_SECRET_ACCESS_KEY are required"
        )
    credentials = (
        IAMCredentials(access_key_id=key, secret_access_key=secret)
        if key
        else load_iam_credentials(profile_name)
    )
    if not key and any(
        (credentials.access_token, credentials.access_key_id, credentials.secret_access_key)
    ):
        ensure_bound(profile, credentials)
    if (
        not key
        and _fresh(credentials)
        and credentials.role_arn == profile.iam_role_arn
        and (profile.iam_role_arn is None or credentials.role_fingerprint == _role_binding(profile))
    ):
        return credentials.access_token or ""
    if credentials.access_key_id and credentials.secret_access_key:
        credentials = exchange_access_key(profile, credentials, debug=debug)
    elif not _fresh(credentials) or credentials.principal_type != "iam_user":
        raise AuthError("No renewable IAM session; run `neviri iam login` again")
    if profile.iam_role_arn:
        credentials = assume_role(profile, credentials, debug=debug)
    if not key:
        save_iam_credentials(profile_name, credentials)
    return credentials.access_token or ""


def current_iam_identity(
    profile_name: str, profile: ProfileConfig, *, debug: bool = False
) -> dict[str, Any]:
    return _session(
        profile.iam_url, resolve_iam_token(profile_name, profile, debug=debug), debug=debug
    )


def logout_iam(profile_name: str, profile: ProfileConfig, *, debug: bool = False) -> bool:
    credentials = load_iam_credentials(profile_name)
    revoked = True
    try:
        if credentials.access_token:
            try:
                ensure_bound(profile, credentials)
            except AuthError:
                return False
            with BaseClient(
                validate_iam_origin(profile.iam_url),
                token=credentials.access_token,
                debug=debug,
                max_retries=0,
            ) as client:
                client.delete("/v1/session")
    except AuthError:
        pass
    except Exception:
        # Local cleanup must work during outages; do not claim server revocation.
        revoked = False
    finally:
        iam_store().delete(profile_name)
    return revoked
