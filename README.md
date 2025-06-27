# AI Code Review System for Azure DevOps

A sophisticated code review system that uses multiple AI agents to analyze and review code changes in Azure DevOps pull requests. The system features a Coder agent that explains code changes and a Reviewer agent that provides critical feedback, with results displayed in a comparison view.

## Features

- **Multiple AI Agents**:
  - **Coder Agent**: Analyzes and explains code changes, providing context about why changes were made
  - **Reviewer Agent**: Reviews code critically, identifying bugs, security issues, and suggesting improvements
    - **PR Review Checklist Support**: Optionally append a general and/or Java-specific checklist to every review summary. See below for details.
  - **Iteration Analyzer**: Analyzes changes across multiple iterations of a pull request, tracking how code evolves
  - **Iterative Improvement Loop**: Automatically applies Reviewer Agent suggestions through the Coder Agent until all issues are resolved
  - **Local LLM Support**: Use local LLM models (Ollama, LM Studio, etc.) instead of OpenAI API

- **Azure DevOps Integration**:
  - Fetches pull request details and changed files
  - Supports multiple iterations of pull requests
  - **Enhanced PR Comment Integration**:
    - Posts summary comments for each file review iteration
    - Posts individual issue comments on specific code lines
    - Updates existing threads rather than creating duplicates
    - Automatically marks threads as "fixed" when issues are resolved
    - Adds confirmation comments when issues are fixed

- **Comparison View**:
  - Side-by-side comparison of code changes and AI analyses
  - Syntax-highlighted diff view
  - Markdown rendering for agent analyses
  - Cross-iteration analysis showing code evolution

- **Web Interface**:
  - View all reviews and their summaries
  - Detailed file-by-file review
  - Multiple view options for each file review
  - Timeline view for multi-iteration reviews
  - Iterative improvement results with before/after comparisons

## Setup

### Prerequisites

- Python 3.7+
- Azure DevOps account with a Personal Access Token (PAT)
- OpenAI API key (optional if using local LLM)
- Local LLM server (optional, e.g., Ollama, LM Studio, LocalAI)

### Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd code_review
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on the provided `.env.example`:
   ```
   cp .env.example .env
   ```

4. Edit the `.env` file with your credentials:
   ```
   # Azure DevOps Configuration
   AZURE_DEVOPS_ORG=your-organization
   AZURE_DEVOPS_PROJECT=your-project
   AZURE_DEVOPS_PAT=your-personal-access-token

   # OpenAI Configuration
   OPENAI_API_KEY=your-openai-api-key
   OPENAI_MODEL_CODER=gpt-4
   OPENAI_MODEL_REVIEWER=gpt-4

   # Local LLM Configuration
   USE_LOCAL_LLM=false
   LOCAL_LLM_API_URL=http://localhost:11434
   LOCAL_LLM_API_TYPE=ollama
   LOCAL_LLM_MODEL=llama3

   # Application Configuration
   DEBUG=False
   ```

## Usage

### PR Review Checklist Feature

You can now optionally include detailed checklists in your PR review summaries:

- **General PR Review Checklist**: Covers code quality, testing, documentation, and best practices for any language.
- **Java-Specific Checklist**: Covers Java naming conventions, access modifiers, resource management, Javadoc, and more.

#### How to Enable Checklists

- **Via Orchestrator/Programmatic Use:**
  Pass the following arguments to `review_pull_request`:
  ```python
  orchestrator.review_pull_request(
      pull_request_id=..., 
      include_checklist=True,           # General checklist
      include_java_checklist=True       # Java checklist if Java files present
  )
  ```
  You can enable either, both, or neither checklist.

- **Via CLI or UI:**
  If integrating into your CLI or web UI, expose toggles or flags for `include_checklist` and `include_java_checklist` when starting a review.

#### How It Works
- The general checklist is always included if enabled.
- The Java checklist is only included if enabled **and** the PR contains `.java` files.
- Both checklists are appended to the end of the summary review for maximum reviewer and developer visibility.

#### Test Scripts
- `test_mock_orchestrator_checklist.py`: Demonstrates checklist logic for generic code reviews.
- `test_java_review_checklist.py`: Demonstrates checklist logic for Java code reviews.

