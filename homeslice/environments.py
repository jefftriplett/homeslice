"""
Some simple settings for use in other parts of the tool.
"""

from __future__ import absolute_import, print_function

import os

from pathlib import Path


HOME = Path(os.environ['HOME'])
HOMESLICE_ROOT = HOME.joinpath('.config', 'homeslice')
HOMESLICE_REPO = HOMESLICE_ROOT.joinpath('repos')
