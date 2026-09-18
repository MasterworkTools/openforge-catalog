#!/usr/bin/env python

from setuptools import setup

with open("requirements.txt") as f:
    required = f.read().splitlines()

setup(
    install_requires=required,
    packages=["openforge"],
    scripts=["bin/db_update", "bin/dropbox_scanner", "bin/fixtures"],
    package_data={
        "openforge/db/fixtures": ["*.json", "*.yaml"],
        "openforge/openapi": ["*.yaml"],
    },
)
