from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="pretty-history-claude-code",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Claude Code history viewer - Format Claude Code session history files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shiroinock/pretty-history-claude-code",
    project_urls={
        "Bug Reports": "https://github.com/shiroinock/pretty-history-claude-code/issues",
        "Source": "https://github.com/shiroinock/pretty-history-claude-code",
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="claude, claude-code, history, viewer, formatter",
    package_dir={"": "src"},
    py_modules=[
        "claude_history"
    ],
    python_requires=">=3.6, <4",
    install_requires=[],  # No external dependencies!
    entry_points={
        "console_scripts": [
            "claude-history=claude_history:main",
        ],
    },
)