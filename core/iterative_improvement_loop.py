"""
Iterative improvement loop for code review and automated fixes.
"""
import os
import re
import json
import logging
from datetime import datetime
from langchain.graph.graph import END, StateGraph
from langchain.graph.graph_document import GraphDocument

from agents.reviewer_agent import ReviewerAgent
from agents.coder_agent import CoderAgent
from azure_devops.client import AzureDevOpsIterationClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IterativeImprovementLoop:
    """
    Implements an iterative feedback loop where the Reviewer Agent provides code suggestions,
    and the Coder Agent applies those suggestions until all review comments are resolved.
    
    Key features:
    1. Automated PR Comment Integration:
       - Posts summary comments for each file review iteration
       - Posts individual issue comments on specific code lines
       - Updates existing threads rather than creating duplicates
       - Automatically marks threads as "fixed" when issues are resolved
       - Adds confirmation comments when issues are fixed
       
    2. Issue Tracking and Resolution:
       - Extracts issues and their line numbers from reviewer analysis
       - Tracks issues across iterations to identify which ones are resolved
       - Updates PR thread statuses based on issue resolution
       - Provides detailed logging of thread status changes
       
    3. Iterative Improvement Process:
       - Continues until all issues are resolved or max iterations reached
       - Saves detailed records of each iteration for analysis
       - Applies code suggestions automatically using the Coder Agent
       
    This system enhances developer awareness by posting both summary comments and
    individual line-specific issue comments directly on Azure DevOps PR threads.
    """
    
    def __init__(self, use_local_llm: bool = False):
        """Initialize the iterative improvement loop.
        
        Args:
            use_local_llm: Whether to use a local LLM instead of OpenAI
        """
        self.use_local_llm = use_local_llm
        self.reviewer_agent = ReviewerAgent(use_local_llm=use_local_llm)
        self.coder_agent = CoderAgent(use_local_llm=use_local_llm)
        self.azure_client = AzureDevOpsIterationClient()
        self.file_review_graph = create_file_review_graph(use_local_llm=self.use_local_llm)
        
    def improve_code(self, pull_request_id, file_path, old_content, new_content, max_iterations=3, output_dir="reviews/improvements", post_comments=True):
        """Run an iterative improvement loop on a file with PR comment integration.
        
        This method orchestrates the full iterative improvement process:
        1. The reviewer agent analyzes the code and identifies issues
        2. Comments are posted to the PR (if post_comments=True)
        3. Code suggestions are extracted and applied by the coder agent
        4. The process repeats until all issues are resolved or max_iterations is reached
        5. Thread statuses are updated as issues are resolved
        
        The PR comment integration features include:
        - Posting summary comments for each file review iteration
        - Posting individual issue comments on specific code lines
        - Updating existing threads rather than creating duplicates
        - Automatically marking threads as "fixed" when issues are resolved
        - Adding confirmation comments when issues are fixed
        - Tracking thread IDs across iterations for status updates
        
        Args:
            pull_request_id: The ID of the pull request
            file_path: Path to the file being improved
            old_content: Original content of the file (from previous iteration)
            new_content: Current content of the file to be reviewed
            max_iterations: Maximum number of improvement iterations to perform
            output_dir: Directory to save iteration results as JSON files
            post_comments: Whether to post comments directly to the PR threads
            
        Returns:
            Dictionary containing the complete improvement results including:
            - iterations_completed: Number of iterations performed
            - all_issues_resolved: Whether all issues were resolved
            - iterations: List of all iteration results
            - final_content: The final improved content
            - threads: List of PR thread IDs created (if post_comments=True)
        """
        print(f"Starting iterative improvement for {file_path}")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get repository ID from pull request
        pr_details = self.azure_client.get_pull_request(pull_request_id)
        repository_id = pr_details['repository']['id']
        
        # Initialize variables
        current_content = new_content
        iterations = []
        all_threads = {}
        previous_issues = []
        
        for iteration in range(1, max_iterations + 1):
            print(f"Iteration {iteration} of {max_iterations}")
            
            # Create file state for the review graph
            file_state = {
                "file_path": file_path,
                "old_content": old_content,
                "new_content": current_content
            }
            
            # Run the file review graph
            final_state = self.file_review_graph.invoke(file_state)
            reviewer_analysis = final_state["reviewer_analysis"]
            
            # Post comments to PR if enabled
            iteration_threads = {}
            if post_comments:
                iteration_threads = self._post_review_comments_to_pr(
                    repository_id, 
                    pull_request_id, 
                    file_path, 
                    reviewer_analysis, 
                    iteration
                )
                all_threads.update(iteration_threads)
            
            # Extract current issues
            current_issues = self._extract_issues(reviewer_analysis)
            
            # Save iteration results
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            iteration_result = {
                "iteration": iteration,
                "file_path": file_path,
                "reviewer_analysis": reviewer_analysis,
                "issues": current_issues,
                "threads": iteration_threads
            }
            iterations.append(iteration_result)
            
            # Save to file
            output_file = os.path.join(output_dir, f"{self._safe_filename(file_path)}_iteration_{iteration}_{timestamp}.json")
            with open(output_file, 'w') as f:
                json.dump(iteration_result, f, indent=2)
            
            # Check if there are any suggestions
            if "No suggestions" in reviewer_analysis or not current_issues:
                print(f"No suggestions found in iteration {iteration}, stopping improvement loop")
                break
            
            # Apply suggestions
            improved_content = self._apply_suggestions(file_path, current_content, reviewer_analysis)
            
            # Check if content changed
            if improved_content == current_content:
                print(f"No changes made in iteration {iteration}, stopping improvement loop")
                break
            
            # Update thread status for resolved issues
            if post_comments and previous_issues:
                # Find resolved issues
                resolved_issues = []
                for prev_issue in previous_issues:
                    # Check if the issue is still present in current issues
                    issue_resolved = True
                    for curr_issue in current_issues:
                        if prev_issue['text'] == curr_issue['text']:
                            issue_resolved = False
                            break
                    
                    if issue_resolved:
                        resolved_issues.append(prev_issue)
                
                # Update thread status for resolved issues
                for resolved_issue in resolved_issues:
                    issue_key = f"{file_path}:{resolved_issue['line']}:{resolved_issue['text']}"
                    if issue_key in all_threads:
                        thread_id = all_threads[issue_key]
                        print(f"Marking thread {thread_id} as fixed for resolved issue: {issue_key}")
                        self.azure_client.update_thread_status(
                            repository_id, 
                            pull_request_id, 
                            thread_id, 
                            status="fixed"
                        )
                        # Add a comment confirming the issue is fixed
                        self.azure_client.add_thread_comment(
                            repository_id,
                            pull_request_id,
                            thread_id,
                            content=f"✅ This issue has been fixed in iteration {iteration}."
                        )
            
            # Update for next iteration
            old_content = current_content
            current_content = improved_content
            previous_issues = current_issues
        
        # Final result
        final_result = {
            "iterations_completed": len(iterations),
            "all_issues_resolved": len(current_issues) == 0,
            "iterations": iterations,
            "final_content": current_content,
            "threads": all_threads
        }
        
        # Save final result
        final_output_file = os.path.join(output_dir, f"{self._safe_filename(file_path)}_final_{timestamp}.json")
        with open(final_output_file, 'w') as f:
            json.dump(final_result, f, indent=2)
        
        return final_result
    
    def _extract_issues(self, reviewer_analysis):
        """Extract issues from reviewer analysis for PR comment posting and tracking.
        
        This method parses the markdown-formatted reviewer analysis to identify:
        1. Issue sections (e.g., "Code Quality", "Security", "Performance")
        2. Individual issues within each section
        3. Line numbers referenced in each issue
        
        The parsing logic uses a simple state machine approach to extract structured
        information from the markdown text. It identifies section headers (## headings)
        and bullet points (- items) within those sections, then extracts line numbers
        using regex pattern matching.
        
        This extracted information is crucial for:
        - Posting comments on the correct lines in the PR
        - Tracking which issues are resolved between iterations
        - Updating thread statuses when issues are fixed
        - Creating meaningful PR comments with proper categorization
        
        Args:
            reviewer_analysis: Markdown-formatted analysis text from the reviewer agent
            
        Returns:
            List of dictionaries, each containing:
            - section: The category of the issue (e.g., "Code Quality")
            - text: The full text description of the issue
            - line: The line number where the issue was found
        """
        lines = reviewer_analysis.split('\n')
        current_section = ""
        issues = []
        current_issue_text = ""
        
        for line in lines:
            # Check for section headers
            if line.startswith('## '):
                current_section = line[3:].strip()
                continue
                
            # Check for bullet points which indicate issues
            if line.strip().startswith('- '):
                # If we were already collecting an issue, save it before starting a new one
                if current_issue_text:
                    # Try to extract line number
                    line_match = re.search(r'line (\d+)', current_issue_text, re.IGNORECASE)
                    line_number = int(line_match.group(1)) if line_match else None
                    
                    if line_number:
                        issues.append({
                            'section': current_section,
                            'text': current_issue_text.strip(),
                            'line': line_number
                        })
                
                # Start collecting a new issue
                current_issue_text = line.strip()[2:]  # Remove the "- " prefix
            elif current_issue_text:
                # Continue collecting the current issue
                current_issue_text += " " + line.strip()
        
        # Don't forget the last issue
        if current_issue_text:
            line_match = re.search(r'line (\d+)', current_issue_text, re.IGNORECASE)
            line_number = int(line_match.group(1)) if line_match else None
            
            if line_number:
                issues.append({
                    'section': current_section,
                    'text': current_issue_text.strip(),
                    'line': line_number
                })
        
        return issues
    
    def _apply_suggestions(self, file_path, content, reviewer_analysis):
        """Apply suggestions from the reviewer to the code.
        
        Args:
            file_path: Path to the file being improved
            content: Current content of the file
            reviewer_analysis: Analysis from the reviewer agent
            
        Returns:
            Improved content with suggestions applied
        """
        print(f"Applying suggestions to {file_path}")
        
        # Use the coder agent to apply suggestions
        improved_content = self.coder_agent.apply_suggestions(file_path, content, reviewer_analysis)
        
        return improved_content
    
    def _safe_filename(self, filename):
        """Convert a file path to a safe filename for saving results.
        
        Args:
            filename: Original file path
            
        Returns:
            Safe filename for saving results
        """
        return filename.replace('/', '_').replace('\\', '_').replace(':', '_')
        
    def _post_review_comments_to_pr(self, repository_id, pull_request_id, file_path, reviewer_analysis, iteration):
        """Post review comments directly to the Azure DevOps PR threads.
        
        This method handles the core PR comment posting functionality:
        1. Checks for existing threads to avoid duplicates
        2. Posts a summary comment for the entire file review
        3. Posts individual issue comments on specific code lines
        4. Updates existing threads rather than creating duplicates
        
        The method parses the reviewer analysis to extract issues and their line numbers,
        then creates or updates PR threads accordingly. Each issue is posted as a separate
        thread attached to the specific line of code where the issue was found.
        
        Thread management features:
        - Threads are identified by file path and line number
        - Existing threads are updated with new comments rather than creating duplicates
        - Each thread is tracked with a unique key for status updates in later iterations
        - Detailed logging helps track which threads are created or updated
        
        Args:
            repository_id: The ID of the repository in Azure DevOps
            pull_request_id: The ID of the pull request being reviewed
            file_path: Path to the file being reviewed
            reviewer_analysis: Markdown-formatted analysis from the reviewer agent
            iteration: Current iteration number in the improvement loop
            
        Returns:
            Dictionary mapping issue keys to thread IDs for tracking and status updates
        """
        # Parse the reviewer analysis to extract issues and their locations
        lines = reviewer_analysis.split('\n')
        issues = self._extract_issues(reviewer_analysis)
        
        # Get existing threads to avoid duplicates
        existing_threads = self.azure_client.get_pull_request_threads(repository_id, pull_request_id)
        
        # Create a summary comment for the file
        summary_content = f"## Code Review - Iteration {iteration}\n\n"
        summary_content += f"AI review for file: `{file_path}`\n\n"
        summary_content += "### Summary\n\n"
        
        # Add a brief summary from the first few lines of the review
        summary_lines = [line for line in lines[:10] if not line.startswith('#') and line.strip()]
        if summary_lines:
            summary_content += "\n".join(summary_lines) + "\n\n"
        
        # Add issue count
        summary_content += f"\n\n**Found {len(issues)} issues to address in this file.**"
        
        # Post the summary comment (not attached to a specific line)
        summary_thread = self.azure_client.add_pull_request_thread(
            repository_id,
            pull_request_id,
            summary_content
        )
        
        # Track threads by issue
        thread_map = {}
        
        # Post individual comments for each issue
        for issue in issues:
            if not issue.get('line'):
                continue
                
            line_number = issue['line']
            issue_text = issue['text']
            section = issue['section']
            
            # Create a unique key for this issue
            issue_key = f"{file_path}:{line_number}:{issue_text}"
            
            # Check if a thread already exists for this issue
            thread_exists = False
            existing_thread_id = None
            
            for thread in existing_threads:
                # Check if thread is for this file and line
                thread_context = thread.get('threadContext', {})
                thread_file_path = thread_context.get('filePath')
                
                if thread_file_path == file_path:
                    right_file_start = thread_context.get('rightFileStart', {})
                    thread_line = right_file_start.get('line') if right_file_start else None
                    
                    if thread_line == line_number:
                        # Check if the content is similar
                        thread_comments = thread.get('comments', [])
                        if thread_comments:
                            first_comment = thread_comments[0].get('content', '')
                            # Simple check - if the section name appears in the comment
                            if section in first_comment:
                                thread_exists = True
                                existing_thread_id = thread['id']
                                break
            
            # Format the comment
            comment_content = f"## {section}\n\n{issue_text}"
            
            if thread_exists and existing_thread_id:
                # Add a comment to the existing thread
                logger.info(f"Updating existing thread for {issue_key}")
                self.azure_client.add_thread_comment(
                    repository_id,
                    pull_request_id,
                    existing_thread_id,
                    f"Iteration {iteration}: {issue_text}"
                )
                thread_map[issue_key] = existing_thread_id
            else:
                # Create a new thread for this issue
                logger.info(f"Creating new thread for {issue_key}")
                thread = self.azure_client.add_pull_request_thread(
                    repository_id,
                    pull_request_id,
                    comment_content,
                    file_path,
                    line_number
                )
                thread_map[issue_key] = thread['id']
        
        return thread_map


