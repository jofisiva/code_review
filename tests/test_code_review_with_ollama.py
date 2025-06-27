from agents.coder_agent import CoderAgent
from agents.reviewer_agent import ReviewerAgent
import os
import json
from datetime import datetime

def test_local_llm_code_review():
    """Test the code review system with local LLM (Ollama)."""
    print("Testing code review with Ollama...")
    
    # Create agents with local LLM enabled
    coder = CoderAgent(use_local_llm=True)
    reviewer = ReviewerAgent(use_local_llm=True)
    
    # Sample code for testing
    old_code = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total
    """
    
    new_code = """
def calculate_sum(numbers):
    if not numbers:
        return 0
    return sum(numbers)
    """
    
    file_path = "example.py"
    
    # Step 1: Coder analyzes the changes
    print("Step 1: Coder analyzing changes...")
    coder_analysis = coder.analyze_file_changes(file_path, old_code, new_code)
    print("\nCoder Analysis:")
    print("-" * 50)
    print(coder_analysis)
    print("-" * 50)
    
    # Step 2: Reviewer reviews the changes with coder's analysis
    print("\nStep 2: Reviewer reviewing changes...")
    reviewer_analysis = reviewer.review_file_changes(file_path, old_code, new_code, coder_analysis)
    print("\nReviewer Analysis:")
    print("-" * 50)
    print(reviewer_analysis)
    print("-" * 50)
    
    # Save results to a file for reference
    os.makedirs("test_results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    result_file = f"test_results/ollama_test_{timestamp}.json"
    
    with open(result_file, 'w') as f:
        json.dump({
            "file_path": file_path,
            "old_code": old_code,
            "new_code": new_code,
            "coder_analysis": coder_analysis,
            "reviewer_analysis": reviewer_analysis,
            "timestamp": timestamp,
            "model": "llama3.2:1b (Ollama)"
        }, f, indent=2)
    
    print(f"\nResults saved to {result_file}")
    return coder_analysis, reviewer_analysis

if __name__ == "__main__":
    test_local_llm_code_review()
