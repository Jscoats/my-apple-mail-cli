# Contributing to my-apple-mail-cli

Thanks for your interest in contributing! 🎉

This project welcomes contributions from the community. Whether you're fixing a bug, adding a feature, or improving documentation, your help is appreciated.

## 🐛 Reporting Bugs

Found a bug? Please [open an issue](https://github.com/Jscoats/my-apple-mail-cli/issues/new?template=bug_report.md) with:

- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (macOS version, Python version, Mail.app version)
- Relevant error messages or logs

**Note:** Please check existing issues first to avoid duplicates.

## 💡 Requesting Features

Have an idea? [Open a feature request](https://github.com/Jscoats/my-apple-mail-cli/issues/new?template=feature_request.md) with:

- Clear description of the feature
- Why it would be useful
- Example usage (if applicable)

## 🔧 Contributing Code

### Before You Start

1. **Check existing issues** - Someone might already be working on it
2. **Discuss major changes** - Open an issue first for big features/refactors
3. **Keep it focused** - One feature/fix per pull request

### Development Setup

```bash
# Clone the repo
git clone https://github.com/Jscoats/my-apple-mail-cli.git
cd my-apple-mail-cli

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

### Code Guidelines

**Follow existing patterns:**
- Match the style of surrounding code
- Use existing utilities in `src/my_cli/util/`
- Add AppleScript code to `applescript_templates.py` if reusable
- Keep functions focused and testable

**Zero runtime dependencies:**
- This project uses only Python stdlib
- Do not add external packages without discussion

**Testing:**
- Add tests for new features
- Ensure existing tests pass: `pytest`
- Test files live in `tests/`
- Mock AppleScript calls in tests (see existing test files for examples)

**Documentation:**
- Update README.md if adding user-facing features
- Add docstrings to new functions
- Update CLAUDE.md for architectural changes

### Pull Request Process

1. **Fork the repo** and create a feature branch
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make your changes**
   - Write clean, readable code
   - Add tests for new functionality
   - Update documentation

3. **Test thoroughly**
   ```bash
   pytest  # All tests must pass
   ```

4. **Commit with clear messages**
   ```bash
   git commit -m "Add email filter by date range"
   ```

5. **Push and create a pull request**
   ```bash
   git push origin feature/my-new-feature
   ```

6. **Describe your changes** in the PR:
   - What does it do?
   - Why is it needed?
   - How was it tested?

### Code Review

- PRs will be reviewed for code quality, test coverage, and alignment with project goals
- Be patient - reviews may take a few days
- Be open to feedback and iteration

## 📝 Documentation

Documentation improvements are always welcome! You can help by:

- Fixing typos or unclear wording
- Adding examples to the README
- Improving code comments
- Writing tutorials or guides

## 🤔 Questions?

Not sure about something? Open an issue with the `question` label or reach out via GitHub discussions.

## 🙏 Thank You!

Every contribution, no matter how small, helps make this project better. Thank you for being part of the community!

---

**By contributing, you agree that your contributions will be licensed under the project's MIT License.**
