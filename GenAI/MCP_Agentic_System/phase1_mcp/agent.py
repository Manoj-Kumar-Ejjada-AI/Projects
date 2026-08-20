from llm import call_llm
import json
from validation.schemas import ToolInputValidator

class Agent:
    def __init__(self, llm, model: str, mcp_client, tool_registry, max_iterations: int = 5):
        self.llm = llm
        self.model = model
        self.mcp_client = mcp_client
        self.tool_registry = tool_registry
        self.max_iterations = max_iterations

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
                    tool_result = {
                        "error": {
                            "code": "UNKNOWN_TOOL",
                            "message": (
                                f"Tool {tool_name} doesn't exist"
                            ),
                            "retryable": False
                        }
                    }

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result)
                    })

                    continue
                try:

                    tool_args = json.loads(
                        tool_call.function.arguments
                        )

                except json.JSONDecodeError as exc:
                    tool_result = {
                        "error": {
                            "code": "INVALID_TOOL_ARGUMENTS",
                            "message": (
                                "The tool arguments returned "
                                f" by the LLM are not valid JSON {exc}"
                            ),
                            "retyrable": False
                        }
                    }

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_result)
                    })

                    continue

                tool = self.tool_registry.get_tool(tool_name)

                validation = ToolInputValidator.validate(tool, tool_args)

                if not validation.get("valid"):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(validation)
                    })

                    continue

                tool_result = await self.mcp_client.call_tool(
                    tool_name,
                    tool_args
                )

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