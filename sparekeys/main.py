#!/usr/bin/env python3

"""\
Create an encrypted archive of the keys and secrets you might need to recover 
from a catastrophic hard-drive failure.

Usage:
    sparekeys [options]
    sparekeys plugins

Subcommands:
    plugins:
        List and briefly describe any installed plugins.

Options:
    -v --verbose
        Output more information, include stack traces.
"""

__version__ = '0.1.0'
__author__ = "Ken & Kale Kundert"
__slug__ = 'sparekeys'

import sys, os, inspect, shlex
import toml, appdirs, docopt

#from typing import Any
#from dataclasses import dataclass
from collections import namedtuple
from pkg_resources import iter_entry_points
from inform import Inform as set_output_prefs, Error, display, comment, narrate, warn, error
from shlib import cd, chmod, cp, ls, mkdir, mount, rm, Run as run, to_path, set_prefs as set_shlib_prefs
from arrow import now
from gnupg import GPG

def main():
    set_shlib_prefs(use_inform=True, log_cmd=True)
    args = docopt.docopt(__doc__)

    if args['--verbose']:
        set_output_prefs(verbose=True, narrate=True)

    try:
        config = load_config()
        if args['plugins']:
            list_plugins(config)
            sys.exit()

        # Get the passcode before building the archive, so if something goes 
        # wrong with the passcode, we don't need to worry about cleaning up the 
        # unencrypted archive.
        passcode = query_passcode(config)
        archive = build_archive(config)
        encrypt_archive(config, archive, passcode)
        publish_archive(config, archive)

    except KeyboardInterrupt:
        print()

    except Error as err:
        if args['--verbose']: raise
        else: error(err)


def load_config():
    config_dir = to_path(appdirs.user_config_dir(__slug__))
    config_path = config_dir / 'config.toml'

    if not config_path.exists():
        display(f"'{config_path}' not found, installing defaults.")
        defaults = to_path(__file__).parent / 'default_config.toml'
        mkdir(config_dir)
        cp(defaults, config_path)

    try:
        config = toml.load(config_path)
    except toml.decoder.TomlDecodeError as err:
        raise Error(err, culprit=config_path)

    # Set default values for options that are accessed in multiple places: 
    config.setdefault('remote_dir', 'backup/sparekeys')
    config.setdefault('archive', {})
    config.setdefault('publish', {})
    config.setdefault('auth', {})

    return config

def query_passcode(config):
    narrate("Getting a passcode for the archive")

    plugins = load_auth_plugins(config)

    for plugin in plugins:
        subconfig = config['auth'].get(plugin.name, {})

        try:
            disabled, passcode = eval_plugin(plugin, config, subconfig)
        except PluginError as err:
            display(f"'{plugin.name}' authentication failed: {err}")
            continue

        if not disabled:
            return passcode

    raise AllAuthFailed(plugins)

def build_archive(config):
    narrate("Building the archive")

    # Make the archive directory:
    date = now().format(config.get('archive_name', 'YYYY-MM-DD'))
    workspace = to_path(appdirs.user_data_dir(__slug__), date)
    archive = to_path(workspace / 'archive')

    rm(workspace)
    mkdir(archive)

    # Apply any 'archive' plugins:
    for plugin in load_plugins('archive'):
        subconfigs = config['archive'].get(plugin.name, [])
        run_plugin(plugin, config, subconfigs, archive)

    return workspace

