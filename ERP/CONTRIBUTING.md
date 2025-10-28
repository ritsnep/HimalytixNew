# Contributing to Himalytix ERP

Thank you for your interest in contributing to Himalytix ERP! This document provides guidelines and instructions for contributing to the project.

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Commit Messages](#commit-messages)
- [Issue Reporting](#issue-reporting)

## 🤝 Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please:
- Be respectful and considerate
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards others

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Clone your fork
git clone https://github.com/YOUR_USERNAME/himalytix-erp.git
cd himalytix-erp

# Add upstream remote
git remote add upstream https://github.com/himalytix/erp.git
```

### 2. Set Up Development Environment

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Install development tools
pip install pre-commit black flake8 isort coverage pytest pytest-django

# Set up pre-commit hooks
pre-commit install
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your local settings
```

### 4. Create Database and Run Migrations

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 5. Verify Setup

```bash
# Run tests
python manage.py test

# Start server
python manage.py runserver
```

## 🔄 Development Workflow

### 1. Create a Feature Branch

```bash
# Update your fork
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feat/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Changes

- Write clean, readable code
- Follow the code style guidelines (see below)
- Add tests for new functionality
- Update documentation as needed

### 3. Test Your Changes

```bash
# Run tests
python manage.py test

# Check coverage
coverage run --source='.' manage.py test
coverage report

# Lint code
flake8 .
black --check .
isort --check .

# Run pre-commit checks
pre-commit run --all-files
```

### 4. Commit Your Changes

```bash
# Stage changes
git add .

# Commit with conventional commit message
git commit -m "feat: add invoice generation feature"
```

### 5. Push and Create Pull Request

```bash
# Push to your fork
git push origin feat/your-feature-name

# Go to GitHub and create a Pull Request
```

## 🎨 Code Style

### Python

We follow PEP 8 with some modifications:

- **Line Length**: 100 characters (not 79)
- **Formatter**: Black
- **Linter**: Flake8
- **Import Sorting**: isort

```bash
# Format code
black . --line-length=100

# Sort imports
isort . --profile=black --line-length=100

# Lint
flake8 . --max-line-length=100 --extend-ignore=E203,W503
```

### Django-Specific Guidelines

```python
# ✅ Good: Use get_object_or_404
from django.shortcuts import get_object_or_404
invoice = get_object_or_404(Invoice, pk=invoice_id)

# ❌ Bad: Manual try/except
try:
    invoice = Invoice.objects.get(pk=invoice_id)
except Invoice.DoesNotExist:
    raise Http404

# ✅ Good: Use select_related/prefetch_related
invoices = Invoice.objects.select_related('customer').all()

# ❌ Bad: N+1 queries
invoices = Invoice.objects.all()  # Then accessing invoice.customer in loop

# ✅ Good: Use timezone-aware datetimes
from django.utils import timezone
created_at = timezone.now()

# ❌ Bad: Naive datetimes
import datetime
created_at = datetime.datetime.now()
```

### JavaScript/HTMX

```javascript
// ✅ Good: Use Alpine.js for reactivity
<div x-data="{ open: false }">
    <button @click="open = !open">Toggle</button>
    <div x-show="open">Content</div>
</div>

// ✅ Good: HTMX attributes
<button hx-post="/api/submit/" hx-swap="outerHTML">Submit</button>

// Use Prettier for formatting
// Indent: 2 spaces
// Quotes: Single
```

### CSS/Tailwind

```html
<!-- ✅ Good: Use Tailwind utility classes -->
<div class="flex items-center justify-between p-4 bg-white rounded-lg shadow">
    <h2 class="text-lg font-semibold">Title</h2>
</div>

<!-- ❌ Avoid: Inline styles -->
<div style="display: flex; padding: 16px;">...</div>
```

## 🧪 Testing

### Writing Tests

```python
# tests/test_invoice.py
from django.test import TestCase
from accounting.models import Invoice

class InvoiceModelTest(TestCase):
    def setUp(self):
        """Set up test data"""
        self.invoice = Invoice.objects.create(
            number="INV-001",
            amount=1000.00
        )

    def test_invoice_creation(self):
        """Test invoice is created correctly"""
        self.assertEqual(self.invoice.number, "INV-001")
        self.assertEqual(self.invoice.amount, 1000.00)

    def test_invoice_str(self):
        """Test string representation"""
        self.assertEqual(str(self.invoice), "INV-001")
```

### Running Tests

```bash
# All tests
python manage.py test

# Specific app
python manage.py test accounting

# Specific test class
python manage.py test accounting.tests.test_invoice.InvoiceModelTest

# With coverage
coverage run --source='.' manage.py test
coverage report --fail-under=70
coverage html  # Generate HTML report
```

### Coverage Requirements

- **Minimum**: 70% overall coverage
- **New code**: Aim for 90%+ coverage
- **Critical paths**: 100% coverage (authentication, payment, data integrity)

## 📝 Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines (Black, Flake8, isort)
- [ ] All tests pass locally
- [ ] Coverage meets minimum threshold (70%)
- [ ] Documentation updated (if applicable)
- [ ] Pre-commit hooks pass
- [ ] Commit messages follow Conventional Commits
- [ ] Branch is up-to-date with `main`

### PR Template

```markdown
## Description
[Brief description of changes]

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Related Issues
Closes #[issue number]

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed

## Screenshots (if UI changes)
[Add screenshots here]

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] Tests pass locally
- [ ] Coverage meets requirements
```

### Review Process

1. **Automated Checks**: CI pipeline must pass (lint, tests, security)
2. **Code Review**: At least 1 approval from CODEOWNERS required
3. **Address Feedback**: Respond to comments within 48 hours
4. **Merge**: Squash and merge (maintainer will merge)

## 💬 Commit Messages

We follow **Conventional Commits** specification.

### Format

```
<type>(<scope>): <subject>

[optional body]

[optional footer]
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring (no feature/fix)
- `perf`: Performance improvements
- `test`: Adding/updating tests
- `build`: Build system changes
- `ci`: CI/CD changes
- `chore`: Other changes (dependencies, tooling)
- `revert`: Revert previous commit

### Examples

```bash
# Feature
git commit -m "feat(accounting): add invoice PDF export"

# Bug fix
git commit -m "fix(auth): resolve login redirect loop"

# Documentation
git commit -m "docs(readme): update installation instructions"

# Breaking change
git commit -m "feat(api)!: change authentication to OAuth2

BREAKING CHANGE: API now requires OAuth2 tokens instead of API keys"
```

### Rules

- Use imperative mood ("add feature" not "added feature")
- First line ≤100 characters
- Reference issues: `Closes #123`, `Fixes #456`
- Breaking changes: Add `!` after type/scope, explain in footer

## 🐛 Issue Reporting

### Before Creating an Issue

1. **Search existing issues**: Check if already reported
2. **Verify bug**: Reproduce on latest `main` branch
3. **Check documentation**: Ensure it's not expected behavior

### Bug Report Template

```markdown
**Description**
[Clear description of the bug]

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

**Expected Behavior**
[What you expected to happen]

**Actual Behavior**
[What actually happened]

**Environment**
- OS: [e.g., Windows 11]
- Python: [e.g., 3.11.5]
- Django: [e.g., 5.1.2]
- Browser: [e.g., Chrome 120]

**Screenshots**
[If applicable]

**Additional Context**
[Any other relevant information]
```

### Feature Request Template

```markdown
**Problem Statement**
[What problem does this solve?]

**Proposed Solution**
[How should it work?]

**Alternatives Considered**
[What other approaches did you consider?]

**Additional Context**
[Mockups, examples, etc.]
```

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [HTMX Documentation](https://htmx.org/docs/)
- [Alpine.js Documentation](https://alpinejs.dev/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [PEP 8 Style Guide](https://pep8.org/)

## ❓ Questions?

- **General**: [GitHub Discussions](https://github.com/himalytix/erp/discussions)
- **Bugs**: [GitHub Issues](https://github.com/himalytix/erp/issues)
- **Security**: Email security@himalytix.com (do not open public issue)

## 🙏 Thank You!

Your contributions make Himalytix ERP better for everyone. We appreciate your time and effort!

---

**Happy Coding! 🚀**
