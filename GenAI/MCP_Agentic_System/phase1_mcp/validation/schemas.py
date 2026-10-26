"""Strict, reusable input validation for agent and MCP tool calls.

Pydantic models define the application's trusted argument contract. JSON Schema
validation remains the fallback for tools discovered from remote MCP servers.
"""
from __future__ import annotations

import inspect
import logging
from functools import wraps
from typing import Annotated, Any, Callable, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError as JsonSchemaDefinitionError
from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError

from errors.framework import ErrorCode, StructuredError

logger = logging.getLogger(__name__)


PositiveIdentifier = Annotated[
    int,
    Field(
        strict=True,
        ge=1,
        description="A positive integer identifier.",
    ),
]

BoundedDelay = (
    Annotated[
        int,
        Field(strict=True, ge=0, le=10, description="Delay in seconds, from 0 to 10."),
    ]
    | Annotated[
        float,
        Field(
            strict=True,
            ge=0,
            le=10,
            allow_inf_nan=False,
            description="Delay in seconds, from 0 to 10.",
        ),
    ]
)


class StrictToolArguments(BaseModel):
    """Base contract: strict types and no unexpected fields."""

    model_config = ConfigDict(extra="forbid", strict=True)


class GetCustomerArguments(StrictToolArguments):
    customer_id: PositiveIdentifier


class ListCustomersArguments(StrictToolArguments):
    """The list_customers tool accepts no arguments."""


class GetOrderArguments(StrictToolArguments):
    order_id: PositiveIdentifier


class SlowToolArguments(StrictToolArguments):
    delay: BoundedDelay = 0.0


TOOL_ARGUMENT_MODELS: dict[str, type[BaseModel]] = {
    "get_customer": GetCustomerArguments,
    "list_customers": ListCustomersArguments,
    "get_order": GetOrderArguments,
    "slow_tool": SlowToolArguments,
}


class ToolInputValidationException(ValueError):
    """Fallback for validation failures when the MCP SDK is unavailable."""

    def __init__(self, error: StructuredError) -> None:
        self.error = error
        super().__init__(error.message)


class ToolInputValidator:
    

    def validate(self, tool: Any, arguments: Any) -> StructuredError | None:
        tool_name, schema, model = self._resolve_tool_contract(tool)

        if not isinstance(arguments, dict):
            return StructuredError(
                code=ErrorCode.INVALID_TOOL_ARGUMENTS,
                message=f"Arguments for tool '{tool_name}' must be a JSON object.",
                retryable=False,
                hint="Send the tool arguments as an object containing the named fields.",
                details={"tool": tool_name, "validation_errors": [{
                    "path": "$",
                    "message": "expected an object",
                }]},
            )

        if schema is not None:
            schema_error = self._json_schema_error(tool_name, schema, arguments)
            if schema_error is not None:
                return schema_error

        if model is not None:
            try:
                model.model_validate(arguments)
            except PydanticValidationError as exc:
                return self._pydantic_error(tool_name, exc)
            return None

        if schema is None:
            return StructuredError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"No valid input schema is registered for tool '{tool_name}'.",
                retryable=False,
                hint="Check the tool's input schema registration.",
                details={"tool": tool_name, "reason": "missing_input_schema"},
            )

        return None

    @staticmethod
    def _json_schema_error(
        tool_name: str,
        schema: dict[str, Any],
        arguments: dict[str, Any],
    ) -> StructuredError | None:
        try:
            Draft202012Validator.check_schema(schema)
        except JsonSchemaDefinitionError as exc:
            logger.error(
                "Invalid JSON Schema registered for tool=%s: %s",
                tool_name,
                exc.message,
            )
            return StructuredError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"The input schema for tool '{tool_name}' is invalid.",
                retryable=False,
                hint="Correct the tool schema before exposing the tool.",
                details={"tool": tool_name, "reason": "invalid_input_schema"},
            )

        validator = Draft202012Validator(schema)
        errors = sorted(
            validator.iter_errors(arguments),
            key=lambda error: (list(map(str, error.absolute_path)), error.validator or ""),
        )
        if not errors:
            return None

        details = [
            {
                "path": _json_path(error.absolute_path),
                "keyword": str(error.validator or "schema"),
                "message": _json_schema_message(error),
            }
            for error in errors[:8]
        ]
        first = details[0]
        hint = (
            f"Correct '{first['path']}' and retry."
            if first["path"] != "$"
            else "Correct the tool arguments and retry."
        )
        return StructuredError(
            code=ErrorCode.INVALID_TOOL_ARGUMENTS,
            message=f"Invalid arguments for tool '{tool_name}'.",
            retryable=False,
            hint=hint,
            details={"tool": tool_name, "validation_errors": details},
        )

    @staticmethod
    def _resolve_tool_contract(tool: Any) -> tuple[str, dict[str, Any] | None, type[BaseModel] | None]:
        if isinstance(tool, str):
            tool_name = tool
            schema = None
            model = TOOL_ARGUMENT_MODELS.get(tool_name)
        else:
            metadata = getattr(tool, "meta", None)
            tool_name = (
                getattr(tool, "name", None)
                or getattr(metadata, "name", None)
                or "<unknown>"
            )
            schema = getattr(tool, "input_schema", None)
            model = getattr(tool, "input_model", None) or TOOL_ARGUMENT_MODELS.get(tool_name)

        if not isinstance(tool_name, str) or not tool_name:
            tool_name = "<unknown>"
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            model = None
        if not isinstance(schema, dict):
            schema = None
        return tool_name, schema, model

    @staticmethod
    def _pydantic_error(tool_name: str, exc: PydanticValidationError) -> StructuredError:
        issues: list[dict[str, str]] = []
        for error in exc.errors(include_url=False, include_context=False)[:8]:
            issues.append({
                "path": _json_path(error.get("loc", ())),
                "keyword": str(error.get("type", "value_error")),
                "message": _pydantic_message(error),
            })

        first = issues[0] if issues else {"path": "$", "message": "invalid arguments"}
        path = first["path"]
        hint = f"Correct '{path}' and retry." if path != "$" else "Correct the tool arguments and retry."
        return StructuredError(
            code=ErrorCode.INVALID_TOOL_ARGUMENTS,
            message=f"Invalid arguments for tool '{tool_name}'.",
            retryable=False,
            hint=hint,
            details={"tool": tool_name, "validation_errors": issues},
        )


