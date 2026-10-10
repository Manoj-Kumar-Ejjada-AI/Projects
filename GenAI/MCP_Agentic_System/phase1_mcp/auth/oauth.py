from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Mapping
from urllib.parse import urlparse

import httpx
import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier
from pydantic import AnyHttpUrl


logger = logging.getLogger(__name__)

_ALLOWED_ASYMMETRIC_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"}
)


@dataclass(frozen=True)
class AuthConfig:
    """Configuration for the MCP server's OAuth resource-server boundary.
    
    The MCP server validates tokens; it does not issue them. ``static`` mode is
    only for local development. ``jwt`` mode validates signed JWT access tokens
    using the authorization server's JWKS endpoint.
    """

    enabled: bool = False
    auth_mode: str = "static"
    issuer_url: str = "https://auth.example.com/"
    resource_server_url: str = "http://127.0.0.1:8080/mcp"
    jwks_url: str | None = None
    required_scopes: tuple[str, ...] = ("mcp:read",)
    dev_access_token: str | None = None
    jwt_algorithms: tuple[str, ...] = ("RS256",)
    jwks_cache_seconds: int = 300
    jwt_leeway_seconds: int = 30
    jwks_refresh_cooldown_seconds: int = 30
    jwks_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "AuthConfig":
        """Build authentication configuration from environment variables."""
        required_scopes = tuple(
            scope
            for scope in os.getenv("MCP_REQUIRED_SCOPES", "mcp:read").split()
            if scope
        )

        if not required_scopes:
            raise ValueError("MCP_REQUIRED_SCOPES must contain at least one scope")

        enabled = os.getenv("MCP_AUTH_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        auth_mode = os.getenv("MCP_AUTH_MODE", "static").strip().lower()
        if auth_mode not in {"static", "jwt"}:
            raise ValueError("MCP_AUTH_MODE must be either 'static' or 'jwt'")

        algorithms = tuple(
            algorithm.strip()
            for algorithm in os.getenv("MCP_AUTH_JWT_ALGORITHMS", "RS256").split(",")
            if algorithm.strip()
        )
        if not algorithms or any(
            algorithm not in _ALLOWED_ASYMMETRIC_ALGORITHMS
            for algorithm in algorithms
        ):
            raise ValueError(
                "MCP_AUTH_JWT_ALGORITHMS may contain only supported asymmetric "
                "algorithms: RS256, RS384, RS512, ES256, ES384, ES512, EdDSA"
            )

        jwks_cache_seconds = int(os.getenv("MCP_AUTH_JWKS_CACHE_SECONDS", "300"))
        jwt_leeway_seconds = int(os.getenv("MCP_AUTH_JWT_LEEWAY_SECONDS", "30"))
        jwks_refresh_cooldown_seconds = int(
            os.getenv("MCP_AUTH_JWKS_REFRESH_COOLDOWN_SECONDS", "30")
        )
        jwks_timeout_seconds = float(os.getenv("MCP_AUTH_JWKS_TIMEOUT_SECONDS", "5"))
        if jwks_cache_seconds < 1:
            raise ValueError("MCP_AUTH_JWKS_CACHE_SECONDS must be >= 1")
        if jwt_leeway_seconds < 0:
            raise ValueError("MCP_AUTH_JWT_LEEWAY_SECONDS must be >= 0")
        if jwks_refresh_cooldown_seconds < 0:
            raise ValueError("MCP_AUTH_JWKS_REFRESH_COOLDOWN_SECONDS must be >= 0")
        if jwks_timeout_seconds <= 0:
            raise ValueError("MCP_AUTH_JWKS_TIMEOUT_SECONDS must be > 0")

        return cls(
            enabled=enabled,
            auth_mode=auth_mode,
            issuer_url=os.getenv(
                "MCP_AUTH_ISSUER_URL",
                "https://auth.example.com/",
            ),
            resource_server_url=os.getenv(
                "MCP_RESOURCE_SERVER_URL",
                "http://127.0.0.1:8080/mcp",
            ),
            jwks_url=os.getenv("MCP_AUTH_JWKS_URL")
            or os.getenv("ATLAS_AUTH_JWKS_URL"),
            required_scopes=required_scopes,
            dev_access_token=os.getenv("MCP_DEV_ACCESS_TOKEN"),
            jwt_algorithms=algorithms,
            jwks_cache_seconds=jwks_cache_seconds,
            jwt_leeway_seconds=jwt_leeway_seconds,
            jwks_refresh_cooldown_seconds=jwks_refresh_cooldown_seconds,
            jwks_timeout_seconds=jwks_timeout_seconds,
        )



@dataclass(frozen=True)
class Principal:
    """Identity information used by later policy/tenant layers."""

    client_id: str
    subject: str | None = None
    tenant: str | None = None
    scopes: frozenset[str] = field(default_factory=frozenset)
    delegator: str | None = None
    claims: Mapping[str, Any] = field(default_factory=dict)

    def has_scope(self, scope: str) -> bool:
        """Return True when this principal has the requested OAuth scope."""
        return scope in self.scopes


def principal_from_access_token(access_token: AccessToken) -> Principal:
    """Convert the SDK AccessToken into stable application identity model."""
    claims = dict(access_token.claims or {})

    tenant = claims.get("tenant")

    actor = claims.get("act")
    delegator = actor.get("sub") if isinstance(actor, dict) else None

    subject = access_token.subject or claims.get("sub")

    return Principal(
        client_id=access_token.client_id,
        subject=subject,
        tenant=tenant if isinstance(tenant, str) else None,
        scopes=frozenset(access_token.scopes),
        delegator=delegator if isinstance(delegator, str) else None,
        claims=claims,
    )


class StaticTokenVerifier(TokenVerifier):
    """Development-only token verifier backed by an in-memory token map."""

    def __init__(self, tokens: Mapping[str, AccessToken]):
        self._tokens = dict(tokens)

    async def verify_token(self, token: str) -> AccessToken | None:
        return self._tokens.get(token)


class JwksJWTVerifier(TokenVerifier):
    """Validate signed JWT access tokens against a cached authorization-server JWKS."""

    def __init__(
        self,
        *,
        issuer_url: str,
        resource_server_url: str,
        jwks_url: str,
        algorithms: tuple[str, ...] = ("RS256",),
        cache_seconds: int = 300,
        leeway_seconds: int = 30,
        refresh_cooldown_seconds: int = 30,
        timeout_seconds: float = 5.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not issuer_url.strip():
            raise ValueError("issuer_url must not be empty")
        if not resource_server_url.strip():
            raise ValueError("resource_server_url must not be empty")
        if not jwks_url.strip():
            raise ValueError("jwks_url must not be empty")
        _validate_jwks_url(jwks_url)
        if not algorithms or any(
            algorithm not in _ALLOWED_ASYMMETRIC_ALGORITHMS
            for algorithm in algorithms
        ):
            raise ValueError("JWT verifier requires supported asymmetric algorithms")
        if cache_seconds < 1:
            raise ValueError("cache_seconds must be >= 1")
        if leeway_seconds < 0:
            raise ValueError("leeway_seconds must be >= 0")
        if refresh_cooldown_seconds < 0:
            raise ValueError("refresh_cooldown_seconds must be >= 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")

        self.issuer_url = issuer_url
        self.resource_server_url = resource_server_url
        self.jwks_url = jwks_url
        self.algorithms = tuple(algorithms)
        self.cache_seconds = cache_seconds
        self.leeway_seconds = leeway_seconds
        self.refresh_cooldown_seconds = refresh_cooldown_seconds
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client
        self._jwks: dict[str, dict[str, Any]] = {}
        self._cache_expires_at = 0.0
        self._last_refresh_at = float("-inf")
        self._refresh_lock = asyncio.Lock()

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an SDK AccessToken only when the JWT validates completely."""
        if not isinstance(token, str) or not token:
            return None

        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            return None

        kid = header.get("kid")
        algorithm = header.get("alg")
        if not isinstance(kid, str) or not kid:
            return None
        if not isinstance(algorithm, str) or algorithm not in self.algorithms:
            return None

        try:
            jwk_document = await self._get_jwk(kid)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("Unable to retrieve a usable MCP JWKS document: %s", exc)
            return None

        if jwk_document is None:
            return None

        jwk_algorithm = jwk_document.get("alg")
        if jwk_algorithm is not None and jwk_algorithm != algorithm:
            return None
        if jwk_document.get("use") not in (None, "sig"):
            return None
        key_ops = jwk_document.get("key_ops")
        if key_ops is not None and "verify" not in key_ops:
            return None

        try:
            signing_key = jwt.PyJWK.from_dict(
                jwk_document,
                algorithm=algorithm,
            ).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=list(self.algorithms),
                issuer=self.issuer_url,
                audience=self.resource_server_url,
                leeway=self.leeway_seconds,
                options={"require": ["exp", "iat", "sub", "jti", "aud", "iss"]},
            )
        except jwt.PyJWTError:
            return None
        except (TypeError, ValueError, OverflowError):
            return None

        subject_claim = claims.get("sub")
        token_id_claim = claims.get("jti")
        if not isinstance(subject_claim, str) or not subject_claim:
            return None
        if not isinstance(token_id_claim, str) or not token_id_claim:
            return None

        client_id_claim = (
            claims.get("client_id")
            or claims.get("azp")
            or claims.get("appid")
            or subject_claim
        )
        if not isinstance(client_id_claim, str) or not client_id_claim:
            return None
        subject = subject_claim if isinstance(subject_claim, str) else None

        scope_claim = claims.get("scope", claims.get("scp", []))
        if isinstance(scope_claim, str):
            scopes = scope_claim.split()
        elif isinstance(scope_claim, list) and all(
            isinstance(scope, str) for scope in scope_claim
        ):
            scopes = scope_claim
        else:
            return None

        try:
            expires_at = int(claims["exp"])
        except (KeyError, TypeError, ValueError, OverflowError):
            return None

        return AccessToken(
            token=token,
            client_id=client_id_claim,
            scopes=scopes,
            expires_at=expires_at,
            resource=self.resource_server_url,
            subject=subject,
            claims=claims,
        )

    async def _get_jwk(self, kid: str) -> dict[str, Any] | None:
        now = time.monotonic()
        if now < self._cache_expires_at:
            cached = self._jwks.get(kid)
            if cached is not None:
                return cached
            if now - self._last_refresh_at < self.refresh_cooldown_seconds:
                return None

        async with self._refresh_lock:
            now = time.monotonic()
            if now < self._cache_expires_at:
                cached = self._jwks.get(kid)
                if cached is not None:
                    return cached
                if now - self._last_refresh_at < self.refresh_cooldown_seconds:
                    return None

            jwks_document = await self._fetch_jwks()
            key_documents = jwks_document.get("keys")
            if not isinstance(key_documents, list):
                raise ValueError("JWKS response must contain a 'keys' array")

            refreshed: dict[str, dict[str, Any]] = {}
            for key_document in key_documents:
                if not isinstance(key_document, dict):
                    continue
                key_id = key_document.get("kid")
                if not isinstance(key_id, str) or not key_id:
                    continue
                key_type = key_document.get("kty")
                if key_type not in {"RSA", "EC", "OKP"}:
                    continue
                if key_document.get("use") not in (None, "sig"):
                    continue
                key_ops = key_document.get("key_ops")
                if key_ops is not None and "verify" not in key_ops:
                    continue
                declared_alg = key_document.get("alg")
                if declared_alg is not None and declared_alg not in self.algorithms:
                    continue
                refreshed[key_id] = key_document

            if not refreshed:
                raise ValueError("JWKS response did not contain usable signing keys")

            self._jwks = refreshed
            self._cache_expires_at = time.monotonic() + self.cache_seconds
            self._last_refresh_at = time.monotonic()
            return self._jwks.get(kid)

    async def _fetch_jwks(self) -> dict[str, Any]:
        if self._http_client is not None:
            response = await self._http_client.get(
                self.jwks_url,
                timeout=self.timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
            document = response.json()
        else:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(self.jwks_url, follow_redirects=False)
                response.raise_for_status()
                document = response.json()

        if not isinstance(document, dict):
            raise ValueError("JWKS response must be a JSON object")
        return document


def _validate_jwks_url(jwks_url: str) -> None:
    """Require HTTPS for remote JWKS URLs; allow HTTP only on loopback in dev."""
    parsed = urlparse(jwks_url)
    if parsed.scheme == "https" and parsed.hostname:
        return
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "http" and parsed.hostname in local_hosts:
        return
    raise ValueError(
        "MCP_AUTH_JWKS_URL must use HTTPS; HTTP is allowed only for loopback "
        "development URLs"
    )
def build_dev_token_verifier(config: AuthConfig) -> StaticTokenVerifier:
    """Build a local verifier from the configured development bearer token."""
    if not config.dev_access_token:
        raise ValueError(
            "MCP_DEV_ACCESS_TOKEN must be set when MCP authentication is enabled"
        )

    resource = AnyHttpUrl(config.resource_server_url)

    access_token = AccessToken(
        token=config.dev_access_token,
        client_id="local-dev-agent",
        scopes=list(config.required_scopes),
        resource=resource,
        subject="local-dev-user",
        claims={
            "tenant": "default",
            "act": {"sub": "local-dev-user"},
        },
    )

    return StaticTokenVerifier({config.dev_access_token: access_token})
    
def build_token_verifier(config: AuthConfig) -> TokenVerifier:
    """Select the configured authentication verifier for the MCP resource server."""
    if config.auth_mode == "static":
        return build_dev_token_verifier(config)
    if config.auth_mode == "jwt":
        if not config.jwks_url:
            raise ValueError(
                "MCP_AUTH_JWKS_URL is required when MCP_AUTH_MODE=jwt "
                "(ATLAS_AUTH_JWKS_URL is also accepted)"
            )
        return JwksJWTVerifier(
            issuer_url=config.issuer_url,
            resource_server_url=config.resource_server_url,
            jwks_url=config.jwks_url,
            algorithms=config.jwt_algorithms,
            cache_seconds=config.jwks_cache_seconds,
            leeway_seconds=config.jwt_leeway_seconds,
            refresh_cooldown_seconds=config.jwks_refresh_cooldown_seconds,
            timeout_seconds=config.jwks_timeout_seconds,
        )
    raise ValueError(f"Unsupported MCP_AUTH_MODE: {config.auth_mode!r}")

