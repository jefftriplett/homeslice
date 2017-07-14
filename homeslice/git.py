"""
Provides functional interface to git by running shell commands through the
subprocess module.
"""
from __future__ import absolute_import

import click
import locale
import os

from subprocess import STDOUT, CalledProcessError, check_output


from .dircontext import dircontext

# Determine system encoding from locale
SYSENC = locale.getpreferredencoding()


class GitException(Exception):
    pass


def git(*args):
    """
    Run a git command.
    """

    # Construct command list
    cmd = ['git'] + list(args)

    # Attempt command and handle errors
    try:
        output = check_output(cmd, stderr=STDOUT)
    except OSError as e:
        raise GitException('git command not found')
    except CalledProcessError as e:
        raise GitException(e.output.decode(SYSENC).strip())
    finally:
        pass

    out = output.decode(SYSENC).strip()
    if len(out) > 0:
        click.echo(out)
    return out


def reponame(url, name=None):
    """
    Determine a repo's cloned name from its URL.
    """
    if name is not None:
        return name
    name = os.path.basename(url)
    if name.endswith('.git'):
        name = name[:-4]
    return name


def clone(parent, url, name=None, submodules=True):
    """
    Clone a git repo.
    """

    cmd = [
        'clone',
        '-q',
        '--config',
        'push.default=upstream',
        '--recursiveurl'
    ]

    if name is not None:
        cmd.append(name)

    with dircontext(parent):
        git(*cmd)

        if submodules:
            with dircontext(reponame(url, name)):
                git('submodule', 'update', '--init')


def config(repo):
    cmd = [
        'config',
        'remote.origin.url',
    ]

    with dircontext(repo):
        return git(*cmd)


def pull(repo, submodules=True):
    """
    Update a repo.
    """
    with dircontext(repo):
        git('pull')
        if submodules:
            git('submodule', 'update', '--init')
