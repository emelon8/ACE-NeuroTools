"""MiniscopeDataManager.create() must work without any other module having
imported the concrete data-manager subclasses first.

Historically the registry was only populated as a side effect of importing
aceneurotools.stats.loader; create() now registers the built-in subclasses
itself. Run in a clean subprocess so no other test's imports mask a regression.
"""

from __future__ import annotations

import subprocess
import sys


def test_create_registers_builtin_subclasses_in_fresh_interpreter(tmp_path):
    code = (
        "from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager\n"
        "try:\n"
        f"    MiniscopeDataManager.create(999999, project_path={str(tmp_path)!r})\n"
        "except Exception:\n"
        "    pass  # no experiments.csv here — registration happens before the lookup\n"
        "names = {c.__name__ for c in MiniscopeDataManager._registry}\n"
        "assert 'UCLADataManager' in names, names\n"
        "assert 'OnixMiniscopeDataManager' in names, names\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
