
from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FakeAccessToken:
    token: str
    client_id: str
    scopes: list[str]
    expires_at: int | None = None
    resource: object | None = None
    subject: str | None = None
    claims: dict | None = None


class FakeTokenVerifier:
    pass


provider_module = types.ModuleType("mcp.server.auth.provider")
provider_module.AccessToken = FakeAccessToken
provider_module.TokenVerifier = FakeTokenVerifier

settings_module = types.ModuleType("mcp.server.auth.settings")


class FakeAuthSettings:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


settings_module.AuthSettings = FakeAuthSettings

mcp_module = types.ModuleType("mcp")
server_module = types.ModuleType("mcp.server")
auth_module = types.ModuleType("mcp.server.auth")
mcp_module.server = server_module
server_module.auth = auth_module
auth_module.provider = provider_module
auth_module.settings = settings_module

sys.modules.setdefault("mcp", mcp_module)
sys.modules.setdefault("mcp.server", server_module)
sys.modules.setdefault("mcp.server.auth", auth_module)
sys.modules.setdefault("mcp.server.auth.provider", provider_module)
sys.modules.setdefault("mcp.server.auth.settings", settings_module)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from auth.oauth import (  # noqa: E402
    AuthConfig,
    Principal,
    StaticTokenVerifier,
    build_dev_token_verifier,
    principal_from_access_token,
)


def test_principal_from_access_token():
    token = FakeAccessToken(
        token="abc",
        client_id="agent-1",
        scopes=["mcp:read", "tool:orders:read"],
        subject="user-1",
        claims={
            "tenant": "tenant-a",
            "act": {"sub": "human-1"},
            "custom": "value",
        },
    )

    principal = principal_from_access_token(token)

    assert isinstance(principal, Principal)
    assert principal.client_id == "agent-1"
    assert principal.subject == "user-1"
    assert principal.tenant == "tenant-a"
    assert principal.delegator == "human-1"
    assert principal.has_scope("mcp:read")
    assert not principal.has_scope("tool:orders:write")
    assert principal.claims["custom"] == "value"


def test_static_token_verifier_returns_known_token_and_rejects_unknown():
    known = FakeAccessToken(
        token="known",
        client_id="agent-1",
        scopes=["mcp:read"],
    )
    verifier = StaticTokenVerifier({"known": known})

    assert asyncio.run(verifier.verify_token("known")) == known
    assert asyncio.run(verifier.verify_token("wrong")) is None


def test_auth_config_from_env(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_ENABLED", "true")
    monkeypatch.setenv("MCP_AUTH_ISSUER_URL", "https://issuer.example.com/")
    monkeypatch.setenv("MCP_RESOURCE_SERVER_URL", "http://localhost:8080/mcp")
    monkeypatch.setenv(
        "MCP_REQUIRED_SCOPES",
        "mcp:read tool:orders:read",
    )
    monkeypatch.setenv("MCP_DEV_ACCESS_TOKEN", "dev-secret")

    config = AuthConfig.from_env()

    assert config.enabled is True
    assert config.required_scopes == (
        "mcp:read",
        "tool:orders:read",
    )
    assert config.dev_access_token == "dev-secret"


def test_build_dev_token_verifier_creates_a_resource_scoped_token():
    config = AuthConfig(
        enabled=True,
        resource_server_url="http://127.0.0.1:8080/mcp",
        required_scopes=("mcp:read",),
        dev_access_token="dev-secret",
    )

    verifier = build_dev_token_verifier(config)

    token = asyncio.run(verifier.verify_token("dev-secret"))
    assert token is not None
    assert token.client_id == "local-dev-agent"
    assert token.scopes == ["mcp:read"]
    assert token.resource == "http://127.0.0.1:8080/mcp"
    assert isinstance(token.resource, str)
    assert token.claims["tenant"] == "default"
    assert token.claims["act"]["sub"] == "local-dev-user"