#### Extending for Other Languages
- Add additional language-specific checklists to `utils/pr_review_checklist.py`.
- Update `ReviewerAgent` to detect and append the relevant checklist for each language.

### Running the Web Application

1. Start the Flask application:
   ```
   python app.py
   ```

2. Open your browser and navigate to `http://localhost:5000`

3. Enter an Azure DevOps pull request ID, optionally enable "Use Local LLM", and click "Start Review"

4. For multi-iteration reviews:
   - Click "Fetch Iterations" to get available iterations for the PR
   - Choose to review the latest iteration, all iterations, or a specific iteration
   - Optionally enable "Run iterative improvement loop" to have the system automatically apply reviewer suggestions

5. The system will:
   - Fetch the pull request details from Azure DevOps
   - Analyze each changed file using the Coder agent
   - Review each changed file using the Reviewer agent
   - Generate a summary review (with optional checklists)
   - For multi-iteration reviews, generate a cross-iteration analysis
   - Optionally post comments to the pull request

6. View the results in the web interface, including:
   - Summary review (with checklists if enabled)
   - File-by-file reviews
   - Code diffs with syntax highlighting
   - Side-by-side comparison of code changes and AI analyses
   - For multi-iteration reviews, a timeline view and cross-iteration analysis
   - For iterative improvements, before/after comparisons showing how code evolved through multiple improvement cycles

### Using the API

The system also provides API endpoints for integration with other tools:

- `GET /api/reviews`: List all reviews
- `GET /api/review/<review_id>`: Get a specific review
- `GET /api/iterations`: Get iterations for a pull request
- `GET /api/improvement_details`: Get details of iterative improvements for a file

## PR Comment Integration

The system features a sophisticated PR comment integration that automatically posts and updates detailed code review comments directly on Azure DevOps pull requests:

### Key Features

- **Summary and Line-Specific Comments**:
  - Posts a summary comment for each file review iteration
  - Posts individual issue comments on specific code lines referenced in the review
  - Enhances developer awareness by highlighting issues directly in the PR context

- **Smart Thread Management**:
  - Checks for existing threads before creating new ones to avoid duplicates
  - Updates existing threads with new comments when issues persist across iterations
  - Automatically marks threads as "fixed" when issues are resolved
  - Adds confirmation comments when issues are fixed

- **Iterative Improvement Integration**:
  - Tracks issue resolution across improvement iterations
  - Updates thread statuses as the Coder Agent applies fixes
  - Provides a complete audit trail of issues and resolutions

### How to Enable PR Comment Posting

1. **Via Web Interface**:
   - When starting a review, check the "Post summary comments to PR" option
   - For detailed line comments, also check "Automatically post detailed comments on specific lines"

2. **Via API/Programmatic Use**:
   ```python
   orchestrator = MultiIterationReviewOrchestrator(
       pull_request_id=pr_id,
       post_comments=True,         # Enable summary comments
       auto_post_comments=True     # Enable detailed line comments
   )
   ```

3. **For Iterative Improvements**:
   ```python
   improvement_loop = IterativeImprovementLoop(use_local_llm=False)
   result = improvement_loop.improve_code(
       pull_request_id=pr_id,
       file_path=file_path,
       old_content=old_content,
       new_content=new_content,
       post_comments=True          # Enable PR comment posting
   )
   ```

### How It Works

1. The system analyzes code using the Reviewer Agent
2. It parses the reviewer analysis to extract issues and their line numbers
3. It posts a summary comment for the entire file review
4. It posts individual issue comments on specific code lines
5. During iterative improvements, it tracks which issues are resolved
6. It updates thread statuses and adds confirmation comments when issues are fixed

This feature significantly enhances developer awareness by bringing AI-generated code review feedback directly into the PR workflow, eliminating the need to switch between tools.

## Project Structure

The codebase is organized into a modular package structure for better maintainability and separation of concerns:

