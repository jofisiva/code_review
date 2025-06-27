#!/usr/bin/env python3
"""
Test script to verify the iterative improvement loop functionality with Ollama local LLM.

This script simulates a code review scenario where:
1. A sample code file with issues is created
2. The Reviewer Agent identifies issues in the code
3. The Coder Agent applies fixes based on the Reviewer's feedback
4. The process repeats until all issues are resolved or max iterations reached

This test validates that both local LLM support and iterative improvement work together.
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
from iterative_improvement_loop import IterativeImprovementLoop, BatchImprovementProcessor

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

print("Initializing iterative improvement loop with local LLM (Ollama)")

# Initialize the iterative improvement loop with local LLM
improvement_loop = IterativeImprovementLoop(use_local_llm=True)

# Configure the loop parameters
max_iterations = 3  # Limit iterations for testing

# File metadata for the test
file_metadata = {
    "file_path": str(sample_file),
    "language": "python",
    "content": sample_code
}

print("Starting iterative improvement loop...")
print("This will run the Reviewer and Coder agents in alternating sequence")
print("Each iteration: Reviewer identifies issues → Coder fixes them → Repeat")

# Create a mock pull request ID for testing
mock_pr_id = "test-pr-123"

# Run the iterative improvement loop
improvement_results = improvement_loop.improve_code(
    pull_request_id=mock_pr_id,
    file_path=str(sample_file),
    old_content="",  # No previous content for this test
    new_content=sample_code,
    max_iterations=max_iterations,
    output_dir="./test_results"
)

# Save the results
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
results_file = results_dir / f"ollama_improvement_results_{timestamp}.json"

with open(results_file, "w") as f:
    json.dump(improvement_results, f, indent=2)

print(f"\nImprovement loop completed with {len(improvement_results['iterations'])} iterations")
print(f"Results saved to: {results_file}")

# Print the final improved code
if improvement_results["iterations"]:
    final_code = improvement_results["iterations"][-1]["improved_code"]
    print("\nFinal improved code:")
    print("-" * 50)
    print(final_code)
    print("-" * 50)

# Clean up
shutil.rmtree(test_dir)
print(f"Cleaned up temporary directory: {test_dir}")

print("\nTest completed successfully!")