def encrypt_archive(config, workspace, passcode):
    narrate("Encrypting the archive")

    with cd(workspace):
        run('tar -cf archive.tgz archive', 'soeW')
        with open('archive.tgz', 'rb') as f:
            cleartext = f.read()

        gpg = GPG()
        encrypted = gpg.encrypt(
            cleartext,
            recipients=None,
            symmetric=True,
            passphrase=str(passcode),
        )
        if encrypted.ok:
            with open('archive.tgz.gpg', 'w') as f:
                f.write(str(encrypted))
        else:
            raise EncryptionFailed(encrypted)

        rm('archive.tgz', 'archive')

    script = workspace / 'decrypt.sh'
    script.write_text('''\
#!/bin/sh
# Decrypts the archive.

gpg -d -o archive.tgz archive.tgz.gpg
tar xvf archive.tgz
''')
    chmod(0o700, script, workspace / 'archive.tgz.gpg')
    display(f"Archive '{workspace.name}' created.")

def publish_archive(config, workspace):
    results = []
    for plugin in load_plugins('publish'):
        subconfigs = config['publish'].get(plugin.name, [])
        results += run_plugin(plugin, config, subconfigs, workspace)

    if not results:
        warn(f"No automated publishing rules found.\nMake copies of the archive yourself:\n{workspace}")

def list_plugins(config):
    print("auth:")
    for plugin in load_auth_plugins(config):
        print(' ', plugin.name)

    print()

    print("archive:")
    for plugin in load_plugins('archive'):
        print(' ', plugin.name)

    print()

    print("publish:")
    for plugin in load_plugins('publish'):
        print(' ', plugin.name)


def load_plugins(group):
    plugins = []
    group = '.'.join([__slug__, group])

    for entry_point in iter_entry_points(group=group):
        plugin = entry_point.load()
        plugin.name = entry_point.name
        plugin.module = entry_point.module_name
        plugin.lineno = inspect.getsourcelines(plugin)[1]
        plugin.priority = getattr(plugin, 'priority', 0)
        plugins.append(plugin)

    plugins.sort(key=lambda x: x.lineno)
    plugins.sort(key=lambda x: x.priority, reverse=True)

    return plugins

def load_auth_plugins(config):
    plugins = load_plugins('auth')
    plugins.sort(key=lambda x: config['auth'].get(x, {}).get('priority', 0))
    return plugins

def run_plugin(plugin, config, subconfigs, *args, **kwargs):
    results = []

    if not isinstance(subconfigs, list):
        subconfigs = [subconfigs]
    if not subconfigs:
        subconfigs = [{}]

    for subconfig in subconfigs:
        disabled, result = eval_plugin(
                plugin, config, subconfig, *args, **kwargs)
        if not disabled:
            results.append(result)

    return results

def eval_plugin(plugin, config, subconfig, *args, **kwargs):
    if subconfig.get('disable', False):
        narrate(f"Skipping the '{plugin.name}' plugin: disabled by user")
        return PluginResult(True, None)
    else:
        narrate(f"Running the '{plugin.name}' plugin")

    # Provide select global options to the plugin.
    subconfig.setdefault('remote_dir', config['remote_dir'])

    try:
        result = plugin(subconfig, *args, **kwargs)
        return PluginResult(False, result)

    except SkipPlugin as err:
        narrate(f"Skipping the '{plugin.name}' plugin: {err}")
        return PluginResult(True, None)

    except PluginError as err:
        err.plugin = plugin
        raise


def auth_getpass(config):
    from getpass import getpass

    try:
        while True:
            passcode = getpass("Please enter a password encrypt your spare keys: ")
            verify = getpass("Enter the same password again to check for typos: ")

            if passcode == verify:
                return passcode
            else:
                error("The passwords you entered did not match.\nTry again or type Ctrl-C to exit:\n")

    except EOFError:
        print()
        raise PluginError("Received EOF")

def auth_avendesora(config):
    from avendesora import PasswordGenerator

    if 'account' not in config:
        raise PluginConfigError("No account specified.", config, 'account')

    avendesora = PasswordGenerator()
    account = avendesora.get_account(config['account'])
    return str(account.passcode)

