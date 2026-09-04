from dataclasses import dataclass, field
from typing import Any


class ErrorCode:
    UNKNOWN_TOOL = "UNKNOWN_TOOL"
    INVLAID_JSON = "INVALID_JSON"
    INVALID_TOOL_ARGUMENTS = "INVALID_TOOL_ARGUMENTS"

    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"

    TOOL_TIMEOUT = "TOOL_TIMEOUT"
    EXECUTION_DEADLINE_EXCEEDED = "EXECUTION_DEADLINE_EXCEEDED"

    INTERNAL_ERROR = "INTERNAL_ERROR"

    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    RATE_LIMITED = "RATE_LIMITED"

@dataclass
class StructuredError:
    code: str
    message: str
    retryable: bool = False
    hint: str | None = None
    counts_toward_circuit_breaker: bool = False
    details: dict[str, Any] = field(default_factory=dict)


    def to_dict(self):

        payload = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "counts_toward_circuit_breaker": self.counts_toward_circuit_breaker
        }

        if self.hint is not None:
            payload["hint"] = self.hint

        if self.details:
            payload["details"] = self.details

        return payload

class ToolExecutionException(Exception):
    def __init__(self, error: StructuredError):
        self.error = error
        super().__init__(error.message)