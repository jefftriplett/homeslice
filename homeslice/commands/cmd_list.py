from __future__ import absolute_import

import click

from ..cli import pass_context
from ..utils import do_repo_list


@click.command()
@pass_context
def cli(context):
    """
    List all existing repos in your homeslice
    """

    click.echo('Current homeslice repos:')
    for repo in do_repo_list():
        click.echo('    {}'.format(repo))
