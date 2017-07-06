from __future__ import absolute_import

import click
import click_log
import logging

from .. import git
from ..cli import pass_context
from ..utils import do_repos_from_arguments


logger = logging.getLogger(__name__)


@click.command()
@click_log.simple_verbosity_option()
@click_log.init(__name__)
@pass_context
def cli(context):
    """
    List all existing repos in your homeslice
    """

    click.echo('Current homeslice repos:')
    repos = do_repos_from_arguments(True, None)

    for repo in repos:
        config = git.config(repo)
        click.echo('    {} {}'.format(
            str(repo).split('/')[-1],
            config,
        ))
