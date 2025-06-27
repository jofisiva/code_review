from agents.reviewer_agent import ReviewerAgent

# Dummy file review data for a fake PR
dummy_file_reviews = [
    {
        "path": "foo.py",
        "reviewer_analysis": "## Code Quality\n- Good use of functions.\n## Bugs\n- No major bugs found."
    },
    {
        "path": "bar.py",
        "reviewer_analysis": "## Code Quality\n- Needs better variable names.\n## Performance\n- Consider optimizing the loop."
    }
]

def mock_provide_summary_review(all_file_reviews, include_checklist=False):
    reviewer = ReviewerAgent(use_local_llm=True)
    # Compose a string that would simulate the file review aggregation
    reviews_text = "\n\n".join([f"### {f['path']}\n{f['reviewer_analysis']}" for f in all_file_reviews])
    return reviewer.provide_summary_review(reviews_text, include_checklist=include_checklist)

if __name__ == "__main__":
    # Run with checklist
    print("===== SUMMARY REVIEW WITH CHECKLIST =====")
    summary_with_checklist = mock_provide_summary_review(dummy_file_reviews, include_checklist=True)
    print(summary_with_checklist)
    print("\n\n")

    # Run without checklist
    print("===== SUMMARY REVIEW WITHOUT CHECKLIST =====")
    summary_without_checklist = mock_provide_summary_review(dummy_file_reviews, include_checklist=False)
    print(summary_without_checklist)
