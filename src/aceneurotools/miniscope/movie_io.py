"""Compatibility import; use :mod:`aceneurotools.calcium_imaging.movie_io`."""

import sys

from aceneurotools.calcium_imaging import movie_io as _implementation

sys.modules[__name__] = _implementation
