# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Instead, please email the maintainer directly with:

1. A description of the vulnerability
2. Steps to reproduce the issue
3. Potential impact assessment
4. Any suggested fixes (optional)

You can expect an initial response within 72 hours.

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | Yes                |

## Security Best Practices

When deploying this application:

- Never commit `.env` files or API keys to version control
- Use strong, unique API keys for all external services
- Run the application behind a reverse proxy (e.g., nginx) in production
- Keep all dependencies up to date
- Use the Docker deployment with the non-root user configuration
