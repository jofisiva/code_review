from agents.base_agent import BaseAgent
from config import OPENAI_MODEL_REVIEWER, USE_LOCAL_LLM

class ReviewerAgent(BaseAgent):
    """Agent that acts as a code reviewer, providing feedback on code changes."""
    
    def __init__(self, use_local_llm: bool = False):
        """Initialize the reviewer agent with the configured model.
        
        Args:
            use_local_llm: Whether to use a local LLM instead of OpenAI
        """
        super().__init__(OPENAI_MODEL_REVIEWER, use_local_llm=use_local_llm or USE_LOCAL_LLM)
        self.system_message = """
        You are an expert code reviewer with years of experience in software development.
        Your job is to:
        1. Review code changes critically and thoroughly
        2. Identify potential bugs, security issues, and performance problems
        3. Suggest improvements to code quality, readability, and maintainability
        4. Ensure the code follows best practices and design patterns
        5. Provide constructive feedback that helps the developer improve
        
        Be thorough but fair in your assessment. Always provide specific suggestions
        for improvement rather than just pointing out problems.
        """
    
    def review_file_changes(self, file_path, old_content, new_content, coder_explanation=None):
        """Review changes between old and new versions of a file."""
        prompt = f"""
        I need you to review the changes made to the file: {file_path}
        
        OLD VERSION:
        ```
        {old_content if old_content else 'This is a new file.'}
        ```
        
        NEW VERSION:
        ```
        {new_content}
        ```
        
        {f"The developer explains these changes as follows: {coder_explanation}" if coder_explanation else ""}
        
        Please provide a thorough code review addressing:
        1. Code quality and readability
        2. Potential bugs or edge cases
        3. Security concerns
        4. Performance considerations
        5. Adherence to best practices
        6. Specific suggestions for improvement
        
        Format your review as markdown with sections for different categories of feedback.
        """
        
        return self.generate_response(prompt, self.system_message, temperature=0.4, max_tokens=2500)
    
    def provide_summary_review(self, all_file_reviews):
        """Provide an overall summary review of all file changes."""
        prompt = f"""
        I need you to provide an overall summary review of a pull request based on the individual file reviews.
        
        Here are the file reviews:
        
        {all_file_reviews}
        
        Please provide:
        1. A summary of the key findings across all files
        2. Overall assessment of the code quality
        3. Major concerns that should be addressed before merging
        4. Positive aspects of the changes
        5. A final recommendation (Approve, Request Changes, or Comment)
        
        Format your summary as markdown.
        """
        
        return self.generate_response(prompt, self.system_message, temperature=0.4)
