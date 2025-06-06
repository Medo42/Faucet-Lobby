from setuptools import setup, find_packages

setup(
    name="faucet-lobby",
    version="0.1.0",
    description="Game server lobby system for Gang Garrison 2 and generic games",
    packages=find_packages(include=["protocols"]),
    py_modules=["config", "expirationset", "lobby", "server", "weblist"],
    package_data={"": ["httpdocs/*"]},
    install_requires=["Twisted", "requests"],
    python_requires=">=3.10",
)
