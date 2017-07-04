from __future__ import absolute_import

import click
import click_completion
import crayons
import os
import shutil
import sys

from . import environments
from . import git
from . import symlink
from .__version__ import __version__


click_completion.init()


def do_repo_list():
    """
    Return list of all git repos in repodir
    """

    # Assuming all git repos contain a .git folder
    pattern = environments.PYHOME_REPO

    # Do some extra checks
    repos = []
    for path in pattern.glob('*/.git'):
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
            click.echo('No repos have yet been cloned to your pyhome')
            click.echo('    Repo dir: {}'.format(environments.PYHOME_REPO))
            sys.exit(1)

    else:
        repos = repos

        if len(repos) == 0:
            click.echo('Either specify repos on the command line or use --all')
            sys.exit(1)

    return [os.path.join(environments.PYHOME_REPO, r) for r in repos]


'''A dotfile management and synchronisation tool.'''


@click.group()
@click.version_option(prog_name=crayons.yellow('pipenv'), version=__version__)
@click.pass_context
def cli(context):
    pass


@click.command()
@click.argument('url', nargs=1)
@click.argument('name', nargs=1, required=False)
@click.option('--no-submodules', 'submodules', is_flag=True, default=False,
              help='do not update submodules')
def clone(url, name, submodules):
    """
    Clone a new repo to your pyhome
    """

    # Make sure repo dir exists
    if not environments.PYHOME_REPO.exists():
        environments.PYHOME_REPO.mkdir(parents=True, exist_ok=True)

    click.echo('Cloning repo from {} ...'.format(url))
    git.clone(environments.PYHOME_REPO, url, name, submodules)


@click.command()
@click.option('--all', '-a', is_flag=True, help='link all repos')
@click.argument('repos', nargs=-1)
def link(all, repos):
    """
    Generate links for this repo in your $HOME folder
    """

    repos = do_repos_from_arguments(all, repos)

    for repo in repos:
        click.echo('\nCreating symlinks for repo {} ...'.format(repo))
        symlink.repo_create_symlinks(repo)


@click.command()
def list():
    """
    List all existing repos in your pyhome
    """

    click.echo('Current pyhome repos:')
    for repo in do_repo_list():
        click.echo('    {}'.format(repo))


@click.command()
@click.option('--all', '-a', is_flag=True, help='link all repos')
@click.option('--no-submodules', 'submodules', is_flag=True, default=False,
              help='do not update submodules')
@click.argument('repos', nargs=-1)
def pull(all, submodules, repos):
    """
    Pull a repo and optionally update its submodules
    """

    repos = do_repos_from_arguments(all, repos)

    for repo in repos:
        click.echo('\nPulling repo in {} ...'.format(repo))
        git.pull(repo, submodules)


@click.command()
@click.argument('repo', nargs=1)
@click.argument('url', nargs=1, required=False)
@click.option('--force', '-f', 'force', is_flag=True, default=False,
              help='confirm the removal of the repo')
def remove(repo, url, force):
    """
    Remove a repo from your pyhome
    """

    repopath = os.path.join(environments.PYHOME_REPO, repo)

    if not os.path.exists(repopath):
        click.echo('No repo "{}" found.'.format(repo))
        # This is an error
        sys.exit(1)

    if not force:
        # Make sure of no accidental deletions
        tpl = 'Really remove "{}"? Run again with "-f" to confirm.'
        click.echo(tpl.format(repopath))

    else:
        # Actually delete the thing
        click.echo('Removing repo {} ...'.format(repopath))
        click.echo(' - Unlinking ...')
        symlink.repo_clear_symlinks(repopath)
        click.echo(' - Removing directory ...')
        shutil.rmtree(repopath)


@click.command()
@click.option('--all', '-a', is_flag=True, help='link all repos')
@click.argument('repos', nargs=-1)
def unlink(all, repos):
    """
    Remove links for this repo in your $HOME folder
    """
    repos = do_repos_from_arguments(all, repos)

    for repo in repos:
        click.echo('\nRemoving symlinks for repo {} ...'.format(repo))
        symlink.repo_clear_symlinks(repo)


cli.add_command(clone)
cli.add_command(link)
cli.add_command(list)
cli.add_command(pull)
cli.add_command(remove)
cli.add_command(unlink)


if __name__ == '__main__':
    cli()
