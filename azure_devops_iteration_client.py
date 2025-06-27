from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from config import AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, AZURE_DEVOPS_PAT
import base64

class AzureDevOpsIterationClient:
    """Client for working with Azure DevOps PR iterations."""
    
    def __init__(self):
        """Initialize the Azure DevOps client with credentials from config."""
        credentials = BasicAuthentication('', AZURE_DEVOPS_PAT)
        organization_url = f"https://dev.azure.com/{AZURE_DEVOPS_ORG}"
        self.connection = Connection(base_url=organization_url, creds=credentials)
        self.git_client = self.connection.clients.get_git_client()
        self.project = AZURE_DEVOPS_PROJECT

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
