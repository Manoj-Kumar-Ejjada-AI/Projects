from llm import call_llm
import json
from validation.schemas import ToolInputValidator
from errors.framework import ErrorCode, StructuredError

class Agent:
    def __init__(self, llm, model: str, tool_executor, tool_registry, max_iterations: int = 5):
        self.llm = llm
        self.model = model
        # self.mcp_client = mcp_client
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
        self.max_iterations = max_iterations

        self.validate = ToolInputValidator()

    async def run(self, user_message):

        messages = [{
            "role": "user",
            "content": user_message
        }]

        tools = self.tool_registry.get_llm_tools()
        # print("Tools: ", tools )

        for iteration in range(self.max_iterations):

            response = await call_llm(self.llm,
                                    self.model,
                                    messages,
                                    tools)

            message = response.choices[0].message
            # print("message:", message)

            if not message.tool_calls:
                return message.content

            messages.append(message)


            for tool_call in message.tool_calls:

                tool_name = tool_call.function.name

                if not self.tool_registry.has_tool(tool_name):
                    error = StructuredError(
                        code = ErrorCode.UNKNOWN_TOOL,
                        message= f"Tool '{tool_name}' does not exist",
                        retryable= False
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                                        "error":error.to_dict()
                                            })
                    })

                    continue
                try:

                    tool_args = json.loads(
                        tool_call.function.arguments
                        )

                except json.JSONDecodeError as exc:
                    error = StructuredError(
                        code=ErrorCode.INVLAID_JSON,
                        message= "Tool arguments are not valid JSON",
                        retryable= False
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps({
                            "error": error.to_dict()
                        })
                    })

                    continue

                tool = self.tool_registry.get_tool(tool_name)

                validation = self.validate.validate(tool, tool_args)

                if validation is not None:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(validation)
                    })

                    continue

                # tool_result = await self.mcp_client.call_tool(
                #     tool_name,
                #     tool_args
                # )
                tool_result, tool_error = await self.tool_executor.execute(
                    tool_name,
                    tool_args
                )

                if tool_error:
                    tool_result = json.dumps(tool_error.to_dict())

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    }
                )

            # print("tool result: ", tool_result)

        raise RuntimeError(
            f"Agent exceeded maximum iterations: "
            f"{self.max_iterations}"
        )