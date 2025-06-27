import os
import requests
import json
from typing import Dict, List, Any, Optional, Union
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

class LocalLLMClient:
    """
    Client for interacting with locally hosted LLM models.
    Supports various local model APIs including:
    - Ollama
    - LM Studio
    - LocalAI
    - Text Generation WebUI
    """
    
    def __init__(self, api_base_url=None, model_name=None):
        """
        Initialize the local LLM client.
        
        Args:
            api_base_url: Base URL for the local LLM API
            model_name: Name of the model to use
        """
        self.api_base_url = api_base_url or os.getenv("LOCAL_LLM_API_URL", "http://localhost:11434")
        self.model_name = model_name or os.getenv("LOCAL_LLM_MODEL", "llama3")
        self.api_type = os.getenv("LOCAL_LLM_API_TYPE", "ollama").lower()
        
    def generate_response(self, prompt: str, system_message: Optional[str] = None, 
                          temperature: float = 0.7, max_tokens: int = 4000) -> str:
        """
        Generate a response from the local LLM.
        
        Args:
            prompt: The user prompt to send to the model
            system_message: Optional system message for models that support it
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            The generated text response
        """
        if self.api_type == "ollama":
            return self._generate_ollama(prompt, system_message, temperature, max_tokens)
        elif self.api_type == "lmstudio":
            return self._generate_lmstudio(prompt, system_message, temperature, max_tokens)
        elif self.api_type == "localai":
            return self._generate_localai(prompt, system_message, temperature, max_tokens)
        elif self.api_type == "textgen":
            return self._generate_textgen(prompt, system_message, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported API type: {self.api_type}")
    
    def _generate_ollama(self, prompt: str, system_message: Optional[str], 
                        temperature: float, max_tokens: int) -> str:
        """Generate a response using Ollama API"""
        url = f"{self.api_base_url}/api/generate"
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "temperature": temperature,
            "max_length": max_tokens,
            "stream": False
        }
        
        if system_message:
            payload["system"] = system_message
            
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("response", "")
        except Exception as e:
            print(f"Error generating response from Ollama: {str(e)}")
            return f"Error: Could not generate response from local LLM. {str(e)}"
    
    def _generate_lmstudio(self, prompt: str, system_message: Optional[str], 
                          temperature: float, max_tokens: int) -> str:
        """Generate a response using LM Studio API"""
        url = f"{self.api_base_url}/v1/completions"
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            print(f"Error generating response from LM Studio: {str(e)}")
            return f"Error: Could not generate response from local LLM. {str(e)}"
    
    def _generate_localai(self, prompt: str, system_message: Optional[str], 
                         temperature: float, max_tokens: int) -> str:
        """Generate a response using LocalAI API"""
        url = f"{self.api_base_url}/v1/chat/completions"
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            print(f"Error generating response from LocalAI: {str(e)}")
            return f"Error: Could not generate response from local LLM. {str(e)}"
    
    def _generate_textgen(self, prompt: str, system_message: Optional[str], 
                         temperature: float, max_tokens: int) -> str:
        """Generate a response using Text Generation WebUI API"""
        url = f"{self.api_base_url}/api/v1/generate"
        
        full_prompt = prompt
        if system_message:
            full_prompt = f"{system_message}\n\n{prompt}"
            
        payload = {
            "prompt": full_prompt,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "do_sample": True,
            "top_p": 0.9,
            "typical_p": 0.9,
            "repetition_penalty": 1.05,
            "encoder_repetition_penalty": 1.0,
            "top_k": 0,
            "min_length": 0,
            "no_repeat_ngram_size": 0,
            "num_beams": 1,
            "penalty_alpha": 0,
            "length_penalty": 1,
            "early_stopping": False,
            "seed": -1,
            "add_bos_token": True,
            "stopping_strings": [],
            "truncation_length": 2048,
            "ban_eos_token": False,
            "skip_special_tokens": True,
            "top_a": 0
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json().get("results", [{}])[0].get("text", "")
        except Exception as e:
            print(f"Error generating response from Text Generation WebUI: {str(e)}")
            return f"Error: Could not generate response from local LLM. {str(e)}"


class LocalLLMLangChain(LLM):
    """
    LangChain integration for local LLM models.
    This allows using local LLMs with LangChain workflows.
    """
    
    api_base_url: str = None
    model_name: str = None
    api_type: str = "ollama"
    temperature: float = 0.7
    max_tokens: int = 4000
    
    def __init__(self, **kwargs):
        """Initialize the LangChain LLM wrapper"""
        super().__init__(**kwargs)
        self.client = LocalLLMClient(
            api_base_url=self.api_base_url or os.getenv("LOCAL_LLM_API_URL", "http://localhost:11434"),
            model_name=self.model_name or os.getenv("LOCAL_LLM_MODEL", "llama3")
        )
        self.client.api_type = self.api_type or os.getenv("LOCAL_LLM_API_TYPE", "ollama").lower()
        
    @property
    def _llm_type(self) -> str:
        """Return the type of LLM"""
        return "local_llm"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, 
              run_manager: Optional[CallbackManagerForLLMRun] = None, 
              **kwargs) -> str:
        """Generate text from the local LLM"""
        system_message = kwargs.get("system_message")
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        return self.client.generate_response(
            prompt=prompt,
            system_message=system_message,
            temperature=temperature,
            max_tokens=max_tokens
        )
