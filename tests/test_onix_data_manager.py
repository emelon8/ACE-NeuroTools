"""Light coverage for OnixMiniscopeDataManager native-sync behavior.

Exercises the sync_timestamps path (the ``__import__('numpy')`` cleanup),
constructing the instance without the heavy data-loading ``__init__``.
"""

from __future__ import annotations

import numpy as np
import pytest


def test_onix_sync_timestamps_returns_native_arrays():
    pytest.importorskip("caiman")
    from aceneurotools.miniscope.onix_miniscope_data_manager import OnixMiniscopeDataManager

    dm = object.__new__(OnixMiniscopeDataManager)  # bypass data-loading __init__
    dm.time_stamps = np.arange(10, dtype=float) / 30.0

    t_ca, low_conf = dm.sync_timestamps()

    assert isinstance(t_ca, np.ndarray)
    np.testing.assert_allclose(t_ca, dm.time_stamps)
    assert isinstance(low_conf, np.ndarray)
    assert low_conf.shape == (0, 2)
