from typing import Dict, List, Annotated, TypedDict, Literal, Union, Any
import json
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from langchain.tools import Tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain import hub
from langchain.prompts import PromptTemplate
from config import OPENAI_MODEL_CODER, OPENAI_MODEL_REVIEWER, OPENAI_API_KEY

# Define the state for our graph
class FileReviewState(TypedDict):
    file_path: str
    old_content: str
    new_content: str
    change_type: str
    coder_analysis: str
    reviewer_analysis: str
    final_review: str
    status: Literal["analyzing", "reviewing", "completed"]

# Define the state for our overall review process
class PRReviewState(TypedDict):
    pull_request_id: int
    title: str
    repository: str
    source_branch: str
    target_branch: str
    created_by: str
    files: List[Dict[str, Any]]
    current_file_index: int
    summary_review: str
    status: Literal["fetching_files", "reviewing_files", "summarizing", "completed"]

# Coder Agent Node
def create_coder_agent():
    """Create a Coder agent that analyzes code changes."""
    llm = ChatOpenAI(
        model=OPENAI_MODEL_CODER,
        temperature=0.3,
        api_key=OPENAI_API_KEY
    )
    
    coder_prompt = """
    You are an expert software developer tasked with explaining code changes in a pull request.
    Your job is to:
    1. Understand the changes made in the code
    2. Explain the purpose and functionality of the changes
    3. Identify any potential issues or improvements
    4. Provide context about why these changes might have been made
    
    Focus on being clear, concise, and technically accurate. Explain the changes as if you were
    the developer who made them, providing insight into your thought process.
    
    File path: {file_path}
    Change type: {change_type}
    
    OLD VERSION:
    ```
    {old_content}
    ```
    
    NEW VERSION:
    ```
    {new_content}
    ```
    
    Please explain:
    1. What changes were made to the file?
    2. What is the purpose of these changes?
    3. Are there any potential issues or improvements you can identify?
    
    {format_instructions}
    """
    
    prompt = PromptTemplate(
        template=coder_prompt,
        input_variables=["file_path", "old_content", "new_content", "change_type"],
        partial_variables={"format_instructions": "Format your response as markdown."}
    )
    
    def analyze_code_changes(state: FileReviewState) -> FileReviewState:
        """Analyze code changes using the Coder agent."""
        # Format the prompt with the file information
        formatted_prompt = prompt.format(
            file_path=state["file_path"],
            old_content=state["old_content"] if state["old_content"] else "This is a new file.",
            new_content=state["new_content"],
            change_type=state["change_type"]
        )
        
        # Get response from LLM
        response = llm.invoke(formatted_prompt)
        
        # Update the state with the coder's analysis
        state["coder_analysis"] = response.content
        state["status"] = "reviewing"
        
        return state
    
    return analyze_code_changes

# Reviewer Agent Node
def create_reviewer_agent():
    """Create a Reviewer agent that reviews code changes."""
    llm = ChatOpenAI(
        model=OPENAI_MODEL_REVIEWER,
        temperature=0.4,
        api_key=OPENAI_API_KEY
    )
    
    reviewer_prompt = """
    You are an expert code reviewer with years of experience in software development.
    Your job is to:
    1. Review code changes critically and thoroughly
    2. Identify potential bugs, security issues, and performance problems
    3. Suggest improvements to code quality, readability, and maintainability
    4. Ensure the code follows best practices and design patterns
    5. Provide constructive feedback that helps the developer improve
    
    Be thorough but fair in your assessment. Always provide specific suggestions
    for improvement rather than just pointing out problems.
    
    File path: {file_path}
    Change type: {change_type}
    
    OLD VERSION:
    ```
    {old_content}
    ```
    
    NEW VERSION:
    ```
    {new_content}
    ```
    
    The developer explains these changes as follows:
    {coder_analysis}
    
    Please provide a thorough code review addressing:
    1. Code quality and readability
    2. Potential bugs or edge cases
    3. Security concerns
    4. Performance considerations
    5. Adherence to best practices
    6. Specific suggestions for improvement
    
    {format_instructions}
    """
    
    prompt = PromptTemplate(
        template=reviewer_prompt,
        input_variables=["file_path", "old_content", "new_content", "change_type", "coder_analysis"],
        partial_variables={"format_instructions": "Format your review as markdown with sections for different categories of feedback."}
    )
    
    def review_code_changes(state: FileReviewState) -> FileReviewState:
        """Review code changes using the Reviewer agent."""
        # Format the prompt with the file information and coder analysis
        formatted_prompt = prompt.format(
            file_path=state["file_path"],
            old_content=state["old_content"] if state["old_content"] else "This is a new file.",
            new_content=state["new_content"],
            change_type=state["change_type"],
            coder_analysis=state["coder_analysis"]
        )
        
        # Get response from LLM
        response = llm.invoke(formatted_prompt)
        
        # Update the state with the reviewer's analysis
        state["reviewer_analysis"] = response.content
        state["status"] = "completed"
        
        return state
    
    return review_code_changes

