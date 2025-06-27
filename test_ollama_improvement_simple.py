#!/usr/bin/env python3
"""
Simplified test script for local LLM code improvement without Azure DevOps dependencies.

This script tests the core functionality of using local LLM (Ollama) to:
1. Review code with the Reviewer Agent
2. Apply fixes with the Coder Agent
"""

import os
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Set environment variables for local LLM
os.environ["USE_LOCAL_LLM"] = "true"
os.environ["LOCAL_LLM_API_TYPE"] = "ollama"
os.environ["LOCAL_LLM_MODEL"] = "llama3.2:1b"  # Using smaller model for faster testing
os.environ["LOCAL_LLM_API_URL"] = "http://localhost:11434"

# Import after setting environment variables
from agents.coder_agent import CoderAgent
from agents.reviewer_agent import ReviewerAgent
from local_llm_client import LocalLLMClient

# Create a temporary directory for our test
test_dir = Path(tempfile.mkdtemp())
print(f"Created temporary test directory: {test_dir}")

# Sample code with issues to be fixed
sample_code = """
def calculate_average(numbers):
    # This function has several issues:
    # 1. No input validation
    # 2. Potential division by zero
    # 3. No docstring
    # 4. Inefficient implementation
    
    sum = 0
    for num in numbers:
        sum = sum + num
    
    return sum / len(numbers)

def find_max(numbers):
    # This function has issues too:
    # 1. No input validation
    # 2. Doesn't handle empty list
    # 3. Inefficient implementation
    
    max_val = numbers[0]
    for num in numbers:
        if num > max_val:
            max_val = num
    
    return max_val
"""

# Write the sample code to a file
sample_file = test_dir / "math_utils.py"
with open(sample_file, "w") as f:
    f.write(sample_code)

print(f"Created sample file with issues: {sample_file}")

# Create a log directory for results
results_dir = Path("./test_results")
results_dir.mkdir(exist_ok=True)

print("Initializing agents with local LLM (Ollama)")

# Initialize agents with local LLM
reviewer = ReviewerAgent(use_local_llm=True)
coder = CoderAgent(use_local_llm=True)

# File metadata for the test
file_path = str(sample_file)
language = "python"

print("\n--- STEP 1: REVIEWER ANALYSIS ---")
print("Asking the Reviewer Agent to analyze the code and identify issues...")

# Step 1: Get reviewer analysis
# Using review_file_changes method which is the actual method in ReviewerAgent
reviewer_analysis = reviewer.review_file_changes(
    file_path="math_utils.py",
    old_content="",  # No old content for this test
    new_content=sample_code
)
print("\nReviewer Analysis:")
print("-" * 50)
print(reviewer_analysis[:500] + "..." if len(reviewer_analysis) > 500 else reviewer_analysis)
print("-" * 50)

print("\n--- STEP 2: CODER IMPROVEMENT ---")
print("Asking the Coder Agent to apply the reviewer's suggestions...")

# Create a prompt for the coder based on the reviewer's feedback
coder_prompt = f"""
I need you to improve the following Python code based on the reviewer's feedback:

Original code:
```python
{sample_code}
```

Reviewer's analysis:
{reviewer_analysis}

Please implement all the suggested improvements and provide the complete improved code.
Make sure to address all the issues mentioned by the reviewer.
"""

# The BaseAgent class has a generate_response method that both agents inherit
improved_code = coder.generate_response(
    prompt=coder_prompt,
    system_message=coder.system_message
)

# Extract code block from response
import re
code_blocks = re.findall(r'```python\n(.*?)```', improved_code, re.DOTALL)
if code_blocks:
    final_code = code_blocks[0]
else:
    final_code = improved_code

print("\nImproved Code:")
print("-" * 50)
print(final_code[:500] + "..." if len(final_code) > 500 else final_code)
print("-" * 50)

# Save the results
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
results_file = results_dir / f"ollama_improvement_simple_{timestamp}.json"

results = {
    "original_code": sample_code,
    "reviewer_analysis": reviewer_analysis,
    "improved_code": final_code,
    "timestamp": timestamp
}

with open(results_file, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nResults saved to: {results_file}")

# Clean up
shutil.rmtree(test_dir)
print(f"Cleaned up temporary directory: {test_dir}")

print("\nTest completed successfully!")
