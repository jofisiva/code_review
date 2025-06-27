from agents.base_agent import BaseAgent
from config import OPENAI_MODEL_CODER

class CoderAgent(BaseAgent):
    """Agent that acts as a coder, analyzing code changes and explaining them."""
    
    def __init__(self):
        """Initialize the coder agent with the configured model."""
        super().__init__(OPENAI_MODEL_CODER)
        self.system_message = """
        You are an expert software developer tasked with explaining code changes in a pull request.
        Your job is to:
        1. Understand the changes made in the code
        2. Explain the purpose and functionality of the changes
        3. Identify any potential issues or improvements
        4. Provide context about why these changes might have been made
        
        Focus on being clear, concise, and technically accurate. Explain the changes as if you were
        the developer who made them, providing insight into your thought process.
        """
    
    def analyze_file_changes(self, file_path, old_content, new_content):
        """Analyze changes between old and new versions of a file."""
        prompt = f"""
        I need you to analyze the changes made to the file: {file_path}
        
        OLD VERSION:
        ```
        {old_content if old_content else 'This is a new file.'}
        ```
        
        NEW VERSION:
        ```
        {new_content}
        ```
        
        Please explain:
        1. What changes were made to the file?
        2. What is the purpose of these changes?
        3. Are there any potential issues or improvements you can identify?
        """
        
        return self.generate_response(prompt, self.system_message, temperature=0.3)
    
    def explain_implementation(self, code_snippet, context=None):
        """Explain the implementation details of a specific code snippet."""
        prompt = f"""
        Please explain the implementation details of this code:
        
        ```
        {code_snippet}
        ```
        """
        
        if context:
            prompt += f"\nAdditional context: {context}"
        
        return self.generate_response(prompt, self.system_message, temperature=0.3)
