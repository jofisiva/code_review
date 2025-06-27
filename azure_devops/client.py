"""
Azure DevOps Iteration Client for accessing PR data across multiple iterations.
"""
import os
import requests
import base64
from config import get_config

class AzureDevOpsIterationClient:
    """
    Client for interacting with Azure DevOps API, specifically for handling
    pull request iterations and their associated data.
    """
    
    def __init__(self, organization=None, project=None, personal_access_token=None):
        """Initialize the Azure DevOps client with credentials."""
        config = get_config()
        self.organization = organization or config.get('AZURE_DEVOPS_ORG')
        self.project = project or config.get('AZURE_DEVOPS_PROJECT')
        self.personal_access_token = personal_access_token or config.get('AZURE_DEVOPS_PAT')
        
        if not all([self.organization, self.project, self.personal_access_token]):
            raise ValueError("Azure DevOps organization, project, and PAT are required")
            
        self.base_url = f"https://dev.azure.com/{self.organization}/{self.project}/_apis/git"
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {base64.b64encode((":" + self.personal_access_token).encode()).decode()}'
        }
    
    def get_pull_request(self, pull_request_id):
        """Get pull request details."""
        url = f"{self.base_url}/pullrequests/{pull_request_id}?api-version=6.0"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_pull_request_iterations(self, repository_id, pull_request_id):
        """Get all iterations of a pull request."""
        url = f"{self.base_url}/repositories/{repository_id}/pullRequests/{pull_request_id}/iterations?api-version=6.0"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()['value']
    
    def get_pull_request_changes(self, repository_id, pull_request_id, iteration_id=None):
        """Get changes for a specific iteration of a pull request."""
        url = f"{self.base_url}/repositories/{repository_id}/pullRequests/{pull_request_id}/iterations"
        if iteration_id is not None:
            url += f"/{iteration_id}"
        url += "/changes?api-version=6.0"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()['changes']
    
    def get_pull_request_commits(self, repository_id, pull_request_id, iteration_id=None):
        """Get commits for a specific iteration of a pull request."""
        url = f"{self.base_url}/repositories/{repository_id}/pullRequests/{pull_request_id}/iterations"
        if iteration_id is not None:
            url += f"/{iteration_id}"
        url += "/commits?api-version=6.0"
        
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()['value']
    
    def get_file_content(self, repository_id, commit_id, file_path):
        """Get file content at a specific commit."""
        url = f"{self.base_url}/repositories/{repository_id}/items"
        params = {
            'path': file_path,
            'versionDescriptor.version': commit_id,
            'versionDescriptor.versionType': 'commit',
            'includeContent': 'true',
            'api-version': '6.0'
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()['content']
    
    def get_pull_request_threads(self, repository_id, pull_request_id):
        """Get all comment threads for a pull request."""
        url = f"{self.base_url}/repositories/{repository_id}/pullRequests/{pull_request_id}/threads?api-version=6.0"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()['value']
    
    def add_pull_request_thread(self, repository_id, pull_request_id, content, file_path=None, line=None, status="active"):
        """Add a new comment thread to a pull request."""
        url = f"{self.base_url}/repositories/{repository_id}/pullRequests/{pull_request_id}/threads?api-version=6.0"
        
        thread_data = {
            "comments": [
                {
                    "parentCommentId": 0,
                    "content": content,
                    "commentType": 1
                }
            ],
            "status": status
        }
        
        if file_path and line:
            thread_data["threadContext"] = {
                "filePath": file_path,
                "rightFileStart": {
                    "line": line,
                    "offset": 1
                },
                "rightFileEnd": {
                    "line": line,
                    "offset": 1
                }
            }
        
        response = requests.post(url, headers=self.headers, json=thread_data)
        response.raise_for_status()
        return response.json()
    
    def add_thread_comment(self, repository_id, pull_request_id, thread_id, content):
        """Add a comment to an existing thread."""
        url = f"{self.base_url}/repositories/{repository_id}/pullRequests/{pull_request_id}/threads/{thread_id}/comments?api-version=6.0"
        
        comment_data = {
            "content": content,
            "parentCommentId": 1,  # Reply to the first comment
            "commentType": 1
        }
        
        response = requests.post(url, headers=self.headers, json=comment_data)
        response.raise_for_status()
        return response.json()
    
    def update_thread_status(self, repository_id, pull_request_id, thread_id, status):
        """Update the status of a thread (active, fixed, pending, etc.)."""
        url = f"{self.base_url}/repositories/{repository_id}/pullRequests/{pull_request_id}/threads/{thread_id}?api-version=6.0"
        
        thread_data = {
            "status": status
        }
        
        response = requests.patch(url, headers=self.headers, json=thread_data)
        response.raise_for_status()
        return response.json()
