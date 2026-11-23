"""Compatibility metadata for older pip/setuptools releases.

The source checkout remains the recommended way to run the dashboard because
the Web workspace and handbook live beside the Python package.
"""
from setuptools import setup


setup(
    name="helix-science-flywheel",
    version="0.1.0",
    description="An evidence-first AI4Science data flywheel reference implementation",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    python_requires=">=3.9",
    packages=["helix"],
)
