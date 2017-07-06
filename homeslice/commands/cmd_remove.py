from __future__ import absolute_import

import click
import click_log
import logging
import shutil
import sys

from .. import environments
from .. import symlink
from ..cli import pass_context


logger = logging.getLogger(__name__)


@click.command()
@click_log.simple_verbosity_option()
@click_log.init(__name__)
@click.argument('repo', nargs=1)
@click.argument('url', nargs=1, required=False)
@click.option('--force', '-f', 'force', is_flag=True, default=False,
              help='confirm the removal of the repo')
@pass_context
def cli(context, repo, url, force):
    """
    Remove a repo from your homeslice
    """

    repopath = environments.HOMESLICE_REPO.joinpath(repo)

    if not repopath.exists():
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
