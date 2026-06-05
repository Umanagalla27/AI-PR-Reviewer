import streamlit as st
import sys
import os

# Ensure the root directory is in the sys.path so we can import shared modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Disable DB pooling for Streamlit to prevent "Future attached to different loop" errors
os.environ["DISABLE_DB_POOL"] = "1"

from services.chatbot.agent import get_chatbot_agent
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

st.set_page_config(page_title="AI PR Reviewer - Chatbot", page_icon="🤖", layout="wide")

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

# Chat input
if prompt := st.chat_input("Ask a question about your repositories... (e.g. 'What are the recent PRs for Umanagalla27/AI-PR-Reviewer?')"):
    # Add user message to state and display
    user_msg = HumanMessage(content=prompt)
    st.session_state.chat_history.append(user_msg)
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # Pass the entire chat history (including previous tool calls) to avoid OpenAI 400 errors
            response = st.session_state.agent_executor.invoke({"messages": st.session_state.chat_history})
            
            # The entire state is now updated, overwrite chat history with the full trace
            st.session_state.chat_history = response["messages"]
            
            # The final response is the last message's content
            answer = st.session_state.chat_history[-1].content
            if answer:
                st.markdown(answer)
