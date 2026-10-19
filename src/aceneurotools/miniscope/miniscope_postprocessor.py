"""Compatibility import; use :mod:`aceneurotools.calcium_imaging.calcium_imaging_postprocessor`."""

import sys

from aceneurotools.calcium_imaging import calcium_imaging_postprocessor as _implementation

sys.modules[__name__] = _implementation
