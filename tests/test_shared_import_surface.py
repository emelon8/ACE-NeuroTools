"""Guards the lightweight import surface of aceneurotools.shared.

`import aceneurotools.shared` must not drag in cv2, and must not trigger
pyplot initialisation (set_backend must run before any pyplot import — see
shared/plotting.py). These tests pin that contract.
"""

from __future__ import annotations

import subprocess
import sys

import numpy as np

from aceneurotools.shared import filter_data, filter_signal


def test_filter_data_matches_filter_signal():
    rng = np.random.default_rng(0)
    sig = rng.standard_normal(500)
    a = filter_data(sig, n=2, cut=[0.1, 1.5], ftype="butter", btype="bandpass", fs=30.0)
    b = filter_signal(sig, n=2, cut=[0.1, 1.5], ftype="butter", btype="bandpass", fs=30.0)
    np.testing.assert_array_equal(a, b)


def test_importing_shared_does_not_load_cv2_or_pyplot():
    """Run in a clean subprocess so module state is pristine."""
    code = (
        "import sys; import aceneurotools.shared; "
        "assert 'cv2' not in sys.modules, 'cv2 was imported'; "
        "assert 'matplotlib.pyplot' not in sys.modules, "
        "'pyplot was imported (breaks the set_backend contract)'; "
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
