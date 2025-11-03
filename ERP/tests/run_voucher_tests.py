"""
Convenience runner for voucher CRUD tests.

Usage:
    python -m pytest ERP/tests/test_voucher_crud.py -v

Or run this script directly:
    python ERP/tests/run_voucher_tests.py
"""
import sys


def main():
    try:
        import pytest  # type: ignore
    except Exception as exc:
        print("pytest is required. Install with: pip install -r ERP/requirements.txt")
        raise exc

    args = ["ERP/tests/test_voucher_crud.py", "-v"]
    sys.exit(pytest.main(args))


if __name__ == "__main__":
    main()