def archive_file(config, archive):
    srcs = require_one_or_more(config, 'src')
    dests = allow_zero_or_more(config, 'dest')
    cmd = config.get('cmd', 'rsync -a --no-specials --no-devices {src} {dest}')
    precmds = allow_zero_or_more(config, 'precmd')
    postcmds = allow_zero_or_more(config, 'precmd')

    # Make sure the 'src' and 'dest' options correspond.
    if not dests:
        dests = [None] * len(srcs)
    if len(srcs) != len(dests):
        raise PluginConfigError("Different number of entries for 'src' ({len(srcs)}) and 'dest' ({len(dests)}).", config, 'src', 'dest')

    def subs_and_run(cmd, paths):
        cmd = [x.format(**paths) for x in shlex.split(cmd)]
        # Shell-mode disabled to eliminate the possibility of getting confused 
        # by spaces/quotes/whatever in file names.
        run(cmd, 's')

    for src, dest in zip(srcs, dests):
        # Resolve the source and destination paths.

        # Use os.path because it preserves the trailing slash, which is 
        # significant to rsync.
        src = os.path.expanduser(src)

        if dest is None:
            dest = archive
        elif os.path.isabs(os.path.expanduser(dest)):
            raise PluginConfigError("'dest' paths cannot be absolute.", config, 'dest')
        else:
            dest = archive / dest

        paths = dict(src=src, dest=dest)

        # Run the commands to copy the file.
        for precmd in precmds:
            subs_and_run(precmd, paths)

        subs_and_run(cmd, paths)

        for postcmd in postcmds:
            subs_and_run(postcmd, paths)

def archive_emborg(config, archive):
    from emborg.command import run_borg
    from emborg.settings import Settings

    copy_to_archive('~/.config/borg', archive)
    copy_to_archive('~/.config/emborg', archive)

    with Settings() as settings:
        cmd = 'borg key export'.split() + [
                settings.repository,
                archive / '.config/borg.repokey',
        ]
        run_borg(cmd, settings)

def archive_avendesora(config, archive):
    copy_to_archive('~/.config/avendesora', archive)

def publish_scp(config, workspace):
    hosts = require_one_or_more(config, 'host')
    remote_dir = config['remote_dir']

    for host in hosts:
        run(['ssh', host, f'mkdir -p {remote_dir}'])
        run(['scp', '-r', workspace, f'{host}:{remote_dir}'])
        display(f"Archive copied to '{host}'.")

def publish_mount(config, workspace):
    drives = require_one_or_more(config, 'drive')
    remote_dir = config['remote_dir']

    for drive in drives:
        try:
            with mount(drive):
                dest = to_path(drive, remote_dir)
                mkdir(dest); rm(dest)
                cp(workspace, dest)
        except Error:
            error(f"'{drive}' not mounted, skipping.")
        else:
            display(f"Archive copied to '{drive}'.")

def copy_to_archive(path, archive):
    src = to_path(path)
    dest = archive / src.relative_to(to_path('~'))
    mkdir(dest.parent)
    cp(src, dest)

def allow_zero_or_more(config, key):
    values = config.get(key, [])
    return values if isinstance(values, list) else [values]

def require_one_or_more(config, key):
    values = allow_zero_or_more(config, key)

    if not values:
        raise SkipPlugin(f"No '{key}' specified.")

    return values

auth_avendesora.priority = 10

PluginResult = namedtuple("PluginResult", "disabled result")

class PluginError(Error):
    pass

class PluginConfigError(PluginError):

    def __init__(self, message, config, *keys):
        super().__init__(message, config, *keys)
        self.message = message
        self.config = config
        self.keys = keys

    def __str__(self):
        return self.message

class SkipPlugin(Error):
    pass

class AllAuthFailed(Error):

    def __init__(self, plugins):
        super().__init__(plugins)
        self.plugins = plugins
        self.plugin_names = [x.name for x in plugins]

    def __str__(self):
        return f"All authentication methods ({', '.join(self.plugin_names)}) failed, cannot encrypt archive."

class EncryptionFailed(Error):
    pass

