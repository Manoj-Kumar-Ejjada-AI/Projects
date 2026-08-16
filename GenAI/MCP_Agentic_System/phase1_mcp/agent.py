from llm import call_llm
import json

class Agent:
    def __init__(self, llm, model, mcp_client, tool_registry):
        self.llm = llm
        self.model = model
        self.mcp_client = mcp_client
        self.tool_registry = tool_registry

    async def run(self, user_message):

        messages = [{
            "role": "user",
            "content": user_message
        }]

        tools = self.tool_registry.get_llm_tools()

        while True:

            response = await call_llm(self.llm,
                                    self.model,
                                    messages,
                                    tools)

            message = response.choices[0].message

            if not message.tool_calls:
                return message.content

            messages.append(message)

            for tool_call in message.tool_calls:

                tool_name = tool_call.function.name

                tool_args = json.loads(tool_call.function.arguments)

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