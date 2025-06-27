from agents.reviewer_agent import ReviewerAgent
from pr_review_checklist import format_java_checklist_markdown

# Dummy Java file review data
java_file_reviews = [
    {
        "path": "MyClass.java",
        "reviewer_analysis": "## Code Quality\n- Good use of encapsulation.\n## Bugs\n- Missing null check in constructor."
    },
    {
        "path": "Utils.java",
        "reviewer_analysis": "## Performance\n- Consider using StringBuilder for string concatenation.\n## Documentation\n- Missing Javadoc for public methods."
    }
]

def mock_java_summary_review(all_file_reviews, include_checklist=False):
    reviewer = ReviewerAgent(use_local_llm=True)
    reviews_text = "\n\n".join([f"### {f['path']}\n{f['reviewer_analysis']}" for f in all_file_reviews])
    summary = reviewer.provide_summary_review(reviews_text, include_checklist=include_checklist)
    if include_checklist:
        summary += "\n\n---\n**Java Review Checklist:**\n" + format_java_checklist_markdown()
    return summary

if __name__ == "__main__":
    print("===== JAVA SUMMARY REVIEW WITH CHECKLIST =====")
    print(mock_java_summary_review(java_file_reviews, include_checklist=True))
    print("\n\n")

    print("===== JAVA SUMMARY REVIEW WITHOUT CHECKLIST =====")
    print(mock_java_summary_review(java_file_reviews, include_checklist=False))
