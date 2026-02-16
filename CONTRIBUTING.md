# Contributing

Thank you for your interest in contributing to ViralForge.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and configure your API keys
5. Run database migrations: `alembic upgrade head`

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes
3. Run linting and tests:
   ```bash
   ruff check app/
   ruff format --check app/
   mypy app/
   pytest
   ```
4. Commit your changes with a descriptive message
5. Push to your fork and open a Pull Request

## Code Style

- Follow PEP 8 conventions
- Use [ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Maximum line length: 120 characters
- Use type hints where practical

## Pull Requests

- Keep PRs focused on a single change
- Include a clear description of what changed and why
- Ensure CI checks pass before requesting review
- Update documentation if your change affects the public API

## Reporting Issues

- Use the GitHub issue templates (bug report or feature request)
- Include steps to reproduce for bug reports
- Check existing issues before opening a new one
