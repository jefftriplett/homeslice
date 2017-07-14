"""
Some simple settings for use in other parts of the tool.
"""
from __future__ import absolute_import

import os
import sys

from pathlib import Path


HOME = Path(os.environ['HOME'])
HOMESLICE_ROOT = HOME.joinpath('.config', 'homeslice')
HOMESLICE_REPO = HOMESLICE_ROOT.joinpath('repos')

PY2 = sys.version_info[0] == 2
