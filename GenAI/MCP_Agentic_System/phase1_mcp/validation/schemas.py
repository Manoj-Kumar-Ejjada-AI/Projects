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
            return StructuredError(
                code = ErrorCode.INVALID_TOOL_ARGUMENTS,
                message=exc.message,
                details=str(exc)
            )

        return None
            