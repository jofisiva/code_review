# Local LLM Integration Guide

This guide explains how to use local Large Language Models (LLMs) with the AI Code Review System as an alternative to OpenAI's API.

## Overview

The AI Code Review System now supports using local LLM models through various server implementations:

- **Ollama** (default)
- **LM Studio**
- **LocalAI**
- **Text Generation WebUI**

This feature allows you to:
- Run the system offline without internet connectivity
- Use custom or specialized models
- Avoid OpenAI API costs
- Maintain privacy by keeping all data local

## Setup Instructions

### 1. Install a Local LLM Server

#### Ollama (Recommended)

1. Download and install Ollama from [ollama.ai](https://ollama.ai)
2. Pull a model:
   ```bash
   ollama pull llama3
   ```
   or for smaller models:
   ```bash
   ollama pull llama3.2:1b
   ```

#### Other Supported Servers

- **LM Studio**: Download from [lmstudio.ai](https://lmstudio.ai)
- **LocalAI**: Follow installation instructions at [github.com/go-skynet/LocalAI](https://github.com/go-skynet/LocalAI)
- **Text Generation WebUI**: Follow setup at [github.com/oobabooga/text-generation-webui](https://github.com/oobabooga/text-generation-webui)

### 2. Configure the System

Edit your `.env` file to enable local LLM usage:

```bash
# Local LLM Configuration
USE_LOCAL_LLM=true
LOCAL_LLM_API_URL=http://localhost:11434
LOCAL_LLM_API_TYPE=ollama
LOCAL_LLM_MODEL=llama3
```

#### Configuration Options

- `USE_LOCAL_LLM`: Set to `true` to enable local LLM by default
- `LOCAL_LLM_API_URL`: The URL of your local LLM server
  - Ollama: `http://localhost:11434`
  - LM Studio: `http://localhost:1234`
  - LocalAI: `http://localhost:8080`
  - Text Generation WebUI: `http://localhost:5000`
- `LOCAL_LLM_API_TYPE`: The type of API (`ollama`, `lmstudio`, `localai`, or `tgwui`)
- `LOCAL_LLM_MODEL`: The model name to use (must be available on your local server)

### 3. Testing the Setup

The system includes test scripts to verify your local LLM setup:

1. Test basic connectivity:
   ```bash
   python test_ollama.py
   ```

2. Test code review functionality:
   ```bash
   python test_code_review_with_ollama.py
   ```

## Using Local LLM in the Web Interface

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to `http://localhost:5000`

3. When starting a new code review:
   - Check the "Use Local LLM" option (if not already enabled by default in your `.env`)
   - Enter the Azure DevOps Pull Request ID
   - Click "Start Review"

## Recommended Models

For optimal performance with code reviews, we recommend:

- **Ollama**: 
  - `llama3` (best quality)
  - `llama3.2:1b` (faster, smaller)
  - `codellama:7b` (code-specific)
  
- **Other providers**:
  - Models with at least 7B parameters for better code understanding
  - Code-specific models when available

## Troubleshooting

### Common Issues

1. **"Connection refused" error**:
   - Ensure your local LLM server is running
   - Verify the `LOCAL_LLM_API_URL` is correct

2. **"Model not found" error**:
   - Verify you've pulled/downloaded the model specified in `LOCAL_LLM_MODEL`
   - Check the model name matches exactly what's on your server

3. **Poor quality reviews**:
   - Try a larger model if available
   - Adjust temperature settings in `local_llm_client.py`
   - Consider using a code-specific model

4. **Slow performance**:
   - Use a smaller model
   - Reduce the maximum tokens in `local_llm_client.py`
   - Consider hardware with GPU acceleration

## Implementation Details

The local LLM integration is implemented through:

- `local_llm_client.py`: Main client for communicating with local LLM servers
- `agents/base_agent.py`: Modified to support both OpenAI and local LLMs
- `config.py`: Environment variable handling for local LLM settings

The system uses HTTP REST calls to communicate with local LLM servers, formatting prompts and processing responses to maintain compatibility with the existing agent architecture.

## Performance Considerations

Local LLMs typically have different performance characteristics compared to OpenAI models:

- **Response quality**: May vary based on model size and training
- **Speed**: Depends on your hardware and model size
- **Context window**: Often smaller than OpenAI models
- **Specialization**: Some models may be better at code than others

Adjust your expectations and model selection accordingly.
