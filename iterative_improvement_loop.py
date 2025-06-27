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
        
    def improve_code(self, pull_request_id, file_path, old_content, new_content, 
                     max_iterations=3, output_dir="reviews/improvements"):
        """
        Iteratively improve code based on reviewer suggestions.
        
        Args:
            pull_request_id: The ID of the pull request
            file_path: Path to the file being improved
            old_content: Original content of the file
            new_content: Current content of the file
            max_iterations: Maximum number of improvement iterations
            output_dir: Directory to save improvement results
            
        Returns:
            Dictionary containing the improvement results
        """
        print(f"Starting iterative improvement for {file_path}")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get pull request details
        pr = self.azure_client.get_pull_request(pull_request_id)
        
        # Initialize variables
        current_content = new_content
        iterations = []
        all_issues_resolved = False
        
        # Start the improvement loop
        for iteration in range(1, max_iterations + 1):
            print(f"Improvement iteration {iteration} for {file_path}")
            
            # Run the file review to get reviewer suggestions
            file_state = FileReviewState(
                file_path=file_path,
                old_content=old_content,
                new_content=current_content,
                coder_analysis="",
                reviewer_analysis="",
                status="analyzing",
                use_local_llm=self.use_local_llm  # Pass the use_local_llm flag to the graph
            )
            
            # Execute the file review graph
            final_state = self.file_review_graph.invoke(file_state)
            
            # Extract reviewer suggestions
            reviewer_analysis = final_state["reviewer_analysis"]
            suggestions = self._extract_code_suggestions(reviewer_analysis)
            
            # Check if there are any suggestions
            if not suggestions:
                print(f"No code suggestions found in iteration {iteration}")
                all_issues_resolved = True
                break
                
            # Apply suggestions using the coder agent
            improved_content = self._apply_suggestions(
                current_content, 
                suggestions, 
                file_path,
                final_state["coder_analysis"]
            )
            
            # Save the iteration results
            iteration_result = {
                "iteration": iteration,
                "file_path": file_path,
                "reviewer_analysis": reviewer_analysis,
                "suggestions": suggestions,
                "original_content": current_content,
                "improved_content": improved_content,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            iterations.append(iteration_result)
            
            # Save iteration to file
            iteration_path = os.path.join(
                output_dir, 
                f"improvement_{pull_request_id}_{self._sanitize_filename(file_path)}_iteration_{iteration}.json"
            )
            with open(iteration_path, 'w') as f:
                json.dump(iteration_result, f, indent=2)
                
            # Update current content for next iteration
            current_content = improved_content
            
            # Check if all issues were resolved
            remaining_issues = self._count_remaining_issues(reviewer_analysis)
            if remaining_issues == 0:
                all_issues_resolved = True
                print(f"All issues resolved after iteration {iteration}")
                break
                
            print(f"Completed iteration {iteration}, {remaining_issues} issues remaining")
        
        # Prepare the final improvement results
        improvement_results = {
            "pull_request_id": pull_request_id,
            "file_path": file_path,
            "iterations_completed": len(iterations),
            "all_issues_resolved": all_issues_resolved,
            "final_content": current_content,
            "original_content": new_content,
            "iterations": iterations
        }
        
        # Save final results
        final_path = os.path.join(
            output_dir, 
            f"final_improvement_{pull_request_id}_{self._sanitize_filename(file_path)}.json"
        )
        with open(final_path, 'w') as f:
            json.dump(improvement_results, f, indent=2)
            
        print(f"Iterative improvement complete for {file_path}")
        return improvement_results
    
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


class BatchImprovementProcessor:
    """
    Process multiple files for iterative improvement.
    """
    
    def __init__(self, use_local_llm: bool = False):
        """Initialize the batch processor.
        
        Args:
            use_local_llm: Whether to use a local LLM instead of OpenAI
        """
        self.use_local_llm = use_local_llm or USE_LOCAL_LLM
        self.improvement_loop = IterativeImprovementLoop(use_local_llm=self.use_local_llm)
        self.azure_client = AzureDevOpsIterationClient()
        
    def process_pull_request(self, pull_request_id, max_iterations=3, output_dir="reviews/improvements"):
        """
        Process all files in a pull request for iterative improvement.
        
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
                    output_dir=output_dir
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
