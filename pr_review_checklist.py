"""
PR Review Checklist Module

This module provides a standard checklist for code reviewers to ensure all important aspects of a pull request are systematically evaluated.
"""

PR_REVIEW_CHECKLIST = [
    "[ ] Code compiles and runs without errors",
    "[ ] All new and changed code is covered by tests",
    "[ ] No obvious bugs or security vulnerabilities",
    "[ ] Code follows project style and linting guidelines",
    "[ ] Functions and classes are documented with docstrings",
    "[ ] No commented-out or dead code remains",
    "[ ] All dependencies are necessary and up-to-date",
    "[ ] User-facing changes are reflected in documentation",
    "[ ] Code is efficient and avoids unnecessary complexity",
    "[ ] All review comments from previous iterations are addressed"
]

JAVA_REVIEW_CHECKLIST = [
    "[ ] Code follows Java naming conventions (classes, methods, variables)",
    "[ ] No public fields unless static final",
    "[ ] Proper use of access modifiers (private, protected, public)",
    "[ ] No resource leaks (files, streams, DB connections closed)",
    "[ ] No use of deprecated APIs",
    "[ ] Proper use of exceptions and error handling",
    "[ ] Javadoc comments for public classes and methods"
]

def get_checklist():
    """Return the standard PR review checklist as a list of items."""
    return PR_REVIEW_CHECKLIST

def get_java_checklist():
    """Return the Java-specific PR review checklist as a list of items."""
    return JAVA_REVIEW_CHECKLIST

def format_checklist_markdown(checklist=None):
    """Return the checklist formatted as a markdown checklist."""
    if checklist is None:
        checklist = PR_REVIEW_CHECKLIST
    return '\n'.join(checklist)

def format_java_checklist_markdown():
    """Return the Java checklist formatted as a markdown checklist."""
    return '\n'.join(JAVA_REVIEW_CHECKLIST)
