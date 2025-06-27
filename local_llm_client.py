"""
Local LLM Client Module

This module provides a client for interacting with locally hosted Large Language Models (LLMs).
It supports various local model APIs including Ollama, LM Studio, LocalAI, and Text Generation WebUI.
The module also includes a LangChain integration for using local LLMs with LangChain workflows.

Environment Variables:
    LOCAL_LLM_API_URL: Base URL for the local LLM API (default: http://localhost:11434)
    LOCAL_LLM_MODEL: Name of the model to use (default: llama3)
    LOCAL_LLM_API_TYPE: Type of API to use (default: ollama)
"""

import os
import requests
import json
import logging
from typing import Dict, List, Any, Optional, Union
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalLLMClient:
    """
    Client for interacting with locally hosted LLM models.
    
    This class provides a unified interface to interact with various local LLM APIs,
    abstracting away the differences between them. It supports:
    - Ollama: https://github.com/ollama/ollama
    - LM Studio: https://lmstudio.ai
    - LocalAI: https://github.com/go-skynet/LocalAI
    - Text Generation WebUI: https://github.com/oobabooga/text-generation-webui
    
    The client automatically loads configuration from environment variables
    but can also be configured directly through constructor parameters.
    """
    
    def __init__(self, api_base_url=None, model_name=None, api_type=None):
        """
        Initialize the local LLM client.
        
        Args:
            api_base_url (str, optional): Base URL for the local LLM API.
                Defaults to LOCAL_LLM_API_URL env var or "http://localhost:11434".
            model_name (str, optional): Name of the model to use.
                Defaults to LOCAL_LLM_MODEL env var or "llama3".
            api_type (str, optional): Type of API to use (ollama, lmstudio, localai, textgen).
                Defaults to LOCAL_LLM_API_TYPE env var or "ollama".
        """
        self.api_base_url = api_base_url or os.getenv("LOCAL_LLM_API_URL", "http://localhost:11434")
        self.model_name = model_name or os.getenv("LOCAL_LLM_MODEL", "llama3")
        self.api_type = (api_type or os.getenv("LOCAL_LLM_API_TYPE", "ollama")).lower()
        
        logger.info(f"Initialized LocalLLMClient with API type: {self.api_type}, model: {self.model_name}")
        
    def generate_response(self, prompt: str, system_message: Optional[str] = None, 
                          temperature: float = 0.7, max_tokens: int = 4000) -> str:
        """
        Generate a response from the local LLM.
        
        Args:
            prompt (str): The user prompt to send to the model.
            system_message (str, optional): System message for models that support it.
                Used to set context or instructions for the model.
            temperature (float, optional): Temperature parameter for controlling randomness.
                Higher values (e.g., 0.8) make output more random, lower values (e.g., 0.2)
                make it more deterministic. Defaults to 0.7.
            max_tokens (int, optional): Maximum tokens to generate in the response.
                Defaults to 4000.
            
        Returns:
            str: The generated text response from the model.
            
        Raises:
            ValueError: If the configured API type is not supported.
            ConnectionError: If the local LLM server cannot be reached.
        """
        logger.debug(f"Generating response with {self.api_type} API")
        logger.debug(f"Prompt: {prompt[:100]}..." if len(prompt) > 100 else f"Prompt: {prompt}")
        
        try:
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
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Could not connect to local LLM server at {self.api_base_url}. Is it running?"
            logger.error(error_msg)
            return f"Error: {error_msg}"
    
    def _generate_ollama(self, prompt: str, system_message: Optional[str], 
                        temperature: float, max_tokens: int) -> str:
        """Generate a response using Ollama API
        
        Args:
            prompt: The user prompt to send to the model
            system_message: Optional system message for context setting
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            The generated text response
            
        Documentation: https://github.com/ollama/ollama/blob/main/docs/api.md
        """
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
            logger.debug(f"Sending request to Ollama API: {url}")
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json().get("response", "")
            logger.debug(f"Received response from Ollama ({len(result)} chars)")
            return result
        except requests.exceptions.Timeout:
            error_msg = "Request to Ollama timed out after 60 seconds"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error from Ollama API: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Error generating response from Ollama: {str(e)}"
            logger.error(error_msg)
            return f"Error: Could not generate response from local LLM. {str(e)}"
    
    def _generate_lmstudio(self, prompt: str, system_message: Optional[str], 
                          temperature: float, max_tokens: int) -> str:
        """Generate a response using LM Studio API
        
        Args:
            prompt: The user prompt to send to the model
            system_message: Optional system message for context setting
            temperature: Temperature parameter for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            The generated text response
            
        Documentation: https://lmstudio.ai/docs/api-reference
        """
        url = f"{self.api_base_url}/v1/chat/completions"
        
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            logger.debug(f"Sending request to LM Studio API: {url}")
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            logger.debug(f"Received response from LM Studio ({len(result)} chars)")
            return result
        except requests.exceptions.Timeout:
            error_msg = "Request to LM Studio timed out after 60 seconds"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP error from LM Studio API: {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
        except Exception as e:
            error_msg = f"Error generating response from LM Studio: {str(e)}"
            logger.error(error_msg)
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
    
    This class provides a LangChain-compatible wrapper around the LocalLLMClient,
    allowing local LLMs to be used in LangChain workflows, chains, and agents.
    
    Example:
        ```python
        from local_llm_client import LocalLLMLangChain
        
        # Create a LangChain-compatible local LLM
        llm = LocalLLMLangChain(
            api_type="ollama",
            model_name="llama3",
            temperature=0.7
        )
        
        # Use it in a LangChain workflow
        result = llm.invoke("Write a function to calculate fibonacci numbers")
        ```
    """
    
    api_base_url: str = None
    model_name: str = None
    api_type: str = "ollama"
    temperature: float = 0.7
    max_tokens: int = 4000
    
    def __init__(self, **kwargs):
        """Initialize the LangChain LLM wrapper
        
        Args:
            api_base_url (str, optional): Base URL for the local LLM API
            model_name (str, optional): Name of the model to use
            api_type (str, optional): Type of API to use (ollama, lmstudio, localai, textgen)
            temperature (float, optional): Temperature parameter for generation
            max_tokens (int, optional): Maximum tokens to generate
        """
        super().__init__(**kwargs)
        self.client = LocalLLMClient(
            api_base_url=self.api_base_url or os.getenv("LOCAL_LLM_API_URL", "http://localhost:11434"),
            model_name=self.model_name or os.getenv("LOCAL_LLM_MODEL", "llama3"),
            api_type=self.api_type or os.getenv("LOCAL_LLM_API_TYPE", "ollama").lower()
        )
        
        logger.info(f"Initialized LocalLLMLangChain with model: {self.model_name}")
        
    @property
    def _llm_type(self) -> str:
        """Return the type of LLM
        
        Returns:
            str: The identifier for this LLM type
        """
        return "local_llm"
    
    def _call(self, prompt: str, stop: Optional[List[str]] = None, 
              run_manager: Optional[CallbackManagerForLLMRun] = None, 
              **kwargs) -> str:
        """Generate text from the local LLM
        
        Args:
            prompt (str): The prompt to send to the model
            stop (List[str], optional): List of stop sequences to halt generation
            run_manager (CallbackManagerForLLMRun, optional): Callback manager for LLM run
            **kwargs: Additional keyword arguments
                system_message (str, optional): System message for the model
                temperature (float, optional): Temperature parameter
                max_tokens (int, optional): Maximum tokens to generate
                
        Returns:
            str: The generated text response
        """
        system_message = kwargs.get("system_message")
        temperature = kwargs.get("temperature", self.temperature)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        
        if run_manager:
            run_manager.on_text("Generating response from local LLM...\n")
            
        result = self.client.generate_response(
            prompt=prompt,
            system_message=system_message,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Handle stop sequences if provided
        if stop and result:
            for stop_seq in stop:
                if stop_seq in result:
                    result = result[:result.index(stop_seq)]
                    
        return result
