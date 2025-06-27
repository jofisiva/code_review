from azure_devops_iteration_client import AzureDevOpsIterationClient
from langgraph_agents import create_pr_review_graph, PRReviewState
import time
import json
import os
from typing import Dict, List, Any, Literal

class MultiIterationReviewOrchestrator:
    """Orchestrates the code review process across multiple PR iterations."""
    
    def __init__(self):
        """Initialize the orchestrator with Azure DevOps client and LangGraph."""
        self.azure_client = AzureDevOpsIterationClient()
        self.pr_review_graph = create_pr_review_graph()
        
    def review_pull_request(self, pull_request_id, output_dir="reviews", iteration_id=None, latest_only=False):
        """
        Review a pull request using the LangGraph-based agent workflow.
        
        Args:
            pull_request_id: The ID of the pull request to review
            output_dir: Directory to save review results
            iteration_id: Specific iteration to review (None for all iterations)
            
        Returns:
            Dictionary containing the review results
        """
        print(f"Starting multi-iteration review for PR #{pull_request_id}")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Get pull request details
        pr = self.azure_client.get_pull_request(pull_request_id)
        print(f"Reviewing PR: {pr.title}")
        
        # Get all iterations for the pull request
        iterations = self.azure_client.get_pull_request_iterations(pull_request_id)
        print(f"Found {len(iterations)} iterations in the pull request")
        
        # If a specific iteration is requested, filter to just that one
        if iteration_id is not None:
            iterations = [it for it in iterations if it.id == iteration_id]
            if not iterations:
                raise ValueError(f"Iteration {iteration_id} not found in pull request {pull_request_id}")
        # If only the latest iteration is requested
        elif latest_only and iterations:
            # Sort iterations by ID (assuming higher ID = newer iteration)
            iterations = [max(iterations, key=lambda it: it.id)]
        
        all_iteration_results = []
        
        # Process each iteration
        for iteration in iterations:
            print(f"Processing iteration {iteration.id}")
            iteration_result = self._review_iteration(pull_request_id, iteration.id, pr, output_dir)
            all_iteration_results.append(iteration_result)
        
        # Generate a cross-iteration summary if we have multiple iterations
        if len(all_iteration_results) > 1:
            cross_iteration_summary = self._generate_cross_iteration_summary(all_iteration_results, pr)
            
            # Save the cross-iteration summary
            summary_path = os.path.join(output_dir, f"cross_iteration_summary_{pull_request_id}.json")
            with open(summary_path, 'w') as f:
                json.dump(cross_iteration_summary, f, indent=2)
                
            print(f"Cross-iteration summary saved to {summary_path}")
            return cross_iteration_summary
        elif all_iteration_results:
            # Return the single iteration result if there's only one
            return all_iteration_results[0]
        else:
            return {"error": "No iterations were reviewed"}
    
    def _review_iteration(self, pull_request_id, iteration_id, pr, output_dir):
        """Review a specific iteration of a pull request."""
        # Get files changed in this iteration
        files = self.azure_client.get_iteration_file_changes(pull_request_id, iteration_id)
        print(f"Found {len(files)} changed files in iteration {iteration_id}")
        
        # Filter out binary files or files that are too large
        filtered_files = []
        for file_info in files:
            file_path = file_info["path"]
            if not self._is_text_file(file_path) or len(file_info["new_content"]) > 50000:
                print(f"Skipping file (binary or too large): {file_path}")
                continue
            filtered_files.append(file_info)
        
        # Initialize the PR review state
        pr_state = PRReviewState(
            pull_request_id=pull_request_id,
            title=f"{pr.title} (Iteration {iteration_id})",
            repository=pr.repository.name,
            source_branch=pr.source_ref_name,
            target_branch=pr.target_ref_name,
            created_by=pr.created_by.display_name,
            files=filtered_files,
            current_file_index=0,
            summary_review="",
            status="reviewing_files"
        )
        
        # Execute the PR review graph
        print(f"Starting LangGraph workflow for iteration {iteration_id} with {len(filtered_files)} files")
        final_state = self.pr_review_graph.invoke(pr_state)
        print(f"LangGraph workflow completed for iteration {iteration_id}")
        
        # Prepare the review results
        review_results = {
            "pull_request_id": pull_request_id,
            "iteration_id": iteration_id,
            "title": final_state["title"],
            "created_by": final_state["created_by"],
            "repository": final_state["repository"],
            "source_branch": final_state["source_branch"],
            "target_branch": final_state["target_branch"],
            "files": final_state["files"],
            "summary_review": final_state["summary_review"]
        }
        
        # Save individual file reviews
        for file_info in review_results["files"]:
            file_output_path = os.path.join(
                output_dir, 
                f"file_review_{pull_request_id}_iteration_{iteration_id}_{self._sanitize_filename(file_info['path'])}.json"
            )
            with open(file_output_path, 'w') as f:
                json.dump(file_info, f, indent=2)
        
        # Save iteration review
        output_path = os.path.join(output_dir, f"iteration_review_{pull_request_id}_{iteration_id}.json")
        with open(output_path, 'w') as f:
            json.dump(review_results, f, indent=2)
            
        print(f"Iteration {iteration_id} review complete. Results saved to {output_path}")
        return review_results
    
    def _generate_cross_iteration_summary(self, iteration_results, pr):
        """Generate a summary comparing changes across iterations."""
        # Create a special agent to analyze changes across iterations
        from langchain_openai import ChatOpenAI
        from config import OPENAI_MODEL_REVIEWER, OPENAI_API_KEY
        
        llm = ChatOpenAI(
            model=OPENAI_MODEL_REVIEWER,
            temperature=0.4,
            api_key=OPENAI_API_KEY
        )
        
        # Prepare the prompt with information about all iterations
        iterations_summary = []
        for i, result in enumerate(iteration_results):
            iterations_summary.append(f"## Iteration {result['iteration_id']}\n\n{result['summary_review']}\n\n")
            
            # Add file changes for this iteration
            iterations_summary.append("### Files changed in this iteration:\n")
            for file in result['files']:
                iterations_summary.append(f"- {file['path']} ({file['change_type']})\n")
            
            iterations_summary.append("\n")
        
        prompt = f"""
        You are analyzing a pull request with multiple iterations.
        
        Pull Request: #{pr.id} - {pr.title}
        Repository: {pr.repository.name}
        Source Branch: {pr.source_ref_name}
        Target Branch: {pr.target_ref_name}
        Created By: {pr.created_by.display_name}
        
        Here are the summaries for each iteration:
        
        {"".join(iterations_summary)}
        
        Please provide:
        1. An overall assessment of how the code evolved across iterations
        2. Key improvements made in response to feedback between iterations
        3. Any recurring issues that persisted across iterations
        4. A final recommendation on the quality of the code in the latest iteration
        
        Format your response as markdown.
        """
        
        # Get response from LLM
        response = llm.invoke(prompt)
        
        # Create the cross-iteration summary
        cross_iteration_summary = {
            "pull_request_id": pr.id,
            "title": pr.title,
            "repository": pr.repository.name,
            "source_branch": pr.source_ref_name,
            "target_branch": pr.target_ref_name,
            "created_by": pr.created_by.display_name,
            "iteration_count": len(iteration_results),
            "iterations": [result["iteration_id"] for result in iteration_results],
            "cross_iteration_analysis": response.content
        }
        
        return cross_iteration_summary
    
    def post_review_comments(self, pull_request_id, review_results, iteration_id=None):
        """Post review comments to the pull request."""
        pr = self.azure_client.get_pull_request(pull_request_id)
        repository_id = pr.repository.id
        
        # Determine if we're posting a cross-iteration summary or a single iteration review
        if "cross_iteration_analysis" in review_results:
            # Post cross-iteration summary
            self.azure_client.add_pull_request_thread(
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                content=f"# AI Cross-Iteration Code Review Summary\n\n{review_results['cross_iteration_analysis']}"
            )
        else:
            # Post single iteration summary
            iteration_text = f" (Iteration {review_results['iteration_id']})" if iteration_id else ""
            self.azure_client.add_pull_request_thread(
                repository_id=repository_id,
                pull_request_id=pull_request_id,
                content=f"# AI Code Review Summary{iteration_text}\n\n{review_results['summary_review']}"
            )
            
            # Post file-specific comments
            for file_result in review_results["files"]:
                # Extract key points from the reviewer analysis
                if "reviewer_analysis" not in file_result:
                    continue
                    
                lines = file_result["reviewer_analysis"].split("\n")
                current_section = ""
                comments = []
                
                for line in lines:
                    if line.startswith("##"):
                        current_section = line.strip("# ")
                    elif line.startswith("- ") and current_section:
                        comments.append(f"**{current_section}**: {line[2:]}")
                
                # Post a comment for each file with key points
                if comments:
                    comment_content = f"# AI Review for `{file_result['path']}`{iteration_text}\n\n"
                    comment_content += "\n\n".join(comments[:5])  # Limit to top 5 comments
                    
                    self.azure_client.add_pull_request_thread(
                        repository_id=repository_id,
                        pull_request_id=pull_request_id,
                        content=comment_content,
                        file_path=file_result["path"],
                        line_number=1  # Default to first line, could be more specific
                    )
        
        print(f"Posted review comments to PR #{pull_request_id}")
    
    def _is_text_file(self, file_path):
        """Check if a file is a text file based on its extension."""
        text_extensions = [
            '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.scss', '.json', '.md',
            '.yml', '.yaml', '.xml', '.txt', '.sh', '.bat', '.ps1', '.c', '.cpp', '.h',
            '.cs', '.java', '.go', '.rb', '.php', '.swift', '.kt', '.rs'
        ]
        
        return any(file_path.lower().endswith(ext) for ext in text_extensions)
    
    def _sanitize_filename(self, filename):
        """Sanitize a filename for use in the filesystem."""
        # Replace path separators and other problematic characters
        return filename.replace('/', '_').replace('\\', '_').replace(':', '_')
