# Template source: python-telegram-bot + openai | Difficulty: medium | Niche: bots
import openai
import asyncio
from config import LLM_API_KEY, LLM_MODEL, LLM_PROVIDER

client = openai.AsyncOpenAI(api_key=LLM_API_KEY)

async def chat(messages: list[dict], stream: bool = True):
    for attempt in range(3):
        try:
            if stream:
                async with client.chat.completions.stream(
                    model=LLM_MODEL,
                    messages=messages
                ) as stream_ctx:
                    async for chunk in stream_ctx:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            yield delta
            else:
                resp = await client.chat.completions.create(model=LLM_MODEL, messages=messages)
                yield resp.choices[0].message.content
            return
        except Exception as e:
            if attempt == 2:
                yield f"Error: {e}"
            await asyncio.sleep(2 ** attempt)
