from __future__ import annotations

import inspect
import logging
import os
import re
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import yaml

from auth.oauth import Principal, principal_from_access_token
from errors.framework import ErrorCode

logger = logging.getLogger(__name__)


class PolicyConfigurationError(ValueError):
    """Raised when a policy file is malformed or unsafe to interpret."""


class AuthorizationDenied(PermissionError):
    """Raised when an authenticated principal is not allowed to invoke a tool."""

    code = ErrorCode.PERMISSION_DENIED


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    effect: str
    resources: tuple[str, ...]
    actions: tuple[str, ...] = ("tool:invoke",)
    required_scopes: frozenset[str] = field(default_factory=frozenset)
    excluded_scopes: frozenset[str] = field(default_factory=frozenset)
    client_ids: tuple[str, ...] = ()
    subjects: tuple[str, ...] = ()
    tenants: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str
    resource: str
    matched_rule_id: str | None = None


class PolicyEngine:
    """Evaluate deterministic rules without consulting LLM-generated identity."""

    def __init__(self, rules: tuple[PolicyRule, ...], *, default_effect: str = "deny"):
        if default_effect != "deny":
            raise PolicyConfigurationError("default_effect must be 'deny'")
        self.rules = tuple(rules)
        self.default_effect = default_effect

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PolicyEngine":
        policy_path = Path(path).expanduser().resolve()
        try:
            with policy_path.open("r", encoding="utf-8") as handle:
                document = yaml.safe_load(handle)
        except OSError as exc:
            raise PolicyConfigurationError(
                f"Could not read policy file: {policy_path}"
            ) from exc
        except yaml.YAMLError as exc:
            raise PolicyConfigurationError(
                f"Policy file is not valid YAML: {policy_path}"
            ) from exc

        if not isinstance(document, dict):
            raise PolicyConfigurationError("Policy document must be a YAML mapping")
        default_effect = document.get("default_effect", "deny")
        if default_effect != "deny":
            raise PolicyConfigurationError("Only default_effect: deny is supported")
        raw_rules = document.get("rules")
        if not isinstance(raw_rules, list):
            raise PolicyConfigurationError("Policy document must contain a rules list")

        rules: list[PolicyRule] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(raw_rules):
            prefix = f"rules[{index}]"
            if not isinstance(item, dict):
                raise PolicyConfigurationError(f"{prefix} must be a mapping")
            rule_id = item.get("id")
            effect = item.get("effect")
            resources = _string_tuple(item.get("resources"), f"{prefix}.resources")
            actions_value = item.get("actions", ["tool:invoke"])
            actions = _string_tuple(actions_value, f"{prefix}.actions")
            if not resources:
                raise PolicyConfigurationError(f"{prefix}.resources must not be empty")
            if not actions:
                raise PolicyConfigurationError(f"{prefix}.actions must not be empty")
            if not isinstance(rule_id, str) or not rule_id.strip():
                raise PolicyConfigurationError(f"{prefix}.id must be a non-empty string")
            if rule_id in seen_ids:
                raise PolicyConfigurationError(f"Duplicate policy rule id: {rule_id}")
            seen_ids.add(rule_id)
            if effect not in {"allow", "deny"}:
                raise PolicyConfigurationError(f"{prefix}.effect must be 'allow' or 'deny'")

            principals = item.get("principals", {})
            if not isinstance(principals, dict):
                raise PolicyConfigurationError(f"{prefix}.principals must be a mapping")
            rules.append(
                PolicyRule(
                    rule_id=rule_id,
                    effect=effect,
                    resources=resources,
                    actions=actions,
                    required_scopes=frozenset(
                        _string_tuple(item.get("required_scopes", []), f"{prefix}.required_scopes")
                    ),
                    excluded_scopes=frozenset(
                        _string_tuple(item.get("excluded_scopes", []), f"{prefix}.excluded_scopes")
                    ),
                    client_ids=_string_tuple(principals.get("client_ids", []), f"{prefix}.principals.client_ids"),
                    subjects=_string_tuple(principals.get("subjects", []), f"{prefix}.principals.subjects"),
                    tenants=_string_tuple(principals.get("tenants", []), f"{prefix}.principals.tenants"),
                )
            )

        return cls(tuple(rules), default_effect=default_effect)

    def evaluate(
        self,
        principal: Principal | None,
        *,
        action: str,
        resource: str,
    ) -> PolicyDecision:
        """Return an explicit decision; a missing principal always fails closed."""
        if principal is None:
            return PolicyDecision(False, "missing_principal", resource)
        if not principal.tenant:
            return PolicyDecision(False, "missing_tenant", resource)
        # Tenant identifiers become part of the resource namespace. Restrict
        # their characters so a claim cannot inject path separators or glob
        # syntax into the policy resource string.
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", principal.tenant):
            return PolicyDecision(False, "invalid_tenant", resource)
        resource_tenant, separator, _resource_path = resource.partition("/")
        if not separator or not resource_tenant.startswith("tenant:"):
            return PolicyDecision(False, "invalid_resource", resource)
        if resource_tenant != f"tenant:{principal.tenant}":
            return PolicyDecision(False, "tenant_mismatch", resource)

        matching = [
            rule for rule in self.rules
            if self._matches(rule, principal, action=action, resource=resource)
        ]
        deny = next((rule for rule in matching if rule.effect == "deny"), None)
        if deny is not None:
            return PolicyDecision(False, "explicit_deny", resource, deny.rule_id)

        allow = next((rule for rule in matching if rule.effect == "allow"), None)
        if allow is not None:
            return PolicyDecision(True, "explicit_allow", resource, allow.rule_id)

        return PolicyDecision(False, "default_deny", resource)

    def _matches(
        self,
        rule: PolicyRule,
        principal: Principal,
        *,
        action: str,
        resource: str,
    ) -> bool:
        if not any(fnmatchcase(resource, pattern) for pattern in rule.resources):
            return False
        if not any(fnmatchcase(action, pattern) for pattern in rule.actions):
            return False
        if not rule.required_scopes.issubset(principal.scopes):
            return False
        if rule.excluded_scopes.intersection(principal.scopes):
            return False
        if rule.client_ids and not _matches_any(principal.client_id, rule.client_ids):
            return False
        if rule.subjects and not _matches_any(principal.subject, rule.subjects):
            return False
        if rule.tenants and not _matches_any(principal.tenant, rule.tenants):
            return False
        return True


