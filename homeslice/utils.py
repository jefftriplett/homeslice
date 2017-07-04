from __future__ import absolute_import

import click
import os
import sys

from . import environments


def do_repo_list():
    """
    Return list of all git repos in repodir
    """

    # Assuming all git repos contain a .git folder
    pattern = environments.HOMESLICE_REPO

    # Do some extra checks
    repos = []
    # rglob == '**/.git'
    for path in pattern.rglob('.git'):
        # .git should be a folder
        if not path.is_dir():
            continue
        repo_root = os.path.dirname(path)
        repos.append(os.path.basename(repo_root))

    return sorted(repos)


def do_repos_from_arguments(all, repos):
    """
    Build a list of repos rom the arguments defined in parser_add_repo_options
    """

    if all:
        repos = do_repo_list()

        if len(repos) == 0:
            click.echo('No repos have yet been cloned to your homeslice')
            click.echo('    Repo dir: {}'.format(environments.HOMESLICE_REPO))
            sys.exit(1)

    else:
        repos = repos

        if len(repos) == 0:
            click.echo('Either specify repos on the command line or use --all')
            sys.exit(1)

    return [environments.HOMESLICE_REPO.joinpath(repo) for repo in repos]
