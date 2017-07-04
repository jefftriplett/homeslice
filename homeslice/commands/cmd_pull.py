from __future__ import absolute_import

import click

from .. import git
from ..cli import pass_context
from ..utils import do_repos_from_arguments


@click.command()
@click.option('--all', '-a', is_flag=True, help='link all repos')
@click.option('--no-submodules', 'submodules', is_flag=True, default=False,
              help='do not update submodules')
@click.argument('repos', nargs=-1)
@pass_context
def cli(context, all, submodules, repos):
    """
    Pull a repo and optionally update its submodules
    """

    repos = do_repos_from_arguments(all, repos)

    for repo in repos:
        click.echo('\nPulling repo in {} ...'.format(repo))
        git.pull(repo, submodules)