def tool_input_validation_guard(
    validator: ToolInputValidator,
    tool_name: str,
):
    
    def decorator(handler: Callable[..., Any]):
        signature = inspect.signature(handler)

        def validate_arguments(args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
            try:
                bound = signature.bind(*args, **kwargs)
            except TypeError:
                error = StructuredError(
                    code=ErrorCode.INVALID_TOOL_ARGUMENTS,
                    message=f"Invalid arguments for tool '{tool_name}'.",
                    retryable=False,
                    hint="Supply only the documented arguments and include all required fields.",
                    details={"tool": tool_name, "reason": "argument_binding_failed"},
                )
                _raise_tool_validation_error(error)

            error = validator.validate(tool_name, dict(bound.arguments))
            if error is not None:
                _raise_tool_validation_error(error)

        if inspect.iscoroutinefunction(handler):
            @wraps(handler)
            async def async_wrapper(*args, **kwargs):
                validate_arguments(args, kwargs)
                return await handler(*args, **kwargs)
            return async_wrapper

        @wraps(handler)
        def sync_wrapper(*args, **kwargs):
            validate_arguments(args, kwargs)
            return handler(*args, **kwargs)
        return sync_wrapper

    return decorator


def _raise_tool_validation_error(error: StructuredError) -> None:
    message = error.message
    if error.hint:
        message = f"{message} {error.hint}"

    try:
        from mcp.server.mcpserver.exceptions import ToolError
    except ImportError:
        raise ToolInputValidationException(error) from None
    raise ToolError(message)


def _json_path(path: Any) -> str:
    parts = [str(part) for part in path]
    
    for index, part in enumerate(parts[1:], start=1):
        if part.startswith(("constrained-", "int", "float")):
            parts = parts[:index]
            break
    return ".".join(parts) if parts else "$"


def _pydantic_message(error: Mapping[str, Any]) -> str:
    error_type = str(error.get("type", ""))
    message = str(error.get("msg", "invalid value"))
    
    if error_type == "missing":
        return "field is required"
    if error_type == "extra_forbidden":
        return "unexpected field is not allowed"
    if error_type in {"int_type", "float_type", "int_parsing", "float_parsing"}:
        return "value has the wrong type"
    return message


def _json_schema_message(error: Any) -> str:
    keyword = error.validator
    if keyword == "required":
        missing = [key for key in error.validator_value if key not in error.instance]
        return "missing required field(s): " + ", ".join(missing)
    if keyword == "additionalProperties":
        return "unexpected field is not allowed"
    if keyword == "type":
        expected = error.validator_value
        if isinstance(expected, list):
            expected = " or ".join(str(item) for item in expected)
        return f"expected type {expected}"
    if keyword in {"minimum", "exclusiveMinimum"}:
        return f"value must be { 'greater than or equal to' if keyword == 'minimum' else 'greater than' } {error.validator_value}"
    if keyword in {"maximum", "exclusiveMaximum"}:
        return f"value must be { 'less than or equal to' if keyword == 'maximum' else 'less than' } {error.validator_value}"
    if keyword == "enum":
        return "value is not one of the permitted options"
    if keyword == "minLength":
        return f"string must contain at least {error.validator_value} character(s)"
    if keyword == "maxLength":
        return f"string must contain no more than {error.validator_value} character(s)"
    return "value does not satisfy the input schema"
