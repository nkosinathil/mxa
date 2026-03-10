from setuptools import setup, find_packages

setup(
    name="forensic_toolkit",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "pandas",
        "chardet",
        "beautifulsoup4",
        "openpyxl",
    ],
    entry_points={
        "console_scripts": [
            "forensic-toolkit=forensic_toolkit.cli:main",
        ],
    },
)
