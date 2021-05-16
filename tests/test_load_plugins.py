#!/usr/bin/env python3

import pytest
from sparekeys import *

def load_plugin_names(config, stage, defaults=None):
    plugins = select_plugins(config, stage, defaults)
    return [f'{x.stage}.{x.name}' for x in plugins]


def test_load_plugins():
    config = {
        'plugins': {
            'archive': [
                'file',
            ],
            'auth': [
                'getpass',
            ],
            'publish': [
                'scp',
                'mount',
            ],
        },
    }
    assert load_plugin_names(config, 'archive') == ['archive.file']
    assert load_plugin_names(config, 'auth')    == ['auth.getpass']
    assert load_plugin_names(config, 'publish') == ['publish.scp', 'publish.mount']

def test_empty_config():
    assert load_plugin_names({}, 'archive') == []
    assert load_plugin_names({}, 'auth')    == []
    assert load_plugin_names({}, 'publish') == []

def test_wrong_type():
    config = {
        'plugins': {
            'archive': 'file'
        },
    }
    with pytest.raises(ConfigError, match=r"'plugins\.archive'.*, not str"):
        select_plugins(config, 'archive')

def test_not_installed():
    config = {
        'plugins': {
            'archive': [
                'not_installed',
            ]
        },
    }
    with pytest.raises(ConfigError, match=r"'archive' plugin is.*: not_installed"):
        select_plugins(config, 'archive')


