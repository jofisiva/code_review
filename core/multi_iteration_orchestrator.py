"""
Multi-iteration review orchestrator for Azure DevOps pull requests.
"""
import os
import re
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Union

from agents.reviewer_agent import ReviewerAgent
from agents.coder_agent import CoderAgent
from azure_devops.client import AzureDevOpsIterationClient
from core.iterative_improvement_loop import IterativeImprovementLoop
from pr_review_checklist import PRReviewChecklist

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MultiIterationReviewOrchestrator:
    """
    Orchestrates the review of multiple iterations of a pull request.
    
    This class handles:
    1. Fetching pull request data from Azure DevOps
    2. Analyzing changes across multiple iterations
    3. Running code reviews using AI agents
    4. Posting review comments to the PR
    5. Running iterative improvement loops
    """
    
    def __init__(self, use_local_llm: bool = False, post_comments: bool = False, auto_post_comments: bool = False):
        """Initialize the multi-iteration review orchestrator.
        
        Args:
            use_local_llm: Whether to use a local LLM instead of OpenAI
            post_comments: Whether to post summary comments to the PR
            auto_post_comments: Whether to automatically post detailed comments on specific lines
        """
        self.use_local_llm = use_local_llm
        self.post_comments = post_comments
        self.auto_post_comments = auto_post_comments
        self.reviewer_agent = ReviewerAgent(use_local_llm=use_local_llm)
        self.coder_agent = CoderAgent(use_local_llm=use_local_llm)
        self.azure_client = AzureDevOpsIterationClient()
        self.improvement_loop = IterativeImprovementLoop(use_local_llm=use_local_llm)
        self.checklist = PRReviewChecklist()
    
    def get_pull_request_iterations(self, pull_request_id):
        """Get all iterations of a pull request.
        
        Args:
            pull_request_id: The ID of the pull request
            
        Returns:
            List of iterations with their details
        """
        # Get pull request details
        pr_details = self.azure_client.get_pull_request(pull_request_id)
        repository_id = pr_details['repository']['id']
        
        # Get iterations
        iterations = self.azure_client.get_pull_request_iterations(repository_id, pull_request_id)
        
        return {
            'pull_request': pr_details,
            'iterations': iterations
        }
    
    def review_pull_request(self, pull_request_id, iteration_id=None, review_all=False, 
                           include_checklist=False, include_java_checklist=False,
                           run_improvement_loop=False):
        """Review a specific iteration or all iterations of a pull request.
        
        Args:
            pull_request_id: The ID of the pull request
            iteration_id: The ID of the specific iteration to review (None for latest)
            review_all: Whether to review all iterations
            include_checklist: Whether to include the general PR review checklist
            include_java_checklist: Whether to include the Java-specific checklist
            run_improvement_loop: Whether to run the iterative improvement loop
            
        Returns:
            Dictionary containing the review results
        """
        # Get pull request details
        pr_details = self.azure_client.get_pull_request(pull_request_id)
        repository_id = pr_details['repository']['id']
        
        # Get iterations
        iterations = self.azure_client.get_pull_request_iterations(repository_id, pull_request_id)
        
        # Determine which iterations to review
        if review_all:
            iterations_to_review = iterations
        elif iteration_id is not None:
            iterations_to_review = [iter for iter in iterations if iter['id'] == iteration_id]
            if not iterations_to_review:
                raise ValueError(f"Iteration {iteration_id} not found")
        else:
            # Default to the latest iteration
            iterations_to_review = [iterations[-1]]
        
        # Review each iteration
        results = {
            'pull_request': pr_details,
            'iterations': []
        }
        
        for iteration in iterations_to_review:
            iteration_result = self._review_iteration(
                repository_id, 
                pull_request_id, 
                iteration,
                include_checklist,
                include_java_checklist,
                run_improvement_loop
            )
            results['iterations'].append(iteration_result)
        
        # Generate cross-iteration analysis if reviewing multiple iterations
        if len(iterations_to_review) > 1:
            cross_iteration_analysis = self._generate_cross_iteration_analysis(results['iterations'])
            results['cross_iteration_analysis'] = cross_iteration_analysis
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = "reviews"
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, f"pr_{pull_request_id}_{timestamp}.json")
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def _review_iteration(self, repository_id, pull_request_id, iteration, 
                         include_checklist=False, include_java_checklist=False,
                         run_improvement_loop=False):
        """Review a specific iteration of a pull request.
        
        Args:
            repository_id: The ID of the repository
            pull_request_id: The ID of the pull request
            iteration: The iteration details
            include_checklist: Whether to include the general PR review checklist
            include_java_checklist: Whether to include the Java-specific checklist
            run_improvement_loop: Whether to run the iterative improvement loop
            
        Returns:
            Dictionary containing the review results for this iteration
        """
        iteration_id = iteration['id']
        print(f"Reviewing iteration {iteration_id}")
        
        # Get changes for this iteration
        changes = self.azure_client.get_pull_request_changes(repository_id, pull_request_id, iteration_id)
        
        # Get commits for this iteration
        commits = self.azure_client.get_pull_request_commits(repository_id, pull_request_id, iteration_id)
        
        # Review each changed file
        file_reviews = []
        has_java_files = False
        
        for change in changes:
            if change['changeType'] == 'Edit':
                file_path = change['item']['path']
                
                # Check if this is a Java file
                if file_path.endswith('.java'):
                    has_java_files = True
                
                # Skip binary files, test files, etc.
                if self._should_skip_file(file_path):
                    print(f"Skipping file: {file_path}")
                    continue
                
                print(f"Reviewing file: {file_path}")
                
                # Get the old and new content
                old_commit_id = change.get('sourceServerItem', {}).get('commitId')
                new_commit_id = change['item']['commitId']
                
                try:
                    old_content = self.azure_client.get_file_content(repository_id, old_commit_id, file_path) if old_commit_id else ""
                    new_content = self.azure_client.get_file_content(repository_id, new_commit_id, file_path)
                    
                    # Generate coder analysis
                    coder_analysis = self.coder_agent.explain_changes(file_path, old_content, new_content)
                    
                    # Generate reviewer analysis
                    reviewer_analysis = self.reviewer_agent.review_changes(file_path, old_content, new_content, coder_analysis)
                    
                    # Post comments to PR if enabled
                    if self.auto_post_comments:
                        self._post_file_review_comments(repository_id, pull_request_id, file_path, reviewer_analysis, iteration_id)
                    
                    # Run improvement loop if enabled
                    improvement_result = None
                    if run_improvement_loop:
                        improvement_result = self.improvement_loop.improve_code(
                            pull_request_id,
                            file_path,
                            old_content,
                            new_content,
                            post_comments=self.post_comments
                        )
                    
                    # Add to file reviews
                    file_review = {
                        'file_path': file_path,
                        'old_content': old_content,
                        'new_content': new_content,
                        'coder_analysis': coder_analysis,
                        'reviewer_analysis': reviewer_analysis
                    }
                    
                    if improvement_result:
                        file_review['improvement_result'] = improvement_result
                        
                    file_reviews.append(file_review)
                except Exception as e:
                    print(f"Error reviewing file {file_path}: {str(e)}")
                    file_reviews.append({
                        'file_path': file_path,
                        'error': str(e)
                    })
        
        # Generate summary review
        summary_review = self._generate_summary_review(file_reviews, include_checklist, include_java_checklist and has_java_files)
        
        # Post summary comment to PR if enabled
        if self.post_comments:
            self._post_summary_comment(repository_id, pull_request_id, summary_review)
        
        # Return iteration review results
        return {
            'iteration_id': iteration_id,
            'commits': commits,
            'file_reviews': file_reviews,
            'summary_review': summary_review
        }
    
    def _generate_summary_review(self, file_reviews, include_checklist=False, include_java_checklist=False):
        """Generate a summary review for all files.
        
        Args:
            file_reviews: List of file reviews
            include_checklist: Whether to include the general PR review checklist
            include_java_checklist: Whether to include the Java-specific checklist
            
        Returns:
            Summary review text
        """
        # Extract key points from each file review
        summary = "# Pull Request Review Summary\n\n"
        
        # Add overview
        summary += "## Overview\n\n"
        summary += f"Reviewed {len(file_reviews)} files.\n\n"
        
        # Add file summaries
        summary += "## File Summaries\n\n"
        
        for file_review in file_reviews:
            file_path = file_review.get('file_path', 'Unknown file')
            reviewer_analysis = file_review.get('reviewer_analysis', '')
            
            summary += f"### {file_path}\n\n"
            
            # Extract first paragraph or key points
            if reviewer_analysis:
                lines = reviewer_analysis.split('\n')
                summary_lines = []
                for line in lines:
                    if line.startswith('## Summary'):
                        # Found the summary section, extract it
                        summary_index = lines.index(line)
                        for i in range(summary_index + 1, len(lines)):
                            if lines[i].startswith('## '):
                                break
                            if lines[i].strip():
                                summary_lines.append(lines[i])
                        break
                
                if summary_lines:
                    summary += "\n".join(summary_lines) + "\n\n"
                else:
                    # No explicit summary section, use the first few non-empty lines
                    non_empty_lines = [line for line in lines if line.strip() and not line.startswith('#')]
                    summary += "\n".join(non_empty_lines[:3]) + "\n\n"
            
            # Check if there were improvements
            if 'improvement_result' in file_review:
                improvement = file_review['improvement_result']
                iterations = improvement.get('iterations_completed', 0)
                all_resolved = improvement.get('all_issues_resolved', False)
                
                summary += f"**Iterative Improvements:** {iterations} iterations"
                if all_resolved:
                    summary += ", all issues resolved.\n\n"
                else:
                    summary += ", some issues remain.\n\n"
        
        # Add checklists if requested
        if include_checklist:
            summary += "\n\n" + self.checklist.get_general_checklist()
        
        if include_java_checklist:
            summary += "\n\n" + self.checklist.get_java_checklist()
        
        return summary
    
    def _generate_cross_iteration_analysis(self, iteration_results):
        """Generate analysis comparing changes across iterations.
        
        Args:
            iteration_results: List of iteration review results
            
        Returns:
            Cross-iteration analysis text
        """
        analysis = "# Cross-Iteration Analysis\n\n"
        
        # Add overview
        analysis += "## Overview\n\n"
        analysis += f"Analyzed {len(iteration_results)} iterations of this pull request.\n\n"
        
        # Track files across iterations
        files_by_iteration = {}
        all_files = set()
        
        for iteration in iteration_results:
            iteration_id = iteration['iteration_id']
            files_by_iteration[iteration_id] = {}
            
            for file_review in iteration['file_reviews']:
                file_path = file_review.get('file_path')
                if file_path:
                    all_files.add(file_path)
                    files_by_iteration[iteration_id][file_path] = file_review
        
        # Analyze changes for each file across iterations
        analysis += "## File Evolution\n\n"
        
        for file_path in sorted(all_files):
            analysis += f"### {file_path}\n\n"
            
            # Track which iterations modified this file
            iterations_with_file = []
            for iteration_id, files in files_by_iteration.items():
                if file_path in files:
                    iterations_with_file.append(iteration_id)
            
            analysis += f"Modified in iterations: {', '.join(map(str, iterations_with_file))}\n\n"
            
            # If the file appears in multiple iterations, analyze the evolution
            if len(iterations_with_file) > 1:
                analysis += "#### Evolution Summary\n\n"
                
                # Compare the first and last iterations
                first_iteration = min(iterations_with_file)
                last_iteration = max(iterations_with_file)
                
                first_review = files_by_iteration[first_iteration][file_path]
                last_review = files_by_iteration[last_iteration][file_path]
                
                # Extract key points from reviewer analysis
                first_analysis = first_review.get('reviewer_analysis', '')
                last_analysis = last_review.get('reviewer_analysis', '')
                
                # Simple heuristic to check if issues were resolved
                first_issues = self._extract_issues_from_analysis(first_analysis)
                last_issues = self._extract_issues_from_analysis(last_analysis)
                
                resolved_issues = []
                for issue in first_issues:
                    if issue not in last_issues:
                        resolved_issues.append(issue)
                
                new_issues = []
                for issue in last_issues:
                    if issue not in first_issues:
                        new_issues.append(issue)
                
                # Add analysis
                if resolved_issues:
                    analysis += "**Resolved Issues:**\n\n"
                    for issue in resolved_issues:
                        analysis += f"- {issue}\n"
                    analysis += "\n"
                
                if new_issues:
                    analysis += "**New Issues:**\n\n"
                    for issue in new_issues:
                        analysis += f"- {issue}\n"
                    analysis += "\n"
                
                if not resolved_issues and not new_issues:
                    analysis += "No significant changes in issues between iterations.\n\n"
        
        return analysis
    
    def _extract_issues_from_analysis(self, analysis):
        """Extract issues from reviewer analysis.
        
        Args:
            analysis: Reviewer analysis text
            
        Returns:
            List of issues
        """
        issues = []
        lines = analysis.split('\n')
        
        for i, line in enumerate(lines):
            if line.strip().startswith('- '):
                # This is likely an issue
                issue = line.strip()[2:]  # Remove the "- " prefix
                
                # Check if the next lines are part of this issue (indented)
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or lines[j].startswith('  ')):
                    if lines[j].strip():
                        issue += " " + lines[j].strip()
                    j += 1
                
                issues.append(issue)
        
        return issues
    
    def _post_summary_comment(self, repository_id, pull_request_id, summary_review):
        """Post a summary comment to the pull request.
        
        Args:
            repository_id: The ID of the repository
            pull_request_id: The ID of the pull request
            summary_review: Summary review text
        """
        try:
            # Add a header to indicate this is an AI review
            comment = "# AI Code Review Summary\n\n"
            comment += summary_review
            
            # Post the comment
            self.azure_client.add_pull_request_thread(repository_id, pull_request_id, comment)
            print("Posted summary comment to PR")
        except Exception as e:
            print(f"Error posting summary comment: {str(e)}")
    
    def _post_file_review_comments(self, repository_id, pull_request_id, file_path, reviewer_analysis, iteration_id):
        """Post file review comments to the pull request.
        
        Args:
            repository_id: The ID of the repository
            pull_request_id: The ID of the pull request
            file_path: Path to the file being reviewed
            reviewer_analysis: Analysis from the reviewer agent
            iteration_id: The ID of the iteration
        """
        try:
            # Parse the reviewer analysis to extract issues and their locations
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
            
            # Post a summary comment for the file
            summary_content = f"## AI Code Review - Iteration {iteration_id}\n\n"
            summary_content += f"Review for file: `{file_path}`\n\n"
            summary_content += "### Summary\n\n"
            
            # Add a brief summary from the first few lines of the review
            summary_lines = [line for line in lines[:10] if not line.startswith('#') and line.strip()]
            if summary_lines:
                summary_content += "\n".join(summary_lines) + "\n\n"
            
            # Add issue count
            summary_content += f"\n\n**Found {len(issues)} issues to address in this file.**"
            
            # Post the summary comment (not attached to a specific line)
            self.azure_client.add_pull_request_thread(repository_id, pull_request_id, summary_content)
            
            # Post individual comments for each issue
            for issue in issues:
                if not issue.get('line'):
                    continue
                    
                line_number = issue['line']
                issue_text = issue['text']
                section = issue['section']
                
                # Format the comment
                comment_content = f"## {section}\n\n{issue_text}"
                
                # Post the comment
                self.azure_client.add_pull_request_thread(
                    repository_id,
                    pull_request_id,
                    comment_content,
                    file_path,
                    line_number
                )
            
            print(f"Posted {len(issues)} comments for file {file_path}")
        except Exception as e:
            print(f"Error posting file review comments: {str(e)}")
    
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
