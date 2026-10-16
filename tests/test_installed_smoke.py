"""The installed smoke check must release its temporary directory on every exit."""

from pathlib import Path

import pytest
from scripts import smoke_installed_package as smoke


@pytest.mark.parametrize("failure", [False, True])
def test_installed_smoke_restores_cwd_before_cleaning_temporary_directory(monkeypatch, failure):
    original = Path.cwd()
    visited = []

    def check():
        visited.append(Path.cwd())
        assert Path.cwd() != original
        if failure:
            raise RuntimeError("simulated smoke failure")

    monkeypatch.setattr(smoke, "check_installed", check)
    monkeypatch.setattr("sys.argv", ["smoke_installed_package.py", "--installed"])
    if failure:
        with pytest.raises(RuntimeError, match="simulated smoke failure"):
            smoke.main()
    else:
        smoke.main()
    assert Path.cwd() == original
    assert len(visited) == 1 and not visited[0].exists()
