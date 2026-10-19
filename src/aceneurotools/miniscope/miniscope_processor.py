"""Compatibility import; use :mod:`aceneurotools.calcium_imaging.calcium_imaging_processor`."""

import sys

from aceneurotools.calcium_imaging import calcium_imaging_processor as _implementation

sys.modules[__name__] = _implementation
