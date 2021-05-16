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
    -y --yes
        Don't prompt for any information, and assume the answer to any 
        question is yes.  This is necessary if running in the background.

    -v --verbose
        Output more information, include stack traces.

    -q --quiet
        Eliminate any unnecessary output (implies --yes).
"""

__version__ = '0.1.4'
__author__ = "Ken & Kale Kundert"
__slug__ = 'sparekeys'

import sys, os, shlex
import toml, appdirs, docopt
import pkg_resources

from collections import namedtuple
from pkg_resources import iter_entry_points
from inform import (
    display, error, Error, fatal, full_stop, get_informer,
    Inform as set_output_prefs, narrate, os_error, output, plural, terminate,
    warn,
)
from shlib import (
    cd, chmod, cp, ls, mkdir, mount, rm, Run as run, to_path, set_prefs as
    set_shlib_prefs
)
from textwrap import shorten
from functools import lru_cache
from shutil import get_terminal_size
from getpass import getuser
from socket import gethostname
from arrow import now
from gnupg import GPG

PARAMS = {
    'date': now(),
    'user': getuser(),
    'host': gethostname(),
}

def main():
    """
    Construct, encrypt, and publish backup keys.  

    As the primary entry point for the end user, this function is also 
    responsible for integrating information from command-line arguments, 
    configuration files, and `setuptools` plugins.
    """
    set_shlib_prefs(use_inform=True, log_cmd=True)
    args = docopt.docopt(__doc__)

    if args['--verbose']:
        set_output_prefs(verbose=True, narrate=True)
    elif args['--quiet']:
        set_output_prefs(quiet=True)

    try:
        config_path, config = load_config()
        try:
            if args['plugins']:
                list_plugins(config)
                sys.exit()

            # Get the passcode before building the archive, so if something 
            # goes wrong with the passcode, we don't need to worry about 
            # cleaning up the unencrypted archive.
            passcode = query_passcode(config)
            batch = args['--yes'] or args['--quiet']
            archive = build_archive(config, not batch)
            encrypt_archive(config, archive, passcode)
            publish_archive(config, archive)

        except ConfigError as e:
            e.reraise(culprit=config_path)
        finally:
            if 'archive' in locals():
                delete_archive(config, archive)

    except KeyboardInterrupt:
        print()

    except Error as e:
        if args['--verbose']: raise
        else: e.report()

    except OSError as e:
        fatal(os_error(e))

    terminate()


def load_config():
    config_dir = to_path(appdirs.user_config_dir(__slug__))
    config_path = config_dir / 'config.toml'
    inform = get_informer()
    inform.set_logfile(config_dir / 'log')

    if not config_path.exists():
        display(f"'{config_path}' not found, installing defaults.")
        defaults = to_path(__file__).parent / 'default_config.toml'
        mkdir(config_dir)
        cp(defaults, config_path)

    try:
        config = toml.load(config_path)
    except toml.decoder.TomlDecodeError as e:
        raise ConfigError(str(e), culprit=config_path)

    # Set default values for options that are accessed in multiple places: 
    config.setdefault('plugins', {})
    config['plugins'].setdefault('archive', [])
    config['plugins'].setdefault('auth', [])
    config['plugins'].setdefault('publish', [])

    return config_path, config

def query_passcode(config):
    narrate("Getting a passcode for the archive")

    # The authentication system is special in that if no plugins are specified, 
    # the 'getpass' plugin will be used by default.
    plugins = select_plugins(config, 'auth', ['getpass'])

    # Try each authentication method until one works.
    for plugin in plugins:
        subconfig = config.get('auth', {}).get(plugin.name, {})

        try:
            return eval_plugin(plugin, config, subconfig)

        except SkipPlugin as e:
            display(f"Skipping '{plugin.name}' authentication: {e}")
            continue

    raise AllAuthFailed(plugins)

def build_archive(config, interactive=True):
    narrate("Building the archive")

    plugins = select_plugins(config, 'archive')
    if not plugins:
        raise ConfigError(f"'plugins.archive' not specified, nothing to do.")

    # Make the archive directory:
    name = config.get('archive_name', '{host}').format(**PARAMS)
    workspace = to_path(appdirs.user_data_dir(__slug__), name)
    archive = to_path(workspace / 'archive')

    rm(workspace)
    mkdir(archive)

    # Apply any 'archive' plugins:
    for plugin in plugins:
        subconfigs = config.get('archive', {}).get(plugin.name, [])
        run_plugin(plugin, config, subconfigs, archive)

    # Show the user which files were included in the archive.
    display("The following files were included in the archive:")

    for root, _, files in os.walk(archive):
        root = to_path(root).relative_to(archive)
        for file in files: 
            display('   ', root / file)
    display()

    if interactive:
        input("Is this correct? <Enter> to continue, <Ctrl-C> to cancel: ")

    return workspace

def encrypt_archive(config, workspace, passcode):
    narrate("Encrypting the archive")

    with cd(workspace):
        run('tar -cf archive.tgz archive', 'soEW')
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

gpg -d -o - archive.tgz.gpg | tar xvf -
''')
    chmod(0o700, script, workspace / 'archive.tgz.gpg')
    narrate(f"Local archive '{workspace.name}' created.")

def publish_archive(config, workspace):
    results = []

    for plugin in select_plugins(config, 'publish'):
        subconfigs = config['publish'].get(plugin.name, [])
        results += run_plugin(
                plugin, config, subconfigs, workspace,
        )

    if not results:
        error(f"No automated publishing rules found.")

    return bool(results)

def delete_archive(config, workspace):
    rm(workspace)

def list_plugins(config):
    # Work out the width of each column:
    stages = 'archive', 'publish', 'auth'
    defaults = {'auth': ['getpass']}
    max_on = 2
    max_type = max(
            len(x)
            for x in stages
    )
    max_name = max(
            len(k)
            for stage in stages
            for k in load_plugins(stage)
    )
    max_width = get_terminal_size().columns - 1
    max_desc = max_width - max_on - max_type - max_name - 3 * 2

    row = "{:%ds}  {:%ds}  {:%ds}  {:%ds}" % (max_on, max_type, max_name, max_desc)
    header = row.format("On", "Stage", "Name", "Description")
    rule = '─' * max_width

    output(rule)
    output(header)
    output(rule)

    for stage in stages:
        installed = load_plugins(stage).values()
        enabled = select_plugins(config, stage, defaults.get(stage))
        plugins = enabled + [x for x in installed if x not in enabled]

        for i, plugin in enumerate(plugins):
            summary = (plugin.__doc__ or "No summary").strip().split('\n')[0]
            output(row.format(
                '*' if plugin in enabled else '',
                stage if i == 0 else '',
                plugin.name,
                shorten(summary, width=max_desc, placeholder='...'),
            ))

        output(rule)


@lru_cache()
def load_plugins(stage):
    plugins = {}
    group = '.'.join([__slug__, stage])

    # Load any plugins that are installed.
    for entry_point in iter_entry_points(group=group):
        plugin = entry_point.load()
        plugin.name = entry_point.name
        plugin.module = entry_point.module_name
        plugin.stage = stage
        plugins[plugin.name] = plugin

    return plugins

def select_plugins(config, stage, defaults=None):
    installed_plugins = load_plugins(stage)

    # Return the plugins that have been enabled by the user for this stage.
    selection = config.get('plugins', {}).get(stage) or defaults or []
    if not isinstance(selection, list):
        raise ConfigError(f"Expected 'plugins.{stage}' to be a list, not {selection.__class__.__name__}.")

    unknown_plugins = set(selection) - set(installed_plugins)
    if unknown_plugins:
        raise ConfigError(f"The following '{stage}' {plural(unknown_plugins):plugin/ is/s are} not installed: {', '.join(unknown_plugins)}")

    return [installed_plugins[x] for x in selection]

def run_plugin(plugin, config, subconfigs, *args, **kwargs):
    results = []

    # If multiple "subconfig" blocks are present for a plugin, the plugin will 
    # be executed once for each such block.  If no blocks are present, the 
    # plugin will be executed just once.

    if not isinstance(subconfigs, list):
        subconfigs = [subconfigs]
    if not subconfigs:
        subconfigs = [{}]

    for subconfig in subconfigs:
        try:
            result = eval_plugin(plugin, config, subconfig, *args, **kwargs)
            results.append(result)

        except SkipPlugin:
            display(f"Skipping the '{plugin.stage}.{plugin.name}' plugin: {e}")
            continue

    return results

def eval_plugin(plugin, config, subconfig, *args, **kwargs):
    narrate(f"Running the '{plugin.stage}.{plugin.name}' plugin")

    try:
        return plugin(subconfig, *args, **kwargs)

    except PluginError as e:
        e.plugin = plugin
        raise


def auth_getpass(config):
    """
    Prompt for a passcode the encrypt the archive with.
    """
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
        raise SkipPlugin("Received EOF")

def auth_avendesora(config):
    """
    Get a passcode to from avendesora.
    """
    from avendesora import PasswordGenerator

    if 'account' not in config:
        raise PluginConfigError("No account specified.", config, 'account')

    avendesora = PasswordGenerator()
    account = avendesora.get_account(config['account'])
    fieldname = config.get('field')
    if fieldname:
        return str(account.get_value(fieldname))
    else:
        return str(account.get_passcode())

def archive_ssh(config, archive):
    """
    Copy `~/.ssh` into the archive.
    """
    copy_to_archive('~/.ssh', archive)

def archive_gpg(config, archive):
    """
    Copy `~/.gnupg` into the archive.
    """
    dest = archive / '.gnupg'; mkdir(dest)
    # Don't try to copy sockets (S.*); it won't work.
    srcs = list(ls('~/.gnupg', reject='S.*'))
    cp(srcs, dest)

def archive_file(config, archive):
    """
    Copy arbitrary files into the archive.
    """
    for src in require_one_or_more(config, 'src'):
        copy_to_archive(src, archive)

def archive_emborg(config, archive):
    """
    Copy `~/.config/borg` and `~/.config/emborg` into the archive.
    """
    from emborg import Emborg

    copy_to_archive('~/.config/borg', archive)
    copy_to_archive('~/.config/emborg', archive)

    with set_output_prefs(prog_name='emborg'):
        with Emborg(name=config.get('config')) as emborg:
            emborg.run_borg(
                cmd = 'key export',
                args = [emborg.destination(), archive / '.config/borg.repokey']
            )

def archive_avendesora(config, archive):
    """
    Copy `~/.config/avendesora` into the archive.
    """

    copy_to_archive('~/.config/avendesora', archive)

def publish_scp(config, workspace):
    """
    Copy the archive to one or more remote hosts via `scp`.
    """
    hosts = require_one_or_more(config, 'host')
    remote_dir = config.get('remote_dir', 'backup/sparekeys')
    remote_dir = remote_dir.format(**PARAMS)
    run_flags = 'sOEW' if get_informer().quiet else 'soEW'

    for host in hosts:
        try:
            run(['ssh', host, f'mkdir -p {remote_dir}'], run_flags)
            run(['scp', '-r', workspace, f'{host}:{remote_dir}'], run_flags)
        except Error as e:
            e.reraise(codicil=e.cmd)
        display(f"Archive copied to '{host}'.")

def publish_mount(config, workspace):
    """
    Copy the archive to one or more mounted/mountable drives.
    """
    drives = require_one_or_more(config, 'drive')
    remote_dir = config.get('remote_dir', 'backup/sparekeys')
    remote_dir = remote_dir.format(**PARAMS)

    for drive in drives:
        narrate(f"copying archive to '{drive}'.")
        try:
            with mount(drive):
                dest = to_path(drive, remote_dir)
                rm(dest); mkdir(dest)
                cp(workspace, dest)
        except Error as e:
            error(e, culprit=drive, codicil='Skipping.')
        else:
            display(f"Archive copied to '{drive}'.")

def publish_email(config, workspace):
    """
    Attach the archive in an email to yourself.
    """
    raise NotImplementedError

    # https://realpython.com/python-send-email/#option-2-setting-up-a-local-smtp-server
    import email, smtplib, ssl
    from email import encoders
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    # Load all the necessary information from the config file.
    sender = config.get('sender', '{user}@{host}').format(**PARAMS)
    recipient = require(config, 'recipient').format(**PARAMS)
    subject = config.get('subject', 'Spare Keys').format(**PARAMS)
    body = config.get('body', '').format(**PARAMS)
    smtp_host = require(config, 'smtp_host')
    smtp_port = require(config, 'smtp_port')

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject

    # Add body to the email.
    message.attach(MIMEText(body, "plain"))

    # Add attachments to the email.
    attachments = [
            'archive.tgz.gpg',
            'decrypt.sh',
    ]

    for attachment in attachemnts:
        path = workspace / attachment

        # Open the attachment file in binary mode
        with path.open('rb') as f:
            # Add file as application/octet-stream
            # Email clients can usually download this MIME-type automatically.
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())

        # Encode file in ASCII characters to send by email    
        encoders.encode_base64(part)

        # Add header as key/value pair to attachment part
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={attachment}",
        )

        # Add attachment to message and convert message to string
        message.attach(part)

    text = message.as_string()

    # Log in to server using secure context and send email
    password = input("Type your email password and press enter:")

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.sendmail(sender_email, receiver_email, text)


def copy_to_archive(path, archive):
    src = to_path(path)
    dest = archive / src.relative_to(to_path('~'))
    mkdir(dest.parent)
    cp(src, dest)

def require(config, key):
    try: value = config[key]
    except KeyError:
        raise SkipPlugin(f"No '{key}' specified.")

def require_one_or_more(config, key):
    values = allow_zero_or_more(config, key)

    if not values:
        raise SkipPlugin(f"No '{key}' specified.")

    return values

def allow_zero_or_more(config, key):
    values = config.get(key, [])
    return values if isinstance(values, list) else [values]

class ConfigError(Error):
    pass

class PluginError(Error):
    pass

class PluginConfigError(PluginError, ConfigError):
    # Is it safe to do diamond inheritance with Error?  Not totally sure...

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

