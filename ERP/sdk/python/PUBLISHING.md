# Python SDK Publishing Guide

## 📦 Publishing to PyPI

This guide walks you through publishing the Himalytix ERP Python SDK to PyPI.

---

## Prerequisites

1. **PyPI Account:**
   - Create account at https://pypi.org/account/register/
   - Verify email address

2. **Install Build Tools:**
   ```bash
   pip install --upgrade pip build twine
   ```

3. **API Token:**
   - Go to https://pypi.org/manage/account/token/
   - Create new API token
   - Save token securely (you'll only see it once)

---

## Step-by-Step Publishing

### 1. Update Version Number

Edit `setup.py` and `himalytix/__init__.py`:

```python
# setup.py
version="1.0.0"  # Increment for new releases

# himalytix/__init__.py
__version__ = "1.0.0"
```

**Version Numbering (Semantic Versioning):**
- `1.0.0` - Major release (breaking changes)
- `1.1.0` - Minor release (new features, backward compatible)
- `1.0.1` - Patch release (bug fixes)

### 2. Clean Previous Builds

```powershell
# Remove old build artifacts
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path *.egg-info) { Remove-Item -Recurse -Force *.egg-info }
```

### 3. Build Distribution

```bash
# Build source distribution and wheel
python -m build

# You should see:
# dist/
#   himalytix-erp-client-1.0.0.tar.gz
#   himalytix_erp_client-1.0.0-py3-none-any.whl
```

### 4. Test on Test PyPI (Optional but Recommended)

```bash
# Upload to Test PyPI first
twine upload --repository testpypi dist/*

# Install from Test PyPI to verify
pip install --index-url https://test.pypi.org/simple/ himalytix-erp-client

# Test installation
python -c "from himalytix import HimalytixClient; print('OK')"
```

### 5. Upload to PyPI

```bash
# Upload to production PyPI
twine upload dist/*

# You'll be prompted for credentials:
# Username: __token__
# Password: pypi-AgEIcHlwaS5vcmcC...  (your API token)
```

### 6. Verify Publication

```bash
# Install from PyPI
pip install himalytix-erp-client

# Test import
python -c "from himalytix import HimalytixClient; print(HimalytixClient.__doc__)"

# Check version
python -c "import himalytix; print(himalytix.__version__)"
```

---

## Automated Publishing with GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish Python SDK

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*
```

**Setup:**
1. Add PyPI token to GitHub secrets as `PYPI_API_TOKEN`
2. Create release on GitHub
3. Package automatically published to PyPI

---

## Configuration Files

### `.pypirc` (Optional - Store Credentials)

Create `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmcC...

[testpypi]
username = __token__
password = pypi-AgEIcHlwaS5vcmcC...
```

**Security:** Add to `.gitignore`, never commit to version control!

---

## Publishing Checklist

Before publishing, verify:

- [ ] Version number updated in `setup.py` and `__init__.py`
- [ ] `README.md` is comprehensive and formatted correctly
- [ ] `CHANGELOG.md` updated with release notes
- [ ] All tests passing (`pytest`)
- [ ] Code formatted (`black`, `isort`)
- [ ] Type hints checked (`mypy`)
- [ ] `requirements.txt` dependencies correct
- [ ] `LICENSE` file included
- [ ] `MANIFEST.in` includes all necessary files
- [ ] Built and tested locally
- [ ] Tested on Test PyPI
- [ ] Git tagged with version (`git tag v1.0.0`)

---

## Updating an Existing Package

```bash
# 1. Increment version
# Edit setup.py: version="1.0.1"

# 2. Update CHANGELOG.md
# Document changes

# 3. Commit changes
git add .
git commit -m "Release v1.0.1"
git tag v1.0.1
git push origin main --tags

# 4. Build and publish
python -m build
twine upload dist/*
```

---

## Common Issues

### Issue: Package name already taken

**Solution:** Change package name in `setup.py`:
```python
name="himalytix-erp-client-yourcompany"
```

### Issue: Upload fails with 403 Forbidden

**Solution:** 
- Verify API token is correct
- Ensure token has upload permissions
- Check if version already exists (can't overwrite)

### Issue: README not rendering on PyPI

**Solution:**
- Ensure `long_description_content_type="text/markdown"` in `setup.py`
- Test with `python setup.py check --restructuredtext --strict`

### Issue: Import error after installation

**Solution:**
- Check `MANIFEST.in` includes all source files
- Verify `packages=find_packages()` in `setup.py`
- Test in fresh virtual environment

---

## Best Practices

1. **Version Control:**
   - Tag each release: `git tag v1.0.0`
   - Maintain `CHANGELOG.md`
   - Use semantic versioning

2. **Testing:**
   - Always test on Test PyPI first
   - Test installation in clean virtual environment
   - Run full test suite before publishing

3. **Documentation:**
   - Keep README.md up to date
   - Include code examples
   - Document breaking changes

4. **Security:**
   - Never commit credentials
   - Use API tokens instead of passwords
   - Rotate tokens periodically

5. **Automation:**
   - Use GitHub Actions for releases
   - Run tests in CI before publishing
   - Automate version bumping

---

## Example Release Process

```bash
# 1. Create feature branch
git checkout -b feature/new-endpoint

# 2. Make changes
# ... edit code ...

# 3. Run tests
pytest

# 4. Format code
black himalytix/
isort himalytix/

# 5. Commit and push
git add .
git commit -m "Add support for new endpoint"
git push origin feature/new-endpoint

# 6. Create pull request
# ... merge to main ...

# 7. Update version and changelog
# Edit setup.py, __init__.py, CHANGELOG.md

# 8. Tag release
git tag v1.1.0
git push origin v1.1.0

# 9. Build and publish
python -m build
twine upload dist/*

# 10. Verify on PyPI
pip install --upgrade himalytix-erp-client
python -c "import himalytix; print(himalytix.__version__)"
```

---

## Resources

- **PyPI:** https://pypi.org
- **Test PyPI:** https://test.pypi.org
- **Packaging Guide:** https://packaging.python.org/
- **Twine Docs:** https://twine.readthedocs.io/
- **Semantic Versioning:** https://semver.org/

---

**Ready to publish? Run:**

```bash
python -m build && twine upload dist/*
```

🎉 **Your SDK is now available on PyPI!**
