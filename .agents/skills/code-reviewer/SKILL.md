---
name: code-reviewer
description: Use this skill when the user asks to review code, check for anti-patterns, or analyze a file for security and style compliance before committing.
---

# Automated Code Reviewer

## Goal
To analyze Python and JavaScript files for common security vulnerabilities, anti-patterns, and style violations, ensuring code meets enterprise standards before deployment.

## Instructions
1. **Analyze the Request**: Determine which file or directory the user wants reviewed (e.g., `@order_service.py` or the current workspace).
2. **Execute the Review Script**: Use the provided script to scan the code.
   - Script: `scripts/scanner.py`
   - Command: `python scripts/scanner.py [file_path]`
3. **Synthesize Findings**: The script will output raw findings. You must organize these findings into a readable markdown report.
4. **Format the Output**: Structure your response using the following headers:
   - **Summary**: A brief overview of the file's purpose and general health.
   - **Security Concerns**: (High priority) Note any potential vulnerabilities.
   - **Anti-Patterns**: Note inefficient logic or potential bugs.
   - **Style Suggestions**: Recommendations for better readability.

## Examples
- **User Prompt**: "Review the @demo_bad_code.py file."
- **Expected Action**: Execute `python scripts/scanner.py demo_bad_code.py` and output a structured report based on the results.

## Constraints
- Do not rewrite the entire file for the user unless explicitly asked. Provide actionable suggestions instead.
- Focus on objective standards; do not nitpick on subjective naming conventions unless they violate PEP 8 or standard JS conventions.
