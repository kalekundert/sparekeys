**********
Spare Keys
**********
Spare Keys makes and distributes encrypted copies of the files that you would
need to recover from a catastrophic hard drive failure, e.g. SSH keys, GPG
keys, password vaults, etc.  The basic process goes like this:

- You specify which files you want to keep spare copies of.  You can do this by
  editing a configuration file, or by installing plugins.

- You specify where you want to store encrypted copies of theses files (e.g.
  remote hosts, USB drives, etc.), again via configuration files or plugins.

- Run ``sparekeys`` to automatically create, encrypt, and distribute spare
  copies of the specified files to the specified locations.  A decryption
  script is distributed with the archive, so the only thing you need to
  remember is the password you used for the encryption.

- If you ever lose your hard drive, download the most recent archive from any
  of the backup locations and run the provided decryption script to recover
  your credentials.

.. image:: https://img.shields.io/pypi/v/sparekeys.svg
   :target: https://pypi.python.org/pypi/sparekeys

.. image:: https://img.shields.io/pypi/pyversions/sparekeys.svg
   :target: https://pypi.python.org/pypi/sparekeys

.. image:: https://img.shields.io/readthedocs/sparekeys.svg
   :target: https://sparekeys.readthedocs.io/en/latest/?badge=latest

.. image:: https://img.shields.io/github/workflow/status/kalekundert/sparekeys/Test%20and%20release/master
   :target: https://github.com/kalekundert/sparekeys/actions

.. image:: https://img.shields.io/coveralls/kalekundert/sparekeys.svg
   :target: https://coveralls.io/github/kalekundert/sparekeys?branch=master

Installation
============
Spare Keys can be installed from PyPI::

   $ pip3 install sparekeys

Note that Spare Keys requires python≥3.6.

Usage
=====
To get started, simply run the following command::

   $ sparekeys

This will create and execute a default configuration that will save your SSH
and GPG credentials.  Your credentials won't be copied anywhere, but the path
to the encrypted archive will be shown so that you can copy it yourself.

For more information::

   $ sparekeys -h

Examples
========
Below are some example Spare Keys configuration files to help get you started.
See the Configuration_ and Plugins_ sections for more information on these
options.

Copy SSH and GPG keys to a remote host via ``scp``::

   [plugins]
   archive = ['ssh', 'gpg']
   publish = ['scp']

   [publish.scp]
   host = 'alice@example.com'

Copy SSH and GPG keys to a USB drive mounted at ``/mnt/usb``::

   [plugins]
   archive = ['ssh', 'gpg']
   publish = ['mount']

   [publish.mount]
   drive = '/mnt/usb'

Archive SSH keys, GPG keys, and a cryptocurrency wallet::

   [plugins]
   archive = ['ssh', 'gpg', 'file']

   # There isn't a built-in plugin for wallets (yet), so instead use the "file"
   # plugin to manually specify files to copy.
   [archive.file]
   src = '~/.config/cryptocurrency'

Use your avendesora_ "login" credentials to encrypt the archive.  As a
fallback, prompt for a password (getpass)::

   [plugins]
   archive = ['ssh', 'gpg']
   auth = ['avendesora', 'getpass']

   [auth.avendesora]
   account = 'login'

Configuration
=============
The configuration file is based on the `TOML file format
<https://github.com/toml-lang/toml>`__.  On Linux systems, it can be found at::

   ~/.config/sparekeys/config.toml

Broadly, you need to enable any plugins use with to use, and you need to
configure any plugins that require extra information::

   ## Enable plugins ###############################################

   [plugins]
   # When creating the archive, use the SSH and GPG plugins.
   archive = ['ssh', 'gpg']

   # When publishing the archive, use the 'scp' and 'mount' plugins:
   publish = ['scp', 'mount']

   ## Configure plugins ############################################

   # The SSH and GPG plugins require no further information.

   # The 'scp' plugin needs the address of a remote host:
   [publish.scp]
   host = 'alice@example.com'

   # The 'mount' plugin needs the path of a drive to mount:
   [publish.scp]
   drive = '/mnt/usb'

