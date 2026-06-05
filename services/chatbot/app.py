import streamlit as st
import sys
import os

# Ensure the root directory is in the sys.path so we can import shared modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Disable DB pooling for Streamlit to prevent "Future attached to different loop" errors
os.environ["DISABLE_DB_POOL"] = "1"

from services.chatbot.agent import get_chatbot_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

import asyncio
from sqlalchemy import select
from shared.db.session import get_db_context
from shared.db.models import PullRequest

def get_repos():
    async def _run():
        async with get_db_context() as db:
            stmt = select(PullRequest.repo_full_name).distinct()
            result = await db.execute(stmt)
            return result.scalars().all()
    try:
        return asyncio.run(_run())
    except Exception:
        return []

st.set_page_config(page_title="AI PR Reviewer - Chatbot", page_icon="🤖", layout="wide")

with st.sidebar:
    st.header("⚙️ Configuration")
    st.markdown("Select a repository to automatically filter your queries.")
    
    known_repos = get_repos()
    selected_repo = ""
    if known_repos:
        selected_repo = st.selectbox("Select Active Repository", [""] + known_repos)
        
    custom_repo = st.text_input("Or type repository manually", placeholder="owner/repo")
    active_repo = custom_repo if custom_repo else selected_repo
    
    if active_repo:
        st.success(f"Context set to: **{active_repo}**")
    else:
        st.info("No active repository selected. Please specify the repository in your questions.")

st.title("🤖 AI PR Reviewer Chatbot")
st.markdown("Ask me about past pull requests, AI findings, or coding styles I've learned!")

# Initialize session state for chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
    
if "agent_executor" not in st.session_state:
    st.session_state.agent_executor = get_chatbot_agent()

# Display chat history
for msg in st.session_state.chat_history:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.markdown(msg.content)
    elif isinstance(msg, AIMessage) and msg.content:
        with st.chat_message("assistant"):
            st.markdown(msg.content)

def get_clean_history(history):
    clean = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            clean.append(msg)
        elif isinstance(msg, AIMessage) and msg.content:
            clean.append(AIMessage(content=msg.content))
    return clean

# Chat input
if prompt := st.chat_input("Ask a question about your repositories... (e.g. 'What are the recent PRs?')"):
    # Add user message to state and display
    st.session_state.chat_history.append(HumanMessage(content=prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            clean_history = get_clean_history(st.session_state.chat_history[:-1])
            
            # Inject context if a repository is active
            augmented_prompt = prompt
            if active_repo:
                augmented_prompt = f"System Context: The user is currently viewing the repository '{active_repo}'. Please scope your query to this repository unless the user specifies otherwise.\n\nUser Question: {prompt}"
            
            messages = clean_history + [HumanMessage(content=augmented_prompt)]
            
            response = st.session_state.agent_executor.invoke({"messages": messages})
            
            # The final response is the last message's content
            answer = response["messages"][-1].content
            if answer:
                st.markdown(answer)
                st.session_state.chat_history.append(AIMessage(content=answer))
