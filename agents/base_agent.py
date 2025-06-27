import os
import openai
from config import OPENAI_API_KEY
from local_llm_client import LocalLLMClient

class BaseAgent:
    """Base class for AI agents."""
    
    def __init__(self, model_name, use_local_llm=False):
        """Initialize the agent with the specified model.
        
        Args:
            model_name: Name of the model to use
            use_local_llm: Whether to use a local LLM instead of OpenAI
        """
        self.use_local_llm = use_local_llm
        self.model_name = model_name
        
        if not self.use_local_llm:
            openai.api_key = OPENAI_API_KEY
        else:
            # Initialize local LLM client
            self.local_llm = LocalLLMClient(
                api_base_url=os.getenv("LOCAL_LLM_API_URL"),
                model_name=os.getenv("LOCAL_LLM_MODEL")
            )
        
    def generate_response(self, prompt, system_message=None, temperature=0.7, max_tokens=2000):
        """Generate a response from the AI model.
        
        Args:
            prompt: The prompt to send to the model
            system_message: Optional system message for the model
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            The generated text response
        """
        if not self.use_local_llm:
            # Use OpenAI API
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
        else:
            # Use local LLM
            return self.local_llm.generate_response(
                prompt=prompt,
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens
            )
