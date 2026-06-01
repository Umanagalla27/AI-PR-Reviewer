from langgraph.graph import StateGraph, START, END
from agents.state import ReviewState
from agents.static_agent import static_agent
from agents.security_agent import security_agent
from agents.style_agent import style_agent
from agents.architecture_agent import architecture_agent
from agents.merger import merger_node

def create_review_graph():
    """Builds and compiles the LangGraph StateGraph for PR review."""
    
    workflow = StateGraph(ReviewState)
    
    # Add nodes
    workflow.add_node("static", static_agent)
    workflow.add_node("security", security_agent)
    workflow.add_node("style", style_agent)
    workflow.add_node("architecture", architecture_agent)
    workflow.add_node("merger", merger_node)
    
    # Add parallel edges from START to all agents
    workflow.add_edge(START, "static")
    workflow.add_edge(START, "security")
    workflow.add_edge(START, "style")
    workflow.add_edge(START, "architecture")
    
    # Add edges from all agents to merger
    workflow.add_edge("static", "merger")
    workflow.add_edge("security", "merger")
    workflow.add_edge("style", "merger")
    workflow.add_edge("architecture", "merger")
    
    # End workflow after merger
    workflow.add_edge("merger", END)
    
    return workflow.compile()

# Singleton graph instance
review_graph = create_review_graph()
