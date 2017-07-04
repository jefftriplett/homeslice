"""
Some simple settings for use in other parts of the tool.
"""

from __future__ import absolute_import, print_function

import os

from pathlib import Path


HOME = Path(os.environ['HOME'])
PYHOME_ROOT = HOME.joinpath('.config', 'pyhome')
PYHOME_REPO = PYHOME_ROOT.joinpath('repos')
