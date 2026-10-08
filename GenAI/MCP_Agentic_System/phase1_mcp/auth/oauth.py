from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Mapping

from mcp.server.auth.provider import AccessToken, TokenVerifier
from pydantic import AnyHttpUrl


@dataclass(frozen=True)
class AuthConfig:
    """Configuration for the MCP server's OAuth resource-server boundary."""

    enabled: bool = False
    issuer_url: str = "https://auth.example.com/"
    resource_server_url: str = "http://127.0.0.1:8080/mcp"
    required_scopes: tuple[str, ...] = ("mcp:read",)
    dev_access_token: str | None = None

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

        return cls(
            enabled=enabled,
            issuer_url=os.getenv(
                "MCP_AUTH_ISSUER_URL",
                "https://auth.example.com/",
            ),
            resource_server_url=os.getenv(
                "MCP_RESOURCE_SERVER_URL",
                "http://127.0.0.1:8080/mcp",
            ),
            required_scopes=required_scopes,
            dev_access_token=os.getenv("MCP_DEV_ACCESS_TOKEN"),
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
