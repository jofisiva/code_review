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

# Application Configuration
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
