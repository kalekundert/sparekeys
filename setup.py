#!/usr/bin/env python3
# encoding: utf-8

from setuptools import setup

with open('README.rst') as file:
    readme = file.read()

setup(
    name='sparekeys',
    version='0.1.0',
    author='Kale Kundert',
    author_email='kale@thekunderts.net',
    long_description=readme,
    packages=[
        'sparekeys',
    ],
    package_data = {
        'sparekeys': [
            'default_config.toml',
        ],
    },
    entry_points={
        'console_scripts': [
            'sparekeys=sparekeys:main',
        ],
        'sparekeys.auth': [
            'getpass=sparekeys:auth_getpass',
            'avendesora=sparekeys:auth_avendesora',
        ],
        'sparekeys.archive': [
            'ssh=sparekeys:archive_ssh',
            'gpg=sparekeys:archive_gpg',
            'file=sparekeys:archive_file',
            'emborg=sparekeys:archive_emborg',
                # wants emborg=>1.1, but that version is not available yet.
            'avendesora=sparekeys:archive_avendesora',
        ],
        'sparekeys.publish': [
            'scp=sparekeys:publish_scp',
            'mount=sparekeys:publish_mount',
        ],
    },
    install_requires=[
        'inform',
        'shlib',
        'setuptools',
        'toml',
        'appdirs',
        'docopt',
        'python-gnupg>=0.4.3',
    ],
)
