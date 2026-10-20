"""Compatibility import; use :mod:`aceneurotools.calcium_imaging.projections`."""

import sys

from aceneurotools.calcium_imaging import projections as _implementation

sys.modules[__name__] = _implementation
