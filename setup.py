"""Setup configuration for home-media package."""

from setuptools import find_packages, setup

# Read version from __version__.py
version = {}
with open("src/python/home_media/__version__.py") as f:
    exec(f.read(), version)

# Read README
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="home-media",
    version=version["__version__"],
    description="AI-powered home media management and classification system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Home Media Team",
    python_requires=">=3.11",
    package_dir={"": "src/python"},
    packages=find_packages(where="src/python"),
    install_requires=[
        "pyyaml>=6.0.1",
        "pandas>=2.1.4",
        "pillow>=10.2.0",
        "exifread>=3.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "jupyter>=1.0.0",
            "notebook>=7.0.6",
            "ipykernel>=6.28.0",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
)
