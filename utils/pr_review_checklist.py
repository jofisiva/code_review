"""
PR review checklists for different languages and scenarios.
"""

class PRReviewChecklist:
    """
    Provides standardized checklists for PR reviews.
    """
    
    def get_general_checklist(self):
        """Get the general PR review checklist.
        
        Returns:
            Markdown-formatted general checklist
        """
        return """
## General PR Review Checklist

### Code Quality
- [ ] Code follows project style guidelines and naming conventions
- [ ] Code is well-structured and easy to understand
- [ ] Functions and methods are focused and not too long
- [ ] No duplicated code or unnecessary complexity
- [ ] No commented-out code or TODOs without associated tickets
- [ ] Proper error handling and edge cases are addressed

### Testing
- [ ] Unit tests are included for new functionality
- [ ] Existing tests pass with the changes
- [ ] Edge cases and error conditions are tested
- [ ] Test coverage is adequate for the changes

### Documentation
- [ ] Code is properly documented with comments where necessary
- [ ] Public APIs have clear documentation
- [ ] README or other documentation is updated if needed
- [ ] PR description clearly explains the changes and rationale

### Performance
- [ ] No obvious performance issues or inefficient algorithms
- [ ] Database queries are optimized if applicable
- [ ] No unnecessary resource usage (memory, CPU, network)

### Security
- [ ] No security vulnerabilities introduced
- [ ] Proper input validation and sanitization
- [ ] No sensitive information exposed in logs or UI
- [ ] Authentication and authorization checks where needed

### Best Practices
- [ ] No hardcoded values that should be configurable
- [ ] Proper use of design patterns where applicable
- [ ] Code is modular and follows separation of concerns
- [ ] Dependencies are properly managed
"""
    
    def get_java_checklist(self):
        """Get the Java-specific PR review checklist.
        
        Returns:
            Markdown-formatted Java checklist
        """
        return """
## Java-Specific PR Review Checklist

### Java Naming Conventions
- [ ] Classes are named using PascalCase
- [ ] Methods and variables use camelCase
- [ ] Constants use UPPER_SNAKE_CASE
- [ ] Package names use lowercase

### Java Best Practices
- [ ] Proper use of access modifiers (private, protected, public)
- [ ] Immutable objects used where appropriate
- [ ] Proper equals() and hashCode() implementations
- [ ] toString() method overridden where useful
- [ ] Proper use of final for variables and methods where appropriate

### Java Resource Management
- [ ] Resources properly closed (try-with-resources used)
- [ ] No memory leaks from unclosed resources
- [ ] Proper exception handling with specific catch blocks
- [ ] No catching of generic Exception without specific handling

### Java Documentation
- [ ] Javadoc comments for public methods and classes
- [ ] @param, @return, and @throws tags used correctly
- [ ] Javadoc is consistent with method behavior

### Java Performance
- [ ] Efficient collection types used for the use case
- [ ] No unnecessary object creation in loops
- [ ] StringBuilder/StringBuffer used for string concatenation in loops
- [ ] Proper use of streams and lambdas

### Java Threading
- [ ] Thread-safety considered where needed
- [ ] Proper synchronization mechanisms used
- [ ] No potential deadlocks or race conditions
- [ ] Proper use of concurrent collections where needed
"""
    
    def get_python_checklist(self):
        """Get the Python-specific PR review checklist.
        
        Returns:
            Markdown-formatted Python checklist
        """
        return """
## Python-Specific PR Review Checklist

### Python Naming Conventions
- [ ] Functions and variables use snake_case
- [ ] Classes use PascalCase
- [ ] Constants use UPPER_SNAKE_CASE
- [ ] Private attributes prefixed with underscore (_)

### Python Best Practices
- [ ] Type hints used where appropriate
- [ ] Docstrings for functions, classes, and modules
- [ ] List comprehensions used where appropriate
- [ ] Context managers (with) used for resource management
- [ ] Proper use of generators and iterators where appropriate

### Python Code Organization
- [ ] Imports organized according to PEP 8
- [ ] Classes and functions have single responsibility
- [ ] Proper use of dunder methods where appropriate
- [ ] Proper use of properties vs. getters/setters

### Python Error Handling
- [ ] Specific exceptions caught rather than generic Exception
- [ ] Custom exceptions defined where appropriate
- [ ] Proper use of try/except/else/finally blocks
- [ ] Exceptions properly propagated or handled

### Python Performance
- [ ] Efficient data structures used for the use case
- [ ] No unnecessary list or dictionary comprehensions in loops
- [ ] Proper use of sets for membership testing
- [ ] Proper use of generators for large data sets

### Python Testing
- [ ] Tests use pytest fixtures where appropriate
- [ ] Mocking used appropriately for external dependencies
- [ ] Parametrized tests used for similar test cases
- [ ] Test coverage for edge cases and error conditions
"""