You can get a list of installed plugins by running ``sparekeys plugins``.  More
information on the built-in plugins is available in the Plugins_ section
below.  The `Plugin API`_ section described how you can make your own plugins.

The ``[plugins]`` block:

- ``archive`` (list): A list of plugins to use for finding important files and
  building the archive.  Built-in options include 'ssh', 'gpg', and 'file'.

- ``publish`` (list): A list of plugins to use when copying the encrypted
  archive to remote destinations.  Built-in options include 'scp' and 'mount'

- ``auth`` (list): A list of plugins to query for a password when encrypting
  archive.  The plugins will be invoked in the order specified until a passcode
  is obtained.  Any subsequent plugins will not be invoked.  If no
  authentication plugins are specified, the built-in 'getpass' plugin (which
  asks for a passcode in the terminal) will be used.  If no passcode can be
  obtained, the archive will not be created.

**The configuration blocks:**

The remaining blocks provide configuration options specific to individual
plugins.  The block follow the naming pattern: ``[STAGE.PLUGIN]``.  ``STAGE``
is the category of plugin, e.g. one of ``archive``, ``publish``, or ``auth``.
``PLUGIN`` is the name of the plugin, which could be anything.  Within the
block go any options relating to the plugin in question.  Each plugin
understands a different set of options.

Below is an example configuration block for the ``publish.scp`` plugin, which
describes how to copy the archive to a remote host via scp::

   [publish.scp]
   host = ['alice@home.net', 'alice@work.com']
   remote_dir = 'backup'

It is also possible to specify multiple configuration blocks for any individual
plugin (except the authentication plugins).  If you do this, the plugin will be
executed once for each such block.  For example, the following configuration
would publish the spare keys to two different directories on two different
remote hosts::

   [[publish.scp]]
   host = 'alice@home.net'
   remote_dir = 'backup'

   [[publish.scp]]
   host = 'alice@work.com'
   remote_dir = '/backups/alice/'

**Top-level options:**

- ``archive_name`` (str, default: ``'{host}'``): A format string that will be
  used to name each archive.  The following values can be substituted using the
  standrad python formatting syntax:

   - ``{user}``: The name of the logged-in user.
   - ``{host}``: The name of the current machine.
   - ``{date:YYYYMMDD}``: The current date.  The characters after the colon
     specify how the date should be `formatted
     <https://arrow.readthedocs.io/en/latest/#format>`__.

Plugins
=======
Spare Keys supports the use of setuptools plugins to customize the backup
process.  Below are descriptions of all the built-in plugins:

``archive.ssh``
   Copy the ``.ssh`` directory into the archive.  No configuration options.

``archive.gpg``
   Copy the ``.gpg`` directory into the archive.  No configuration options.

``archive.file``
   Copy arbitrary files into the archive.  This plugin is provided to make it
   easy to copy valuable files for which devoted plugins are not available.
   The following option must be configured:

   - ``src`` (str or list): One or more paths to copy.  The copied file(s) will
     have the same path relative to the archive as the original file(s) have
     relative to the home directory.

``archive.emborg``
   Copy files for `borg backup <https://www.borgbackup.org/>`__ and its `emborg
   front-end <https://github.com/KenKundert/emborg>`__ into the archive.  These
   files include the keys and configuration options necessary to recover your
   backups.  The ``borg key export`` command is run to download keys for
   'repokey' backups, protecting against corruption in the backup archive.

   - ``config`` (str): Name of emborg configuration to use. If not given the 
     default configuration is used.

``archive.avendesora``
   Copy configuration files for the avendesora_ password manager into the
   archive.

   No configuration options.

``publish.scp``
   Copy the encrypted archive to a remote host via ``scp``.  The following
   configuration options are available:

   - ``host`` (str or list, required): The name(s) of the remote host(s) to
     copy the archive to.  Any format understood by SSH is acceptable.

   - ``remote_dir`` (str, default: ``'backup/sparekeys'``): The directory where
     the spare keys should be stored on the remote host.

