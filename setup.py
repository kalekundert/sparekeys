#!/usr/bin/env python3
# encoding: utf-8

from setuptools import setup

with open('README.rst') as file:
    readme = file.read()

setup(
    name='sparekeys',
    version='0.1.2',
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
                # needs emborg version 1.2 or greater
            'avendesora=sparekeys:archive_avendesora',
        ],
        'sparekeys.publish': [
            'scp=sparekeys:publish_scp',
            'mount=sparekeys:publish_mount',
        ],
    },
    install_requires=[
        'inform>-1.14',
        'shlib>=1.0',
        'setuptools',
        'toml',
        'appdirs',
        'docopt',
        'python-gnupg>=0.4.3',
    ],
    python_requires = '>=3.6',
    classifiers = [
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Utilities',
    ],
)
