# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do not open a public issue for security vulnerabilities.**

Instead, please email a description of the vulnerability to the project maintainer via GitHub's private vulnerability reporting feature:

1. Go to the [Security tab](https://github.com/Jscoats/my-apple-mail-cli/security)
2. Click "Report a vulnerability"
3. Provide details about the issue

## What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response

You can expect an initial response within 7 days. We will work with you to understand and address the issue before any public disclosure.

## Scope

This project runs locally on macOS and communicates with Apple Mail via AppleScript. Security concerns most likely relate to:

- Command injection via unsanitized input passed to AppleScript
- Exposure of email content or credentials
- Unsafe handling of configuration files containing API tokens
