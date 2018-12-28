*******************************
Spare Keys
*******************************
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

.. image:: https://img.shields.io/travis/kalekundert/sparekeys.svg
   :target: https://travis-ci.org/kalekundert/sparekeys

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

Configuration
=============
The configuration file is based on the TOML file format.  On Linux systems, it 
can be found at::

   ~/.config/sparekeys/config.toml

The basic syntax is as follows (lower-case words are literal, upper-case words 
would be replaced by meaningful values)::

   [archive.PLUGIN_1]
   OPTION = VALUE

   [publish.PLUGIN_2]
   OPTION = VALUE

   [auth.PLUGIN_3]
   OPTION = VALUE

   # It's also possible to specify multiple sets of options for the same
   # plugin:

   [[archive.PLUGIN_4]]
   OPTION = VALUE_3A

   [[archive.PLUGIN_4]]
   OPTION = VALUE_3B

   # Any plugin an be disabled like so:

   [archive.PLUGIN_5]
   disable = true

Basically, there are three things that Spare Keys does:

- "archive": Find important files and copy them into an archive.
- "auth": Encrypt the archive using a password.
- "publish": Copy the encrypted archive to remote destinations.

Each of these processes can be executed in different ways by different 
"plugins".  See the Plugins_ section below for more details.  Options can be 
specified for each plugin in the corresponding block.  Below are the options 
understood by the built-in plugins:

``[archive.file]``
   Copy files (local or remote) into the archive.

   - ``src`` (str or list): One or more files to copy into the archive.  
     Trailing slashes are significant, because these paths will be passed to 
     ``rsync`` (by default).  See ``man rsync`` for more information.

   - ``dest`` (str or list): The names to give the copied files in the archive.  
     By default, the original name is kept.  If specified, there must be 
     exactly one ``dest`` for each ``src``.

   - ``cmd`` (str): The command to use to copy the files.  ``{src}`` and 
     ``{dest}`` will be replaced by the source and destination paths, 
     respectively.  The default command is:: 
     
         rsync -a --no-specials --no-devices {src} {dest}

   - ``precmd`` (str or list): One or more commands to run before copying each 
     file.
      
   - ``postcmd`` (str or list): One or more commands to run after copying each 
     file.

``[publish.scp]``
   Copy the encrypted archive to a remote SSH host.

   - ``host`` (str or list): One or more SSH hosts.

   - ``remote_dir`` (str): Where to save the spare keys on the remote host 
     (relative to the home directory).  The default is ``backup/sparekeys``.

``[publish.mount]``
   Copy the encrypted archive to a mount-able drive (e.g. a USB drive).

   - ``drive`` (str or list): One or more mountable drives.  The specified 
     drives must exist in ``/etc/fstab``.

   - ``remote_dir`` (str): Where to save the spare keys on the mounted drive 
     (relative to the home directory).  The default is ``backup/sparekeys``.

The following top-level options are also available:

- ``archive_name`` (str): A date/time format string that will be used to name 
  each archive.  The default is ``YYYY-MM-DD``.

Plugins
=======
Spare Keys supports the use of setuptools plugins to customize the backup 
process.  For example, the following plugins are currently included:

``avendesora``
   Query avendesora for the password to encrypt the archive with, and also 
   include the configuration files for avendesora in the archive.

   To configure::

      [auth.avendesora]
      account = LOGIN_ACCOUNT_NAME

``emborg``
   Include the configuration files for borg and emborg in the archive, and also 
   run ``borg key export`` to archive the keys for "repokey" backups.

Although these plugins are currently distributed with Spare Keys itself, they 
should be moved into the corresponding projects as soon as possible.