- **azure_devops/**: Azure DevOps integration
  - `client.py`: Client for interacting with Azure DevOps API
  - Handles PR data retrieval, comment posting, and thread management

- **core/**: Core logic and orchestration
  - `iterative_improvement_loop.py`: Implements the iterative feedback loop
  - `multi_iteration_orchestrator.py`: Orchestrates multi-iteration PR reviews
  - `langgraph_agents.py`: LangGraph agent definitions and workflow graphs

- **agents/**: AI agent implementations
  - `reviewer_agent.py`: Implements the code reviewer agent
  - `coder_agent.py`: Implements the code explanation and improvement agent
  - `base_agent.py`: Base class for all agents

- **utils/**: Utility functions and helpers
  - `config.py`: Configuration management
  - `local_llm_client.py`: Client for local LLM integration
  - `pr_review_checklist.py`: PR review checklists for different languages

- **tests/**: Test files
  - Contains unit tests and integration tests for all components

## Local LLM Support

The system supports using local LLM models as an alternative to OpenAI's API:

1. **Supported Local LLM Servers**:
   - **Ollama**: Default configuration, access via http://localhost:11434
   - **LM Studio**: Compatible with the system
   - **LocalAI**: Compatible with the system
   - **Text Generation WebUI**: Compatible with the system

2. **Configuration**:
   - Set `USE_LOCAL_LLM=true` in your `.env` file to enable local LLM by default
   - Configure `LOCAL_LLM_API_URL`, `LOCAL_LLM_API_TYPE`, and `LOCAL_LLM_MODEL` in `.env`
   - Toggle "Use Local LLM" in the web interface when starting a review

3. **Using with Ollama**:
   - Install Ollama from [ollama.ai](https://ollama.ai)
   - Pull a model: `ollama pull llama3` or another model of your choice
   - Update the `LOCAL_LLM_MODEL` in `.env` to match your pulled model
   - Start the system with local LLM enabled

4. **Testing Local LLM**:
   - Run `python -m tests.test_ollama` to test basic connectivity
   - Run `python -m tests.test_code_review_with_ollama` to test the code review functionality

## Architecture

The system consists of the following components:

1. **Azure DevOps Clients**:
   - **Azure DevOps Client**: Handles basic communication with Azure DevOps API
   - **Azure DevOps Iteration Client**: Specializes in fetching and analyzing multiple iterations of pull requests

2. **AI Agents**:
   - Base Agent: Common functionality for AI agents
   - Coder Agent: Analyzes and explains code changes
   - Reviewer Agent: Reviews code and provides feedback
   - Iteration Analyzer: Analyzes changes across multiple iterations
   - Iterative Improvement Loop: Applies reviewer suggestions automatically through multiple improvement cycles
   - Local LLM Client: Provides interface to local LLM models as an alternative to OpenAI

3. **Code Review Orchestrators**:
   - **Code Review Orchestrator**: Basic orchestrator for single-iteration reviews
   - **LangGraph Code Review Orchestrator**: Uses LangGraph for advanced multi-agent orchestration
   - **Multi-Iteration Review Orchestrator**: Specializes in reviewing multiple iterations of pull requests

4. **Web Application**: Flask-based web interface for viewing reviews

## Customization

### Iterative Improvement Loop

The system includes an iterative improvement feature that automatically applies reviewer suggestions:

1. Enable the feature by checking "Run iterative improvement loop" when starting a review
2. Set the maximum number of improvement iterations (default is 3)
3. The system will:
   - Have the Reviewer Agent analyze each file and provide suggestions
   - Have the Coder Agent apply those suggestions to improve the code
   - Repeat the process until all issues are resolved or max iterations is reached
4. View the results in the improvement page, showing each iteration's changes

### Modifying Agent Behavior

You can customize the behavior of the AI agents by modifying the system messages in `agents/coder_agent.py` and `agents/reviewer_agent.py`.

### Adding New Agents

To add a new agent:

1. Create a new agent class that inherits from `BaseAgent`
2. Implement the agent's specific functionality
3. Update the appropriate orchestrator to use the new agent

### LangGraph Integration

The system includes LangGraph-based orchestration for advanced multi-agent workflows:

1. Enable the LangGraph workflow by checking the "Use LangGraph multi-agent workflow" option
2. Customize the workflow in `langgraph_agents.py` and `langgraph_orchestrator.py`

### Multi-Iteration Review

To customize the multi-iteration review process:

1. Modify the `MultiIterationReviewOrchestrator` class in `multi_iteration_orchestrator.py`
2. Adjust the cross-iteration analysis prompt to focus on specific aspects of code evolution
3. Update the `AzureDevOpsIterationClient` to fetch additional information about iterations

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