``publish.mount``
   Copy the encrypted archive to a mounted/mountable drive.
   For example, it might be a good idea to copy your keys onto a USB drive
   which could be stored in a safe-deposit box.  The following configuration
   options are available:

   - ``drive`` (str): The path to the mountpoint for the drive, which must be
     present and configured in ``/etc/fstab``.  If the drive is not mounted
     when Spare Keys runs, Spare Keys will attempt to mount it and will (if
     successful) unmount it when finished.  If the drive is mounted when Spare
     Keys runs, Spare Keys will leave it mounted.

   - ``remote_dir`` (str, default: ``'backup/sparekeys'``): The directory where
     the spare keys should be stored on the mounted drive.

``auth.getpass``
   Get a passcode for the archive by prompting for one in the terminal.  The
   passcode is never printed to the terminal and never saved anywhere.  This
   plugin is special in that it is the default if no other authentication
   plugins are enabled.

``auth.avendesora``
   Get a passcode for the archive from avendesora_.

   - ``account`` (str): The name of the account to get the passcode for.  It's
     recommended to use a password you have completely memorized (e.g. a login
     password), because avendesora itself is unlikely to be available to you if
     you ever need to recover your keys.  This configuration option is required.
   - ``field`` (str): The name of the account field that contains the password 
     or pass phrase. If not given, avendesora chooses a likely candidate for 
     you.

Plugin API
==========
Plugins can be installed using the `setuptools Entry Points API
<https://amir.rachum.com/blog/2017/07/28/python-entry-points/>`__::

   setup(
      ...
      entry_points={
          'sparekeys.archive': [
              'spam=package.module:archive_spam',
          ],
          'sparekeys.publish': [
              'spam=package.module:publish_spam',
          ],
          'sparekeys.auth': [
              'spam=package.module:auth_spam',
          ],
      },
      ...
   )

Currently, three entry points are supported: ``sparekeys.archive``,
``sparekeys.publish``, and ``sparekeys.auth``.  These entry points correspond
to the three categories of plugins detailed in the Configuration_ section
above.  Each plugin must have a unique name within its category ("spam" in the
example above).

An ``archive`` plugin must be a function that accepts two arguments:

- A dictionary with any configuration values specific to the plugin.
- The path to the archive.

The function must copy any necessary files into the archive, possibly after
doing more complicated things like generating or downloading said files.  The
``sparekeys.copy_to_archive()`` utility is often useful for these plugins.  It
copies files into the archive such that their path within the archive is the
same as their path relative to the home directory.  Below is an example that
copies ``~/.config/spam`` into the archive::

   def archive_spam(config, archive):
       sparekeys.copy_to_archive('~/.config/spam', archive)

A ``publish`` plugin must be a function that accepts two arguments:

- A dictionary with any configuration values specific to the plugin.
- The path the directory containing the encrypted archive (called
  ``archive.tgz.gpg``) and the decryption script (called ``decrypt.sh``).

The plugin should copy the encrypted archive to a remote destination.  Below is
an example that simply copies the archive to ``~/spam``::

   def publish_spam(config, workspace):
      cp(workspace, '~/spam')

An ``auth`` plugin must be a function that accepts one argument:

- A dictionary with any configuration values specific to the plugin.

The plugin should either return a passcode or raise one of the exceptions
detailed below.  A typical plugin might query a particular password valut,
using an account specified in the given configuration.  Below is an example
that simply returns the string "spam"::

   def auth_spam(config):
       return "spam"

**Exceptions:**

Plugins can raise the following exceptions:

- ``SkipPlugin``: The plugin can't do its job for some reason.  A warning will
  be printed, but the program will continue.

- ``PluginConfigError``: Something about the plugin's configuration doesn't
  make sense and/or is missing.  The program will be stopped and an informative
  error will be displayed.

- ``PluginError``: Something else went wrong.  The program will be aborted
  immediately and an informative error will be displayed..

.. _avendesora: https://github.com/kenkundert/avendesora