class BatchImprovementProcessor:
    """Process multiple files for iterative improvement in batch."""
    
    def __init__(self, use_local_llm: bool = False):
        """Initialize the batch processor.
        
        Args:
            use_local_llm: Whether to use a local LLM instead of OpenAI
        """
        self.improvement_loop = IterativeImprovementLoop(use_local_llm=use_local_llm)
        self.azure_client = AzureDevOpsIterationClient()
    
    def process_pull_request(self, pull_request_id, max_iterations=3, output_dir="reviews/improvements", post_comments=True):
        """Process all files in a pull request for iterative improvement.
        
        Args:
            pull_request_id: The ID of the pull request
            max_iterations: Maximum number of iterations per file
            output_dir: Directory to save improvement results
            post_comments: Whether to post comments to the PR
            
        Returns:
            Dictionary containing the improvement results for all files
        """
        print(f"Processing pull request {pull_request_id} for iterative improvement")
        
        # Get pull request details
        pr_details = self.azure_client.get_pull_request(pull_request_id)
        repository_id = pr_details['repository']['id']
        
        # Get the latest iteration
        iterations = self.azure_client.get_pull_request_iterations(repository_id, pull_request_id)
        latest_iteration = iterations[-1]['id']
        
        # Get changes for the latest iteration
        changes = self.azure_client.get_pull_request_changes(repository_id, pull_request_id, latest_iteration)
        
        # Process each changed file
        results = {}
        for change in changes:
            if change['changeType'] == 'Edit':
                file_path = change['item']['path']
                
                # Skip binary files, test files, etc.
                if self._should_skip_file(file_path):
                    print(f"Skipping file: {file_path}")
                    continue
                
                print(f"Processing file: {file_path}")
                
                # Get the old and new content
                old_commit_id = change.get('sourceServerItem', {}).get('commitId')
                new_commit_id = change['item']['commitId']
                
                try:
                    old_content = self.azure_client.get_file_content(repository_id, old_commit_id, file_path) if old_commit_id else ""
                    new_content = self.azure_client.get_file_content(repository_id, new_commit_id, file_path)
                    
                    # Run the improvement loop
                    result = self.improvement_loop.improve_code(
                        pull_request_id,
                        file_path,
                        old_content,
                        new_content,
                        max_iterations=max_iterations,
                        output_dir=output_dir,
                        post_comments=post_comments
                    )
                    
                    results[file_path] = result
                except Exception as e:
                    print(f"Error processing file {file_path}: {str(e)}")
                    results[file_path] = {"error": str(e)}
        
        return results
    
    def _should_skip_file(self, file_path):
        """Check if a file should be skipped.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if the file should be skipped, False otherwise
        """
        # Skip binary files, test files, etc.
        skip_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.pdf', '.zip', '.tar', '.gz']
        skip_patterns = ['test_', 'tests/', '/test/', '/tests/']
        
        # Check extensions
        _, ext = os.path.splitext(file_path)
        if ext.lower() in skip_extensions:
            return True
            
        # Check patterns
        for pattern in skip_patterns:
            if pattern in file_path:
                return True
                
        return False


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