def filter_tools_for_principal(
    policy_engine: PolicyEngine,
    tools: list[Any] | tuple[Any, ...],
    principal: Principal | None,
) -> list[Any]:
    """Return only tools the principal is allowed to invoke."""
    
    visible: list[Any] = []
    for tool in tools:
        tool_name = getattr(tool, "name", None)
        if not isinstance(tool_name, str) or not tool_name:
            # Malformed tool descriptors should never become visible.
            continue
        tenant = principal.tenant if principal is not None else None
        resource = f"tenant:{tenant if tenant else 'unknown'}/{tool_name}"
        decision = policy_engine.evaluate(
            principal,
            action="tool:invoke",
            resource=resource,
        )
        if decision.allowed:
            visible.append(tool)
    return visible


def default_policy_path() -> Path:
    """Resolve policy configuration without depending on the caller's cwd."""
    configured_path = os.getenv("MCP_POLICY_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return Path(__file__).resolve().parent.parent / "config" / "policy.yaml"


def _get_sdk_access_token():
    """Read the SDK's already-verified request token from its auth context."""
    try:
        from mcp.server.auth.middleware.auth_context import get_access_token
    except ImportError as exc:  # pragma: no cover - only broken SDK installations
        raise RuntimeError(
            "Installed MCP SDK does not expose its authenticated access-token context"
        ) from exc
    return get_access_token()


def current_principal_from_sdk() -> Principal | None:
    """Return a normalized principal from the MCP SDK's verified auth context."""
    access_token = _get_sdk_access_token()
    if access_token is None:
        return None
    return principal_from_access_token(access_token)


def tool_authorization_guard(
    policy_engine: PolicyEngine,
    tool_name: str,
    *,
    enabled: bool,
    access_token_getter: Callable[[], Any] | None = None,
):
    """Wrap a tool handler so policy runs after authentication and before work."""
    if not enabled:
        return lambda handler: handler

    token_getter = access_token_getter or _get_sdk_access_token

    def decorator(handler: Callable[..., Any]):
        def authorize() -> None:
            access_token = token_getter()
            if access_token is None:
                decision = PolicyDecision(
                    False,
                    "missing_principal",
                    f"tenant:unknown/{tool_name}",
                )
                logger.warning(
                    "Tool authorization denied tool=%s reason=%s",
                    tool_name,
                    decision.reason,
                )
                raise AuthorizationDenied(
                    f"Access denied for tool '{tool_name}' ({decision.reason})"
                )

            principal = principal_from_access_token(access_token)
            tenant = principal.tenant or "unknown"
            resource = f"tenant:{tenant}/{tool_name}"
            decision = policy_engine.evaluate(
                principal,
                action="tool:invoke",
                resource=resource,
            )
            if not decision.allowed:
                logger.warning(
                    "Tool authorization denied tool=%s tenant=%s reason=%s rule=%s",
                    tool_name,
                    tenant,
                    decision.reason,
                    decision.matched_rule_id,
                )
                raise AuthorizationDenied(
                    f"Access denied for tool '{tool_name}' ({decision.reason})"
                )

        if inspect.iscoroutinefunction(handler):
            @wraps(handler)
            async def async_wrapper(*args, **kwargs):
                authorize()
                return await handler(*args, **kwargs)
            return async_wrapper

        @wraps(handler)
        def sync_wrapper(*args, **kwargs):
            authorize()
            return handler(*args, **kwargs)
        return sync_wrapper

    return decorator


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise PolicyConfigurationError(f"{label} must be a list of strings")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise PolicyConfigurationError(f"{label} must contain only non-empty strings")
    return tuple(value)


def _matches_any(value: str | None, patterns: tuple[str, ...]) -> bool:
    if value is None:
        return False
    return any(fnmatchcase(value, pattern) for pattern in patterns)
