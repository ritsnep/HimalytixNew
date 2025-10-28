#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Himalytix ERP Python SDK
Official Python client library for the Himalytix ERP API
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="himalytix-erp-client",
    version="1.0.0",
    author="Himalytix Development Team",
    author_email="dev@himalytix.com",
    description="Official Python SDK for the Himalytix ERP API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/himalytix/python-sdk",
    project_urls={
        "Bug Tracker": "https://github.com/himalytix/python-sdk/issues",
        "Documentation": "https://docs.himalytix.com",
        "Source Code": "https://github.com/himalytix/python-sdk",
        "API Reference": "https://api.himalytix.com/docs/",
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Office/Business :: Financial :: Accounting",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
            "isort>=5.12.0",
            "responses>=0.23.0",
        ],
        "async": [
            "httpx>=0.24.0",
            "aiofiles>=23.2.0",
        ],
    },
    keywords="himalytix erp api sdk client accounting journal",
    include_package_data=True,
    zip_safe=False,
)
