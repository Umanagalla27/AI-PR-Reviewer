import json
from openai import AsyncOpenAI
from langfuse import Langfuse
from shared.config.settings import settings

# Initialize Langfuse
langfuse = Langfuse(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY,
    host=settings.LANGFUSE_HOST,
)

client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_API_BASE if settings.OPENAI_API_BASE else None,
)


async def call_llm(
    agent_name: str, system_prompt: str, user_content: str, trace_id: str
) -> dict:
    """Helper to call LLM and log generation to Langfuse."""

    # Optional: fetch trace from langfuse if trace_id exists
    # Normally we would just log the generation with the trace_id

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        response = await client.chat.completions.create(  # type: ignore
            model=settings.OPENAI_MODEL,
            messages=messages,  # type: ignore
            temperature=0.1,
            max_tokens=1024,
            response_format={"type": "json_object"},
        )

        result_str = response.choices[0].message.content
        usage = response.usage

        if trace_id:
            langfuse.generation(  # type: ignore
                trace_id=trace_id,
                name=f"{agent_name}_review",
                model=settings.OPENAI_MODEL,
                input=messages,
                output=result_str,
                usage={"input": usage.prompt_tokens, "output": usage.completion_tokens},
            )

        return json.loads(result_str)
    except Exception:
        return {"findings": []}
