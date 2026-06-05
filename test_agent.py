import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))
import asyncio
from services.chatbot.agent import get_chatbot_agent
from langchain_core.messages import HumanMessage

async def main():
    os.environ["DISABLE_DB_POOL"] = "1"
    agent_executor = get_chatbot_agent()
    print("Agent executor created")
    
    messages = [HumanMessage(content="What are the most recent pull requests for Umanagalla27/AI-PR-Reviewer?")]
    
    try:
        async for chunk in agent_executor.astream({"messages": messages}):
            print("--- CHUNK ---")
            print(chunk)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
