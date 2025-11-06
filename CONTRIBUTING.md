# Contributing to AEA JOE Automation Tool

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/your-username/joe-automation.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Commit your changes: `git commit -m "Add some feature"`
6. Push to the branch: `git push origin feature/your-feature-name`
7. Open a Pull Request

## Development Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy example settings:
```bash
cp config/settings.example.py config/settings.py
```

3. Configure your settings in `config/settings.py` or use environment variables.

## Code Style

- Follow PEP 8 style guide
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and small
- Add comments for complex logic

## Testing

Before submitting a PR, please:
- Test your changes locally
- Ensure no syntax errors
- Check that existing functionality still works

## Pull Request Process

1. Update the README.md if needed
2. Ensure your code follows the style guidelines
3. Write clear commit messages
4. Reference any related issues in your PR

## Questions?

Feel free to open an issue for questions or discussions!

