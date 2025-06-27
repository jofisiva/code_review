import openai
from config import OPENAI_API_KEY

class BaseAgent:
    """Base class for AI agents."""
    
    def __init__(self, model_name):
        """Initialize the agent with the specified model."""
        openai.api_key = OPENAI_API_KEY
        self.model_name = model_name
        
    def generate_response(self, prompt, system_message=None, temperature=0.7, max_tokens=2000):
        """Generate a response from the AI model."""
        messages = []
        
        if system_message:
            messages.append({"role": "system", "content": system_message})
            
        messages.append({"role": "user", "content": prompt})
        
        response = openai.ChatCompletion.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
