"""
Client for interacting with local LLM servers like Ollama.
"""
import os
import json
import requests
from typing import Dict, Any, Optional, List

class LocalLLMClient:
    """
    Client for interacting with local LLM servers like Ollama, LM Studio, etc.
    """
    
    def __init__(self, api_url=None, api_type=None, model=None):
        """Initialize the local LLM client.
        
        Args:
            api_url: URL of the local LLM API server
            api_type: Type of API (ollama, openai, etc.)
            model: Model name to use
        """
        # Load from environment or use defaults
        self.api_url = api_url or os.getenv('LOCAL_LLM_API_URL', 'http://localhost:11434')
        self.api_type = api_type or os.getenv('LOCAL_LLM_API_TYPE', 'ollama')
        self.model = model or os.getenv('LOCAL_LLM_MODEL', 'llama3')
        
        # Remove trailing slash from API URL if present
        if self.api_url.endswith('/'):
            self.api_url = self.api_url[:-1]
    
    def generate(self, prompt: str, system_prompt: Optional[str] = None, 
                temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Generate text from the local LLM.
        
        Args:
            prompt: The prompt to send to the LLM
            system_prompt: Optional system prompt for models that support it
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated text
        """
        if self.api_type.lower() == 'ollama':
            return self._generate_ollama(prompt, system_prompt, temperature, max_tokens)
        elif self.api_type.lower() in ['openai', 'lmstudio', 'localai']:
            return self._generate_openai_compatible(prompt, system_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported API type: {self.api_type}")
    
    def _generate_ollama(self, prompt: str, system_prompt: Optional[str] = None, 
                        temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Generate text using Ollama API.
        
        Args:
            prompt: The prompt to send to the LLM
            system_prompt: Optional system prompt
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated text
        """
        url = f"{self.api_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            # Ollama returns streaming responses, we need to parse them
            lines = response.text.strip().split('\n')
            full_response = ""
            
            for line in lines:
                try:
                    data = json.loads(line)
                    if 'response' in data:
                        full_response += data['response']
                except json.JSONDecodeError:
                    continue
            
            return full_response
        except Exception as e:
            print(f"Error generating text with Ollama: {str(e)}")
            return f"Error: {str(e)}"
    
    def _generate_openai_compatible(self, prompt: str, system_prompt: Optional[str] = None, 
                                  temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Generate text using OpenAI-compatible API.
        
        Args:
            prompt: The prompt to send to the LLM
            system_prompt: Optional system prompt
            temperature: Temperature parameter for generation
            max_tokens: Maximum number of tokens to generate
            
        Returns:
            Generated text
        """
        url = f"{self.api_url}/v1/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            if 'choices' in data and len(data['choices']) > 0:
                return data['choices'][0]['message']['content']
            else:
                return "Error: No response generated"
        except Exception as e:
            print(f"Error generating text with OpenAI-compatible API: {str(e)}")
            return f"Error: {str(e)}"
