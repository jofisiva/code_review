from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from config import AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, AZURE_DEVOPS_PAT
import base64
from typing import Dict, List, Any, Optional, Union

class AzureDevOpsIterationClient:
    """Client for working with Azure DevOps PR iterations."""
    
    def __init__(self):
        """Initialize the Azure DevOps client with credentials from config."""
        credentials = BasicAuthentication('', AZURE_DEVOPS_PAT)
        organization_url = f"https://dev.azure.com/{AZURE_DEVOPS_ORG}"
        self.connection = Connection(base_url=organization_url, creds=credentials)
        self.git_client = self.connection.clients.get_git_client()
        self.project = AZURE_DEVOPS_PROJECT
        # Cache for thread IDs to avoid creating duplicates
        self.thread_cache = {}

    def get_pull_request(self, pull_request_id):
        """Get pull request details by ID."""
        return self.git_client.get_pull_request_by_id(pull_request_id)

    def get_pull_request_iterations(self, pull_request_id):
        """Get all iterations for a pull request."""
        pr = self.get_pull_request(pull_request_id)
        repository_id = pr.repository.id
        
        iterations = self.git_client.get_pull_request_iterations(
            project=self.project,
            repository_id=repository_id,
            pull_request_id=pull_request_id
        )
        
        return iterations
    
    def get_iteration_changes(self, pull_request_id, iteration_id):
        """Get the changes for a specific iteration."""
        pr = self.get_pull_request(pull_request_id)
        repository_id = pr.repository.id
        
        changes = self.git_client.get_pull_request_iteration_changes(
            project=self.project,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            iteration_id=iteration_id
        )
        
        return changes
    
    def get_iteration_commits(self, pull_request_id, iteration_id):
        """Get the commits for a specific iteration."""
        pr = self.get_pull_request(pull_request_id)
        repository_id = pr.repository.id
        
        commits = self.git_client.get_pull_request_iteration_commits(
            project=self.project,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            iteration_id=iteration_id
        )
        
        return commits
    
    def get_file_content_at_iteration(self, repository_id, file_path, commit_id):
        """Get the content of a file at a specific commit."""
        content = self.git_client.get_item_content(
            repository_id=repository_id,
            path=file_path,
            version=commit_id
        )
        
        # Decode the content
        return base64.b64decode(content).decode('utf-8')
    
    def get_iteration_file_changes(self, pull_request_id, iteration_id):
        """Get all files changed in a specific iteration with their content."""
        pr = self.get_pull_request(pull_request_id)
        repository_id = pr.repository.id
        
        # Get changes for the iteration
        changes = self.get_iteration_changes(pull_request_id, iteration_id)
        
        # Get commits for the iteration to find the right commit IDs
        commits = self.get_iteration_commits(pull_request_id, iteration_id)
        
        # Use the last commit in the iteration
        if commits:
            commit_id = commits[-1].commit_id
        else:
            # Fallback to the source commit if no commits found
            commit_id = pr.last_merge_source_commit.commit_id
        
        # Get the target commit ID
        target_commit_id = pr.last_merge_target_commit.commit_id
        
        files = []
        for change in changes.changes:
            if change.change_type == "edit" or change.change_type == "add":
                try:
                    # Get the content of the file in the source branch
                    new_content = self.get_file_content_at_iteration(
                        repository_id=repository_id,
                        file_path=change.item.path,
                        commit_id=commit_id
                    )
                    
                    # Get the content of the file in the target branch if it exists
                    old_content = None
                    if change.change_type == "edit":
                        try:
                            old_content = self.get_file_content_at_iteration(
                                repository_id=repository_id,
                                file_path=change.original_path or change.item.path,
                                commit_id=target_commit_id
                            )
                        except Exception:
                            # File might not exist in target branch
                            pass
                    
                    files.append({
                        'path': change.item.path,
                        'change_type': change.change_type,
                        'new_content': new_content,
                        'old_content': old_content
                    })
                except Exception as e:
                    print(f"Error getting content for {change.item.path}: {str(e)}")
        
        return files
        
    def add_pull_request_thread(self, repository_id, pull_request_id, content, file_path=None, line_number=None, status="active"):
        """Add a thread comment to a pull request.
        
        Args:
            repository_id: The ID of the repository
            pull_request_id: The ID of the pull request
            content: The content of the comment
            file_path: Optional path to the file to comment on
            line_number: Optional line number to comment on
            status: Thread status (active, fixed, etc.)
            
        Returns:
            The created thread
        """
        # Create thread comment parameters
        thread = {
            "comments": [{
                "content": content,
                "parentCommentId": 0,
                "commentType": 1  # Code Comment
            }],
            "status": status
        }
        
        # Add file-specific information if provided
        if file_path:
            thread["threadContext"] = {
                "filePath": file_path
            }
            
            # Add line number if provided
            if line_number is not None:
                thread["threadContext"]["rightFileStart"] = {
                    "line": line_number,
                    "offset": 1
                }
                thread["threadContext"]["rightFileEnd"] = {
                    "line": line_number,
                    "offset": 1
                }
        
        # Create the thread
        created_thread = self.git_client.create_thread(
            comment_thread=thread,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            project=self.project
        )
        
        # Cache the thread ID with a key that includes the file path and content
        cache_key = f"{file_path}:{content[:50]}"
        self.thread_cache[cache_key] = created_thread.id
        
        return created_thread
    
    def update_thread_status(self, repository_id, pull_request_id, thread_id, status="fixed"):
        """Update the status of a thread.
        
        Args:
            repository_id: The ID of the repository
            pull_request_id: The ID of the pull request
            thread_id: The ID of the thread to update
            status: New status (active, fixed, etc.)
            
        Returns:
            The updated thread
        """
        # Get the existing thread
        thread = self.git_client.get_pull_request_thread(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            thread_id=thread_id,
            project=self.project
        )
        
        # Update the status
        thread.status = status
        
        # Update the thread
        updated_thread = self.git_client.update_thread(
            comment_thread=thread,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            thread_id=thread_id,
            project=self.project
        )
        
        return updated_thread
    
    def add_thread_comment(self, repository_id, pull_request_id, thread_id, content):
        """Add a comment to an existing thread.
        
        Args:
            repository_id: The ID of the repository
            pull_request_id: The ID of the pull request
            thread_id: The ID of the thread to comment on
            content: The content of the comment
            
        Returns:
            The created comment
        """
        # Create the comment
        comment = {
            "content": content,
            "parentCommentId": 0,
            "commentType": 1  # Code Comment
        }
        
        # Add the comment to the thread
        created_comment = self.git_client.create_comment(
            comment=comment,
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            thread_id=thread_id,
            project=self.project
        )
        
        return created_comment
    
    def get_pull_request_threads(self, repository_id, pull_request_id):
        """Get all threads for a pull request.
        
        Args:
            repository_id: The ID of the repository
            pull_request_id: The ID of the pull request
            
        Returns:
            List of threads
        """
        return self.git_client.get_threads(
            repository_id=repository_id,
            pull_request_id=pull_request_id,
            project=self.project
        )
