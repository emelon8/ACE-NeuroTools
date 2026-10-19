"""Compatibility import; use :mod:`aceneurotools.calcium_imaging.pipeline_results`."""

import sys

from aceneurotools.calcium_imaging import pipeline_results as _implementation

sys.modules[__name__] = _implementation
