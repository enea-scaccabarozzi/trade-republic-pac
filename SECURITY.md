# Security Policy

## Supported Versions

Only the latest release receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |
| older   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Report security vulnerabilities privately using GitHub Security Advisories:

[Open a private security advisory](https://github.com/enea-scaccabarozzi/trade-republic-pac/security/advisories/new)

You can expect:

- **Acknowledgment within 48 hours** of submission.
- A **coordinated disclosure timeline of 90 days**, during which a fix will be prepared and released before the vulnerability is publicly disclosed.

Please include as much detail as possible:

- A description of the vulnerability and its potential impact.
- Steps to reproduce or proof-of-concept code.
- Any suggested mitigations, if you have them.

## What Qualifies as a Security Issue

**In scope:**

- Authentication or authorization bypass
- Injection vulnerabilities (command injection, SQL injection, template injection, etc.)
- Secrets or credentials exposed in logs, responses, or repository artifacts
- Server-Side Request Forgery (SSRF)
- Insecure deserialization
- Privilege escalation

**Out of scope:**

- General bugs or regressions not related to security
- Feature requests
- Denial-of-service issues caused by intentionally malformed input from authenticated administrators
- Issues already publicly known or previously reported

## Disclosure Policy

This project follows **coordinated disclosure**:

1. Reporter submits a private advisory.
2. Maintainer acknowledges within 48 hours.
3. Maintainer investigates and develops a fix within 90 days.
4. Fix is released and the advisory is published simultaneously.

If a fix cannot be delivered within 90 days, the maintainer will communicate a revised timeline to the reporter before the deadline.

## Credit

Reporters who responsibly disclose security vulnerabilities will be credited by name (or handle, if preferred) in the release notes for the fix, unless they request to remain anonymous.
