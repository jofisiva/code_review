import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Azure DevOps Configuration
AZURE_DEVOPS_ORG = os.getenv("AZURE_DEVOPS_ORG")
AZURE_DEVOPS_PROJECT = os.getenv("AZURE_DEVOPS_PROJECT")
AZURE_DEVOPS_PAT = os.getenv("AZURE_DEVOPS_PAT")

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_CODER = os.getenv("OPENAI_MODEL_CODER", "gpt-4")
OPENAI_MODEL_REVIEWER = os.getenv("OPENAI_MODEL_REVIEWER", "gpt-4")

# Local LLM Configuration
USE_LOCAL_LLM = os.getenv("USE_LOCAL_LLM", "False").lower() == "true"
LOCAL_LLM_API_URL = os.getenv("LOCAL_LLM_API_URL", "http://localhost:11434")
LOCAL_LLM_API_TYPE = os.getenv("LOCAL_LLM_API_TYPE", "ollama")  # Options: ollama, lmstudio, localai, textgen
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3")

# Application Configuration
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
MAX_IMPROVEMENT_ITERATIONS = int(os.getenv("MAX_IMPROVEMENT_ITERATIONS", "3"))
