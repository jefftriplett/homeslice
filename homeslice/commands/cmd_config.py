from __future__ import absolute_import

import click
import click_log
import logging
import json

from ..cli import pass_context
from ..pep508checker import lookup


logger = logging.getLogger(__name__)


@click.command()
@click_log.simple_verbosity_option()
@click_log.init(__name__)
@pass_context
def cli(context):
    click.echo(json.dumps(lookup, indent=2))
