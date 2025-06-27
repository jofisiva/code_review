"""
LangGraph agent definitions for code review.
"""
from langchain.graph.graph import END, StateGraph
from langchain.graph.graph_document import GraphDocument

from agents.reviewer_agent import ReviewerAgent
from agents.coder_agent import CoderAgent

def create_file_review_graph(use_local_llm=False):
    """Create a graph for file review.
    
    Args:
        use_local_llm: Whether to use a local LLM instead of OpenAI
        
    Returns:
        StateGraph for file review
    """
    # Create agents
    reviewer_agent = ReviewerAgent(use_local_llm=use_local_llm)
    
    # Create graph
    workflow = StateGraph(GraphDocument)
    
    # Add nodes
    workflow.add_node("reviewer", reviewer_agent.review_file)
    
    # Add edges
    workflow.add_edge("reviewer", END)
    
    # Set entry point
    workflow.set_entry_point("reviewer")
    
    # Compile the graph
    return workflow.compile()

def create_iterative_improvement_graph(use_local_llm=False):
    """Create a graph for iterative improvement.
    
    Args:
        use_local_llm: Whether to use a local LLM instead of OpenAI
        
    Returns:
        StateGraph for iterative improvement
    """
    # Create agents
    reviewer_agent = ReviewerAgent(use_local_llm=use_local_llm)
    coder_agent = CoderAgent(use_local_llm=use_local_llm)
    
    # Create graph
    workflow = StateGraph(GraphDocument)
    
    # Add nodes
    workflow.add_node("reviewer", reviewer_agent.review_file)
    workflow.add_node("coder", coder_agent.apply_suggestions)
    
    # Define conditional routing
    def has_suggestions(state):
        reviewer_analysis = state["reviewer_analysis"]
        return "coder" if "No suggestions" not in reviewer_analysis else END
    
    # Add edges
    workflow.add_conditional_edges("reviewer", has_suggestions)
    workflow.add_edge("coder", END)
    
    # Set entry point
    workflow.set_entry_point("reviewer")
    
    # Compile the graph
    return workflow.compile()
