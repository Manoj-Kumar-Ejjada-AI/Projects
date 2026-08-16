from openai import AsyncAzureOpenAI


async def call_llm(llm, model, messages: list, tools: list):
    response = await llm.chat.completions.create(
        model = model,
        messages = messages,
        tools = tools
    )
    return response