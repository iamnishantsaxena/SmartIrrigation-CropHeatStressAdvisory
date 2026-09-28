from setuptools import find_packages, setup

setup(
    name="smart-irrigation-advisor",
    version="0.1.0",
    packages=find_packages(include=["src", "api"]),
    install_requires=open("requirements.txt").read().split(),
    python_requires=">=3.10",
)
