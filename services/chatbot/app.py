import streamlit as st
import sys
import os
import datetime
from streamlit_autorefresh import st_autorefresh

# Ensure the root directory is in the sys.path so we can import shared modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Disable DB pooling for Streamlit to prevent "Future attached to different loop" errors
os.environ["DISABLE_DB_POOL"] = "1"

from services.chatbot.agent import get_chatbot_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

import asyncio
from sqlalchemy import select
from shared.db.session import get_db_context
from shared.db.models import PullRequest, Finding

st.set_page_config(page_title="AI PR Reviewer", page_icon="🤖", layout="wide")

# Run auto-refresh every 10 seconds
count = st_autorefresh(interval=10000, limit=None, key="pr_autorefresh")

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

def get_recent_prs(repo=None):
    async def _run():
        async with get_db_context() as db:
            stmt = select(PullRequest).order_by(PullRequest.created_at.desc()).limit(10)
            if repo:
                stmt = stmt.where(PullRequest.repo_full_name == repo)
            result = await db.execute(stmt)
            return result.scalars().all()
    try:
        return asyncio.run(_run())
    except Exception:
        return []

def get_findings_for_pr(pr_id):
    async def _run():
        async with get_db_context() as db:
            stmt = select(Finding).where(Finding.pr_id == pr_id)
            result = await db.execute(stmt)
            return result.scalars().all()
    try:
        return asyncio.run(_run())
    except Exception:
        return []

def check_for_new_prs():
    # If no last_seen_time, set it to now
    if "last_seen_pr_time" not in st.session_state:
        st.session_state.last_seen_pr_time = datetime.datetime.utcnow()
        return

    async def _run():
        async with get_db_context() as db:
            stmt = select(PullRequest).where(PullRequest.created_at > st.session_state.last_seen_pr_time).order_by(PullRequest.created_at.asc())
            result = await db.execute(stmt)
            return result.scalars().all()
    try:
        new_prs = asyncio.run(_run())
        for pr in new_prs:
            st.toast(f"🔔 **New PR #{pr.pr_number}** raised in `{pr.repo_full_name}`!", icon="🚀")
            st.session_state.last_seen_pr_time = pr.created_at
    except Exception as e:
        pass

# Check notifications
check_for_new_prs()

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

st.title("🤖 AI PR Reviewer")

# Initialize session state for chat history and agent
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "agent_executor" not in st.session_state:
    st.session_state.agent_executor = get_chatbot_agent()

# Tabs layout
tab_dashboard, tab_fix, tab_chat = st.tabs(["📊 Dashboard", "🛠️ Fix Center", "💬 AI Chat"])

with tab_dashboard:
    st.header("📊 PR Dashboard")
    st.markdown(f"**Live Feed of Pull Requests** {'for ' + active_repo if active_repo else '(All Repositories)'}")
    
    recent_prs = get_recent_prs(active_repo)
    if recent_prs:
        import pandas as pd
        df = pd.DataFrame([
            {
                "Repo": pr.repo_full_name,
                "PR #": pr.pr_number,
                "Author": pr.author,
                "Status": pr.status.value if hasattr(pr.status, 'value') else pr.status,
                "Created At": pr.created_at.strftime("%Y-%m-%d %H:%M:%S")
            } for pr in recent_prs
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No pull requests found.")

with tab_fix:
    st.header("🛠️ Fix Center")
    st.markdown("Select a PR to analyze and resolve AI reviewer findings.")
    
    if recent_prs:
        pr_options = {f"#{pr.pr_number} in {pr.repo_full_name}": pr for pr in recent_prs}
        selected_pr_name = st.selectbox("Select PR to fix", list(pr_options.keys()))
        selected_pr = pr_options[selected_pr_name]
        
        findings = get_findings_for_pr(selected_pr.id)
        if findings:
            st.warning(f"Found {len(findings)} issues in this PR.")
            for f in findings:
                with st.expander(f"{f.severity.value.upper() if hasattr(f.severity, 'value') else str(f.severity).upper()} in {f.file_path}"):
                    st.markdown(f"**Message:** {f.message}")
                    if f.suggestion:
                        st.markdown(f"**Suggestion:** {f.suggestion}")
            
            if st.button("🤖 Generate AI Fix Instructions", key="btn_fix"):
                with st.spinner("Generating fix steps..."):
                    findings_data = [{"file": f.file_path, "message": f.message, "suggestion": f.suggestion} for f in findings]
                    prompt = f"The following findings were detected on PR #{selected_pr.pr_number} in {selected_pr.repo_full_name}. Please provide a step-by-step guide to fix them:\n\n{findings_data}"
                    
                    response = st.session_state.agent_executor.invoke({"messages": [HumanMessage(content=prompt)]})
                    st.markdown("### AI Fix Steps")
                    st.markdown(response["messages"][-1].content)
        else:
            st.success("No findings recorded for this PR. Looks good! 🎉")
    else:
        st.info("No recent PRs available.")

def get_clean_history(history):
    clean = []
    for msg in history:
        if isinstance(msg, HumanMessage):
            clean.append(msg)
        elif isinstance(msg, AIMessage) and msg.content:
            clean.append(AIMessage(content=msg.content))
    return clean

with tab_chat:
    st.header("💬 AI Chat")
    
    # Display chat history
    for msg in st.session_state.chat_history:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user"):
                st.markdown(msg.content)
        elif isinstance(msg, AIMessage) and msg.content:
            with st.chat_message("assistant"):
                st.markdown(msg.content)

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

