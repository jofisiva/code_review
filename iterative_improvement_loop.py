from agents.coder_agent import CoderAgent
from agents.reviewer_agent import ReviewerAgent
from azure_devops_iteration_client import AzureDevOpsIterationClient
from langgraph_agents import create_file_review_graph, FileReviewState
import time
import json
import os
from typing import Dict, List, Any, Optional, Union, Literal
import re
from config import USE_LOCAL_LLM

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
        """Initialize the iterative improvement loop with agents.
        
        Args:
            use_local_llm: Whether to use a local LLM instead of OpenAI
        """
        self.use_local_llm = use_local_llm or USE_LOCAL_LLM
        self.coder_agent = CoderAgent(use_local_llm=self.use_local_llm)
        self.reviewer_agent = ReviewerAgent(use_local_llm=self.use_local_llm)
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
        pr = self.azure_client.get_pull_request(pull_request_id)
        repository_id = pr.repository.id
        
        # Initialize state
        current_content = new_content
        iterations = []
        issue_threads = {}
        resolved_issues = set()  # Track which issues have been resolved
        all_issues_resolved = False
        
        # Run the improvement loop
        for iteration in range(1, max_iterations + 1):
            print(f"Iteration {iteration} for {file_path}")
            
            # Create the file state for this iteration
            file_state = {
                "file_path": file_path,
                "old_content": old_content,
                "new_content": current_content,
                "iteration": iteration
            }
            
            # Run the review graph
            final_state = self.file_review_graph.invoke(file_state)
            
            # Extract the reviewer analysis
            reviewer_analysis = final_state["reviewer_analysis"]
            
            # Extract current issues for tracking
            current_issues = self._extract_issues(reviewer_analysis)
            current_issue_keys = {f"{file_path}:{issue['line']}:{issue['section']}" for issue in current_issues}
            
            # Identify resolved issues (issues from previous iterations that are no longer present)
            if iteration > 1 and post_comments:
                for issue_key in list(issue_threads.keys()):
                    if issue_key not in current_issue_keys and issue_key not in resolved_issues:
                        # This issue has been resolved
                        resolved_issues.add(issue_key)
                        try:
                            thread_id = issue_threads[issue_key]
                            print(f"Marking thread {thread_id} as fixed for resolved issue: {issue_key}")
                            self.azure_client.update_thread_status(
                                repository_id=repository_id,
                                pull_request_id=pull_request_id,
                                thread_id=thread_id,
                                status="fixed"
                            )
                            # Add a comment indicating the issue is fixed
                            self.azure_client.add_thread_comment(
                                repository_id=repository_id,
                                pull_request_id=pull_request_id,
                                thread_id=thread_id,
                                content=f"✅ This issue was resolved in iteration {iteration}."
                            )
                        except Exception as e:
                            print(f"Error updating thread status: {str(e)}")
            
            # Post comments to PR if enabled
            if post_comments:
                new_threads = self._post_review_comments_to_pr(
                    repository_id=repository_id,
                    pull_request_id=pull_request_id,
                    file_path=file_path,
                    reviewer_analysis=reviewer_analysis,
                    iteration=iteration
                )
                
                # Track threads for status updates
                issue_threads.update(new_threads)
            
            # Extract code suggestions
            suggestions = self._extract_code_suggestions(reviewer_analysis)
            
            # Save the iteration results
            iteration_result = {
                "iteration": iteration,
                "reviewer_analysis": reviewer_analysis,
                "suggestions": suggestions,
                "content": current_content,
                "resolved_issues": list(resolved_issues)
            }
            iterations.append(iteration_result)
            
            # Save the iteration to a file
            iteration_path = os.path.join(
                output_dir, 
                f"iteration_{iteration}_{pull_request_id}_{self._sanitize_filename(file_path)}.json"
            )
            with open(iteration_path, 'w') as f:
                json.dump(iteration_result, f, indent=2)
            
            # If no suggestions, we're done
            if not suggestions:
                print(f"No more suggestions for {file_path} after {iteration} iterations")
                all_issues_resolved = True
                break
            
            # Apply the suggestions
            improved_content = self._apply_suggestions(current_content, suggestions)
            
            # If content didn't change, we're done
            if improved_content == current_content:
                print(f"No changes made for {file_path} in iteration {iteration}")
                break
                
            # Update the current content for the next iteration
            current_content = improved_content
        
        # Mark any remaining threads as fixed if all issues are resolved
        if all_issues_resolved and post_comments and issue_threads:
            print(f"All issues resolved for {file_path}, marking remaining threads as fixed")
            for issue_key, thread_id in issue_threads.items():
                if issue_key not in resolved_issues:
                    try:
                        self.azure_client.update_thread_status(
                            repository_id=repository_id,
                            pull_request_id=pull_request_id,
                            thread_id=thread_id,
                            status="fixed"
                        )
                        # Add a comment indicating all issues are resolved
                        self.azure_client.add_thread_comment(
                            repository_id=repository_id,
                            pull_request_id=pull_request_id,
                            thread_id=thread_id,
                            content=f"✅ All issues have been resolved after {len(iterations)} iterations."
                        )
                        resolved_issues.add(issue_key)
                    except Exception as e:
                        print(f"Error updating thread status: {str(e)}")
                if post_comments:
                    for thread_id in issue_threads.values():
                        try:
                            self.azure_client.update_thread_status(
                                repository_id=repository_id,
                                pull_request_id=pull_request_id,
                                thread_id=thread_id,
                                status="fixed"
                            )
                            print(f"Marked thread {thread_id} as fixed")
                        except Exception as e:
                            print(f"Error updating thread {thread_id}: {str(e)}")
                break
                
            print(f"Completed iteration {iteration}, {remaining_issues} issues remaining")
        
        # Prepare the final result
        final_result = {
            "pull_request_id": pull_request_id,
            "file_path": file_path,
            "iterations_completed": len(iterations),
            "all_issues_resolved": all_issues_resolved,
            "iterations": iterations,
            "final_content": current_content,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "threads": list(issue_threads.values()) if post_comments else []
        }
        
        # Save final results
        final_path = os.path.join(
            output_dir, 
            f"final_improvement_{pull_request_id}_{self._sanitize_filename(file_path)}.json"
        )
        with open(final_path, 'w') as f:
            json.dump(final_result, f, indent=2)
            
        print(f"Iterative improvement complete for {file_path}")
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
        
        # Extract sections and issues
        for line in lines:
            if line.startswith("##"):
                current_section = line.strip("# ")
            elif line.startswith("- ") and current_section:
                issue_text = line[2:]
                # Try to extract line numbers using regex
                line_match = re.search(r'line[s]?\s*(\d+)(?:\s*-\s*(\d+))?', issue_text, re.IGNORECASE)
                line_number = int(line_match.group(1)) if line_match else 1
                
                issues.append({
                    "section": current_section,
                    "text": issue_text,
                    "line": line_number
                })
        
        return issues
    
    def _extract_code_suggestions(self, reviewer_analysis):
        """Extract code suggestions from reviewer analysis."""
        suggestions = []
        
        # Look for code suggestions sections
        sections = re.split(r'##\s+', reviewer_analysis)
        for section in sections:
            if section.lower().startswith('code suggestions') or section.lower().startswith('suggested changes'):
                lines = section.split('\n')
                # Skip the section title
                suggestion_text = '\n'.join(lines[1:])
                
                # Extract individual suggestions
                suggestion_blocks = re.split(r'```\w*\n|```', suggestion_text)
                for i in range(1, len(suggestion_blocks), 2):
                    if i < len(suggestion_blocks):
                        suggestions.append(suggestion_blocks[i].strip())
        
        # Also look for inline code suggestions with markdown code blocks
        code_blocks = re.findall(r'```\w*\n(.*?)```', reviewer_analysis, re.DOTALL)
        for block in code_blocks:
            if block not in suggestions:
                suggestions.append(block.strip())
                
        return suggestions
    
    def _apply_suggestions(self, current_content, suggestions, file_path, coder_analysis):
        """Apply code suggestions using the coder agent."""
        # Prepare the prompt for the coder agent
        prompt = f"""
        You are tasked with improving the following file based on reviewer suggestions.
        
        File path: {file_path}
        
        Current content:
        ```
        {current_content}
        ```
        
        Reviewer has suggested the following changes:
        """
        
        for i, suggestion in enumerate(suggestions, 1):
            prompt += f"\nSuggestion {i}:\n```\n{suggestion}\n```\n"
            
        prompt += """
        Please apply these suggestions to improve the code. Return the complete improved code.
        Make sure to maintain the overall structure and functionality while addressing the reviewer's concerns.
        """
        
        # Get improved code from coder agent
        response = self.coder_agent.generate_response(prompt)
        
        # Extract code from the response
        improved_content = self._extract_code_from_response(response, current_content)
        
        return improved_content
    
    def _extract_code_from_response(self, response, fallback_content):
        """Extract code from agent response."""
        # Look for code blocks
        code_blocks = re.findall(r'```\w*\n(.*?)```', response, re.DOTALL)
        if code_blocks:
            # Use the largest code block (most likely the complete file)
            return max(code_blocks, key=len).strip()
        
        # If no code blocks found, try to find the code without markdown
        # This is a fallback and might not be accurate
        lines = response.split('\n')
        code_lines = []
        in_code = False
        
        for line in lines:
            if line.strip() == '```' or line.strip().startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                code_lines.append(line)
                
        if code_lines:
            return '\n'.join(code_lines)
            
        # If we couldn't extract code, return the original content
        return fallback_content
    
    def _count_remaining_issues(self, reviewer_analysis):
        """Count remaining issues in reviewer analysis."""
        # Look for sections that indicate issues
        issue_sections = ['bugs', 'issues', 'problems', 'concerns', 'code smells']
        
        # Split by sections
        sections = re.split(r'##\s+', reviewer_analysis.lower())
        
        # Count issues
        issue_count = 0
        for section in sections:
            for issue_type in issue_sections:
                if section.startswith(issue_type):
                    # Count bullet points in this section
                    bullet_points = re.findall(r'^\s*[-*]\s+', section, re.MULTILINE)
                    issue_count += len(bullet_points)
        
        return issue_count
    
    def _sanitize_filename(self, filename):
        """Sanitize a filename for use in the filesystem."""
        # Replace path separators and other problematic characters
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
        current_section = ""
        issues = []
        issue_threads = {}
        
        # First, check for existing threads to avoid duplicates
        existing_threads = {}
        try:
            # Get all existing threads for this PR
            all_threads = self.azure_client.get_pull_request_threads(repository_id, pull_request_id)
            
            # Filter threads for this file
            for thread in all_threads:
                if hasattr(thread, 'thread_context') and thread.thread_context:
                    if thread.thread_context.file_path == file_path:
                        # Create a key based on file path and line number
                        thread_key = f"{file_path}:{thread.thread_context.right_line or 1}"
                        existing_threads[thread_key] = thread.id
        except Exception as e:
            print(f"Error fetching existing threads: {str(e)}")
        
        # Create a summary comment for the file
        summary_content = f"# AI Code Review - Iteration {iteration}\n\n"
        summary_content += f"Reviewing file: `{file_path}`\n\n"
        summary_content += "## Summary of Issues\n"
        
        # Extract sections and issues
        for line in lines:
            if line.startswith("##"):
                current_section = line.strip("# ")
            elif line.startswith("- ") and current_section:
                issue_text = line[2:]
                # Try to extract line numbers using regex
                line_match = re.search(r'line[s]?\s*(\d+)(?:\s*-\s*(\d+))?', issue_text, re.IGNORECASE)
                line_number = int(line_match.group(1)) if line_match else 1
                
                issues.append({
                    "section": current_section,
                    "text": issue_text,
                    "line": line_number
                })
                
                # Add to summary
                summary_content += f"- **{current_section}**: {issue_text}\n"
        
        # Post the summary comment
        try:
            summary_thread = self.azure_client.add_pull_request_thread(
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                content=summary_content,
                file_path=file_path
            )
            print(f"Posted summary comment for {file_path} (Thread ID: {summary_thread.id})")
        except Exception as e:
            print(f"Error posting summary comment: {str(e)}")
        
        # Post individual issues as comments on specific lines
        for issue in issues:
            try:
                # Create a unique key for this issue to avoid duplicates
                issue_key = f"{file_path}:{issue['line']}:{issue['section']}"
                thread_location_key = f"{file_path}:{issue['line']}"
                
                # Create the comment content
                content = f"**{issue['section']}**: {issue['text']}\n\n"
                content += f"*AI Code Review - Iteration {iteration}*"
                
                # Check if we already have a thread at this location
                if thread_location_key in existing_threads:
                    # Add a comment to the existing thread
                    thread_id = existing_threads[thread_location_key]
                    self.azure_client.add_thread_comment(
                        repository_id=repository_id,
                        pull_request_id=pull_request_id,
                        thread_id=thread_id,
                        content=f"Update - Iteration {iteration}:\n{content}"
                    )
                    issue_threads[issue_key] = thread_id
                    print(f"Updated existing thread {thread_id} for issue at line {issue['line']}")
                else:
                    # Create a new thread
                    thread = self.azure_client.add_pull_request_thread(
                        repository_id=repository_id,
                        pull_request_id=pull_request_id,
                        content=content,
                        file_path=file_path,
                        line_number=issue['line']
                    )
                    
                    # Store the thread ID
                    issue_threads[issue_key] = thread.id
                    print(f"Posted new comment for issue: {issue['section']} at line {issue['line']}")
                
            except Exception as e:
                print(f"Error posting comment for issue: {str(e)}")
        
        return issue_threads


