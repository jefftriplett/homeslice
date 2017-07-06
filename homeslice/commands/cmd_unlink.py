from __future__ import absolute_import

import click
import click_log
import logging

from .. import symlink
from ..cli import pass_context
from ..utils import do_repos_from_arguments


logger = logging.getLogger(__name__)


@click.command()
@click_log.simple_verbosity_option()
@click_log.init(__name__)
@click.option('--all', '-a', is_flag=True, help='link all repos')
@click.argument('repos', nargs=-1)
@pass_context
def cli(context, all, repos):
    """
    Remove links for this repo in your $HOME folder
    """
    repos = do_repos_from_arguments(all, repos)

    for repo in repos:
        click.echo('\nRemoving symlinks for repo {} ...'.format(repo))
        symlink.repo_clear_symlinks(repo)
