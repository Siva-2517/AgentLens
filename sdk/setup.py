"""Setup configuration for AgentLens SDK."""

from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="agentlensx",
    version="0.1.0",
    author="AgentLens Team",
    description="AI-powered observability SDK for AI agents",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="MIT",
    packages=["agentlensx"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=[
        "httpx>=0.27.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "black>=24.0.0",
            "ruff>=0.5.0",
        ],
    },
)
