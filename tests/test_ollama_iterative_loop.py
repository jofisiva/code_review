#!/usr/bin/env python3
"""
Advanced test script for iterative code improvement with Ollama local LLM.

This script simulates the iterative improvement loop where:
1. The Reviewer Agent reviews the code and identifies issues
2. The Coder Agent applies fixes based on the Reviewer's feedback
3. The process repeats until all issues are resolved or max iterations reached

This demonstrates the integration between local LLM support and the iterative improvement workflow.
"""

import os
import json
import tempfile
import shutil
import re
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

class IterativeLoopSimulator:
    """Simulates the iterative improvement loop without Azure DevOps dependencies."""
    
    def __init__(self, max_iterations=3, improvement_threshold=0.8):
        """Initialize the simulator with agents and parameters."""
        self.reviewer = ReviewerAgent(use_local_llm=True)
        self.coder = CoderAgent(use_local_llm=True)
        self.max_iterations = max_iterations
        self.improvement_threshold = improvement_threshold
        
    def run_improvement_loop(self, file_path, initial_code):
        """Run the iterative improvement loop on the given code."""
        print(f"Starting iterative improvement loop for {file_path}")
        print(f"Maximum iterations: {self.max_iterations}")
        
        current_code = initial_code
        iterations = []
        all_issues_resolved = False
        
        for iteration in range(1, self.max_iterations + 1):
            print(f"\n--- ITERATION {iteration} ---")
            
            # Step 1: Reviewer analyzes the code
            print("Step 1: Reviewer analyzing code...")
            reviewer_analysis = self.reviewer.review_file_changes(
                file_path=file_path,
                old_content="",  # No old content for first iteration
                new_content=current_code
            )
            
            # Count issues in reviewer analysis
            issue_count = self._count_issues(reviewer_analysis)
            print(f"Reviewer identified {issue_count} issues")
            
            # Check if there are any issues to fix
            if issue_count == 0:
                print("No issues found! Code is optimal.")
                all_issues_resolved = True
                break
                
            # Step 2: Coder applies improvements
            print("Step 2: Coder applying improvements...")
            coder_prompt = f"""
            I need you to improve the following Python code based on the reviewer's feedback:
            
            Current code:
            ```python
            {current_code}
            ```
            
            Reviewer's analysis:
            {reviewer_analysis}
            
            Please implement ALL the suggested improvements and provide the complete improved code.
            Make sure to address ALL the issues mentioned by the reviewer.
            Return ONLY the improved code within a Python code block.
            """
            
            improved_code_response = self.coder.generate_response(
                prompt=coder_prompt,
                system_message=self.coder.system_message
            )
            
            # Extract code block from response
            improved_code = self._extract_code_from_response(improved_code_response, current_code)
            
            # Save iteration results
            iterations.append({
                "iteration": iteration,
                "reviewer_analysis": reviewer_analysis,
                "improved_code": improved_code,
                "issues_count": issue_count
            })
            
            # Update current code for next iteration
            current_code = improved_code
            
            print(f"Completed iteration {iteration}")
            
        # Prepare final results
        results = {
            "file_path": file_path,
            "initial_code": initial_code,
            "final_code": current_code,
            "iterations_completed": len(iterations),
            "all_issues_resolved": all_issues_resolved,
            "iterations": iterations,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return results
    
    def _count_issues(self, reviewer_analysis):
        """Count the number of issues in the reviewer analysis."""
        # Look for common issue indicators in the text
        issue_indicators = [
            r"bug", r"issue", r"problem", r"error", r"concern", 
            r"fix", r"improve", r"enhancement", r"suggestion",
            r"consider", r"should", r"could", r"would", r"better"
        ]
        
        # Count occurrences of issue indicators
        count = 0
        for indicator in issue_indicators:
            matches = re.findall(r'\b' + indicator + r'\w*\b', reviewer_analysis.lower())
            count += len(matches)
            
        # Normalize the count (avoid too high counts)
        return min(count, 20)  # Cap at 20 issues
    
    def _extract_code_from_response(self, response, fallback_content):
        """Extract code block from agent response."""
        # Try to find Python code blocks
        code_blocks = re.findall(r'```python\n(.*?)\n```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0]
            
        # Try to find generic code blocks
        code_blocks = re.findall(r'```\n(.*?)\n```', response, re.DOTALL)
        if code_blocks:
            return code_blocks[0]
            
        # Try to find code without markers
        if "def " in response and "return " in response:
            # Attempt to extract just the code part
            lines = response.split('\n')
            code_lines = []
            in_code = False
            for line in lines:
                if line.strip().startswith('def ') or line.strip().startswith('class '):
                    in_code = True
                if in_code:
                    code_lines.append(line)
            if code_lines:
                return '\n'.join(code_lines)
        
        # If all extraction attempts fail, return the original response
        print("WARNING: Could not extract code block from response. Using fallback content.")
        return fallback_content


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

# Create a temporary directory for our test
test_dir = Path(tempfile.mkdtemp())
print(f"Created temporary test directory: {test_dir}")

# Write the sample code to a file
sample_file = test_dir / "math_utils.py"
with open(sample_file, "w") as f:
    f.write(sample_code)

print(f"Created sample file with issues: {sample_file}")

# Create a log directory for results
results_dir = Path("./test_results")
results_dir.mkdir(exist_ok=True)

# Initialize and run the simulator
print("Initializing iterative loop simulator with Ollama local LLM")
simulator = IterativeLoopSimulator(max_iterations=3)

print("\nStarting iterative improvement loop...")
print("This will run multiple alternating invocations of the Reviewer and Coder agents")
print("The process continues until all issues are resolved or max iterations is reached")

# Run the iterative improvement loop
improvement_results = simulator.run_improvement_loop(
    file_path=str(sample_file),
    initial_code=sample_code
)

# Save the results
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
results_file = results_dir / f"ollama_iterative_loop_{timestamp}.json"

with open(results_file, "w") as f:
    json.dump(improvement_results, f, indent=2)

print(f"\nImprovement loop completed with {improvement_results['iterations_completed']} iterations")
print(f"All issues resolved: {improvement_results['all_issues_resolved']}")
print(f"Results saved to: {results_file}")

# Print the final improved code
print("\nFinal improved code:")
print("-" * 50)
print(improvement_results["final_code"][:500] + "..." if len(improvement_results["final_code"]) > 500 else improvement_results["final_code"])
print("-" * 50)

# Clean up
shutil.rmtree(test_dir)
print(f"Cleaned up temporary directory: {test_dir}")

print("\nTest completed successfully!")
