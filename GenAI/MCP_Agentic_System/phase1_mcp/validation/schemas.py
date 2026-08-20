from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate

from errors.framework import ErrorCode, StructuredError

class ToolInputValidator:
    def validate(self, tool, arguments):

        try:
            validate(
                instance=arguments,
                schema=tool.input_schema
            )

        except JsonSchemaValidationError as exc:
            return {
                "valid":  False,
                "error": {
                    "code": "INVALID_TOOL_ARGUMENTS",
                    "message": str(exc),
                    "retryable": False
                }
            }

        return {
            "valid": True,
            "arguments": arguments
        }
            