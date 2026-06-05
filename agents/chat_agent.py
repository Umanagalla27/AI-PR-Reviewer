import structlog
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from shared.config.settings import get_settings
from agents.prompts import CHAT_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)

async def run_chat_agent(
    diff: str,
    recent_comments: list[dict],
    new_comment: str,
) -> str:
    """
    Given the PR diff, previous conversation history, and the new comment,
    generates a helpful response from the AI Reviewer.
    """
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=0.2,
        api_key=settings.OPENAI_API_KEY, # type: ignore
        max_tokens=1024,
        base_url=settings.OPENAI_API_BASE if settings.OPENAI_API_BASE else None, # type: ignore
    )

    from langchain_core.messages import BaseMessage
    messages: list[BaseMessage] = [
        SystemMessage(content=CHAT_SYSTEM_PROMPT),
    ]

    # Add the PR diff for context
    messages.append(
        HumanMessage(content=f"Here is the Pull Request Diff for context:\n```diff\n{diff}\n```")
    )

    # Add conversational memory
    for comment in recent_comments:
        author = comment.get("user", {}).get("login", "unknown")
        body = comment.get("body", "")
        if "ai-pr-reviewer" in author.lower() or "[bot]" in author.lower():
            messages.append(AIMessage(content=body))
        else:
            messages.append(HumanMessage(content=f"@{author}: {body}"))

    # Add the newest comment
    messages.append(HumanMessage(content=f"New Comment:\n{new_comment}"))

    logger.info("invoking_chat_agent", messages_count=len(messages))
    
    try:
        response = await llm.ainvoke(messages)
        return str(response.content)
    except Exception as e:
        logger.error("chat_agent_failed", error=str(e))
        return "I encountered an error trying to process your request. Please try again later."