# Summary Agent Node
def create_summary_agent():
    """Create a Summary agent that provides an overall review of all files."""
    llm = ChatOpenAI(
        model=OPENAI_MODEL_REVIEWER,
        temperature=0.4,
        api_key=OPENAI_API_KEY
    )
    
    summary_prompt = """
    You are tasked with providing an overall summary review of a pull request based on the individual file reviews.
    
    Pull Request: #{pull_request_id} - {title}
    Repository: {repository}
    Source Branch: {source_branch}
    Target Branch: {target_branch}
    Created By: {created_by}
    
    Here are the file reviews:
    
    {file_reviews}
    
    Please provide:
    1. A summary of the key findings across all files
    2. Overall assessment of the code quality
    3. Major concerns that should be addressed before merging
    4. Positive aspects of the changes
    5. A final recommendation (Approve, Request Changes, or Comment)
    
    {format_instructions}
    """
    
    prompt = PromptTemplate(
        template=summary_prompt,
        input_variables=["pull_request_id", "title", "repository", "source_branch", "target_branch", "created_by", "file_reviews"],
        partial_variables={"format_instructions": "Format your summary as markdown."}
    )
    
    def generate_summary(state: PRReviewState) -> PRReviewState:
        """Generate a summary review of all files."""
        # Prepare file reviews for the prompt
        file_reviews = []
        for file_info in state["files"]:
            if "reviewer_analysis" in file_info:
                file_reviews.append(f"## {file_info['path']}\n\n{file_info['reviewer_analysis']}\n\n")
        
        # Format the prompt with the PR information and file reviews
        formatted_prompt = prompt.format(
            pull_request_id=state["pull_request_id"],
            title=state["title"],
            repository=state["repository"],
            source_branch=state["source_branch"],
            target_branch=state["target_branch"],
            created_by=state["created_by"],
            file_reviews="\n".join(file_reviews)
        )
        
        # Get response from LLM
        response = llm.invoke(formatted_prompt)
        
        # Update the state with the summary review
        state["summary_review"] = response.content
        state["status"] = "completed"
        
        return state
    
    return generate_summary

# Create the file review graph
def create_file_review_graph():
    """Create a graph for reviewing a single file."""
    # Create the graph
    graph = StateGraph(FileReviewState)
    
    # Add nodes
    graph.add_node("coder", create_coder_agent())
    graph.add_node("reviewer", create_reviewer_agent())
    
    # Add edges
    graph.add_edge("coder", "reviewer")
    graph.add_edge("reviewer", END)
    
    # Set the entry point
    graph.set_entry_point("coder")
    
    # Compile the graph
    return graph.compile()

# Create the PR review graph
def create_pr_review_graph():
    """Create a graph for reviewing an entire pull request."""
    # Create the graph
    graph = StateGraph(PRReviewState)
    
    # Define the file review node
    def process_file(state: PRReviewState) -> PRReviewState:
        """Process the current file using the file review graph."""
        # Check if we've processed all files
        if state["current_file_index"] >= len(state["files"]):
            state["status"] = "summarizing"
            return state
        
        # Get the current file
        current_file = state["files"][state["current_file_index"]]
        
        # Create a file review state
        file_state = FileReviewState(
            file_path=current_file["path"],
            old_content=current_file.get("old_content", ""),
            new_content=current_file["new_content"],
            change_type=current_file["change_type"],
            coder_analysis="",
            reviewer_analysis="",
            final_review="",
            status="analyzing"
        )
        
        # Process the file through the file review graph
        file_review_graph = create_file_review_graph()
        final_file_state = file_review_graph.invoke(file_state)
        
        # Update the file in the PR state
        state["files"][state["current_file_index"]]["coder_analysis"] = final_file_state["coder_analysis"]
        state["files"][state["current_file_index"]]["reviewer_analysis"] = final_file_state["reviewer_analysis"]
        
        # Move to the next file
        state["current_file_index"] += 1
        
        return state
    
    # Add nodes
    graph.add_node("process_file", process_file)
    graph.add_node("summarize", create_summary_agent())
    
    # Add conditional edges
    def should_continue_processing(state: PRReviewState) -> str:
        """Determine if we should continue processing files or move to summarizing."""
        if state["status"] == "summarizing":
            return "summarize"
        else:
            return "process_file"
    
    # Add edges
    graph.add_conditional_edges(
        "process_file",
        should_continue_processing,
        {
            "process_file": "process_file",
            "summarize": "summarize"
        }
    )
    graph.add_edge("summarize", END)
    
    # Set the entry point
    graph.set_entry_point("process_file")
    
    # Compile the graph
    return graph.compile()
