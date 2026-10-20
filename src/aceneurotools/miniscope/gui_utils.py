"""Compatibility import; use :mod:`aceneurotools.calcium_imaging.gui_utils`."""

import sys

from aceneurotools.calcium_imaging import gui_utils as _implementation

sys.modules[__name__] = _implementation