class IterativeImprovementLoop:
    """
    Implements an iterative improvement loop for code review with PR comment integration.
    
    This class orchestrates the iterative code review and improvement process by:
    1. Using a reviewer agent to analyze code and identify issues
    2. Posting detailed comments directly to Azure DevOps PR threads
    3. Using a coder agent to apply suggested improvements
    4. Tracking issue resolution across iterations
    5. Updating PR thread statuses when issues are fixed
    
    The loop continues until either all issues are resolved, the maximum number of
    iterations is reached, or no further improvements can be made.
    
    PR Comment Features:
    - Posts summary comments for each file review iteration
    - Posts individual issue comments on specific code lines
    - Updates existing threads rather than creating duplicates
    - Automatically marks threads as "fixed" when issues are resolved
    - Adds confirmation comments when issues are fixed
    - Tracks thread IDs across iterations for status updates
    """
    
    def __init__(self, use_local_llm: bool = False):
        """Initialize the improvement loop with agents and clients.
        
        Args:
            use_local_llm: Whether to use a local LLM instead of OpenAI API
                          This flag is passed to both reviewer and coder agents
        """
        self.use_local_llm = use_local_llm or USE_LOCAL_LLM
        self.azure_client = AzureDevOpsIterationClient()
        self.file_review_graph = create_file_review_graph(use_local_llm=self.use_local_llm)
        self.azure_client = AzureDevOpsIterationClient()
        
    def process_pull_request(self, pull_request_id, max_iterations=3, output_dir="reviews/improvements", post_comments=True):
        """
        Process all files in a pull request for iterative improvement.
{{ ... }}
        Args:
            pull_request_id: The ID of the pull request
            max_iterations: Maximum number of improvement iterations per file
            output_dir: Directory to save improvement results
            
        Returns:
            Dictionary containing the batch improvement results
        """
        print(f"Starting batch improvement for PR #{pull_request_id}")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get pull request details
        pr = self.azure_client.get_pull_request(pull_request_id)
        
        # Get the latest iteration
        iterations = self.azure_client.get_pull_request_iterations(pull_request_id)
        if not iterations:
            raise ValueError(f"No iterations found for pull request {pull_request_id}")
            
        latest_iteration = max(iterations, key=lambda it: it.id)
        
        # Get files changed in the latest iteration
        files = self.azure_client.get_iteration_file_changes(pull_request_id, latest_iteration.id)
        print(f"Found {len(files)} changed files in the latest iteration")
        
        # Filter out binary files or files that are too large
        filtered_files = []
        for file_info in files:
            file_path = file_info["path"]
            if not self._is_text_file(file_path) or len(file_info["new_content"]) > 50000:
                print(f"Skipping file (binary or too large): {file_path}")
                continue
            filtered_files.append(file_info)
        
        # Process each file
        file_results = []
        for file_info in filtered_files:
            try:
                file_path = file_info["path"]
                old_content = file_info.get("old_content", "")
                new_content = file_info["new_content"]
                
                print(f"Processing file: {file_path}")
                
                # Run the improvement loop
                result = self.improvement_loop.improve_code(
                    pull_request_id=pull_request_id,
                    file_path=file_path,
                    old_content=old_content,
                    new_content=new_content,
                    max_iterations=max_iterations,
                    output_dir=output_dir,
                    post_comments=post_comments
                )
                
                file_results.append({
                    "file_path": file_path,
                    "iterations_completed": result["iterations_completed"],
                    "all_issues_resolved": result["all_issues_resolved"]
                })
                
            except Exception as e:
                print(f"Error processing file {file_info['path']}: {str(e)}")
                file_results.append({
                    "file_path": file_info["path"],
                    "error": str(e)
                })
        
        # Prepare batch results
        batch_results = {
            "pull_request_id": pull_request_id,
            "repository": pr.repository.name,
            "title": pr.title,
            "files_processed": len(file_results),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "file_results": file_results
        }
        
        # Save batch results
        batch_path = os.path.join(output_dir, f"batch_improvement_{pull_request_id}.json")
        with open(batch_path, 'w') as f:
            json.dump(batch_results, f, indent=2)
            
        print(f"Batch improvement complete for PR #{pull_request_id}")
        return batch_results
    
    def _is_text_file(self, file_path):
        """Check if a file is a text file based on its extension."""
        text_extensions = [
            '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss', '.json', '.md',
            '.yml', '.yaml', '.xml', '.txt', '.sh', '.bat', '.ps1', '.c', '.cpp', '.h',
            '.cs', '.java', '.go', '.rb', '.php', '.swift', '.kt', '.rs'
        ]
        
        return any(file_path.lower().endswith(ext) for ext in text_extensions)
