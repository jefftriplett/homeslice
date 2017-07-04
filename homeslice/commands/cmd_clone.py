from __future__ import absolute_import

import click

from .. import environments
from .. import git
from ..cli import pass_context


@click.command()
@click.argument('url', nargs=1)
@click.argument('name', nargs=1, required=False)
@click.option('--no-submodules', 'submodules', is_flag=True, default=False,
              help='do not update submodules')
@pass_context
def cli(context, url, name, submodules):
    """
    Clone a new repo to your homeslice
    """

    # Make sure repo dir exists
    if not environments.HOMESLICE_REPO.exists():
        environments.HOMESLICE_REPO.mkdir(parents=True, exist_ok=True)

    click.echo('Cloning repo from {} ...'.format(url))
    git.clone(environments.HOMESLICE_REPO, url, name, submodules)
