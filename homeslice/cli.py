from __future__ import absolute_import

import click
import click_completion
import crayons
import sys

from pathlib import Path

from .__version__ import __version__
from .environments import PY2


CONTEXT_SETTINGS = dict(auto_envvar_prefix='HOMESLICE')


class Context(object):

    def __init__(self):
        self.verbose = False
        self.force = False
        self.pretend = False
        self.quiet = False
        self.skip = False

    def log(self, msg, *args):
        """Logs a message to stderr."""
        if args:
            msg %= args
        click.echo(msg, file=sys.stderr)

    def vlog(self, msg, *args):
        """Logs a message to stderr only if verbose is enabled."""
        if self.verbose:
            self.log(msg, *args)


pass_context = click.make_pass_decorator(Context, ensure=True)

cmd_folder = Path(__file__).parent.joinpath('commands')


class HomesliceCLI(click.MultiCommand):

    def list_commands(self, ctx):
        rv = []
        for filename in cmd_folder.glob('cmd_*.py'):
            rv.append(filename.name[4:-3])
        rv.sort()
        return rv

    def get_command(self, ctx, name):
        try:
            if PY2:
                name = name.encode('ascii', 'replace')
            mod = __import__('homeslice.commands.cmd_' + name,
                             None, None, ['cli'])
        except ImportError:
            return
        return mod.cli


# @click.group()
@click.command(cls=HomesliceCLI, context_settings=CONTEXT_SETTINGS)
@click.option('--force', '-f', 'force', is_flag=True, default=False,
              help='Overwrite files that already exist')
@click.option('--pretend', '-p', 'pretend', is_flag=True, default=False,
              help='Run but do not make any changes')
@click.option('--quiet', '-q', 'quiet', is_flag=True, default=False,
              help='Suppress status output')
@click.option('--skip', '-s', 'skip', is_flag=True, default=False,
              help='Skip files that already exist')
@click.option('-v', '--verbose', is_flag=True, help='Enables verbose mode.')
@click.version_option(prog_name=crayons.yellow('homeslice'), version=__version__)
@pass_context
def cli(ctx, verbose, force, pretend, quiet, skip):
    """A dotfile management and synchronisation tool."""

    ctx.verbose = verbose

    if force is not None:
        ctx.force = force

    if pretend is not None:
        ctx.pretend = pretend

    if quiet is not None:
        ctx.quiet = quiet

    if skip is not None:
        ctx.skip = skip


click_completion.init()


if __name__ == '__main__':
    cli()
