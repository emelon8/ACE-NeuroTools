"""Compatibility import; use :mod:`aceneurotools.calcium_imaging.filtered_calcium_imaging_data`."""

import sys

from aceneurotools.calcium_imaging import filtered_calcium_imaging_data as _implementation

sys.modules[__name__] = _implementation
