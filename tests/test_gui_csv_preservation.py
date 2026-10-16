"""Column additions preserve unrelated bytes; rollback preserves its backup."""

from pathlib import Path

import pytest

from aceneurotools.gui.csv_projects import Project


@pytest.mark.parametrize("ending", [b"\n", b"\r\n", b"\r"])
@pytest.mark.parametrize("bom", [b"", b"\xef\xbb\xbf"])
def test_adding_setting_column_retains_quotes_multiline_cells_and_endings(tmp_path, ending, bom):
    (tmp_path / "experiments.csv").write_bytes(b"line number,id\n1,A\n")
    content = bom + ending.join(
        [b'"line number","comments"', b'"1","quoted ""text"", with comma', b'and a second line"']
    )
    path = tmp_path / "analysis_parameters.csv"
    path.write_bytes(content)
    project = Project.open(tmp_path)
    saved, backup = project.save("1", "parameters", {"crop": "False"}, project.digests, new_columns=("crop",))
    assert Path(backup).read_bytes() == content
    expected = bom + ending.join(
        [b'"line number","comments","crop"', b'"1","quoted ""text"", with comma', b'and a second line","False"']
    )
    assert path.read_bytes() == expected
    assert saved.inspect("1")["parameters"]["comments"] == (
        'quoted "text", with comma' + ending.decode() + "and a second line"
    )


def test_create_rollback_keeps_only_backup_reusable(tmp_path, monkeypatch):
    path = tmp_path / "experiments.csv"
    original = b'line number,id\r\n1,"first"\r\n'
    path.write_bytes(original)
    (tmp_path / "analysis_parameters.csv").write_text("line number,crop\n1,False\n")
    project = Project.open(tmp_path)
    real = Project.save

    def fail_second(self, number, section, *args, **kwargs):
        if section == "parameters":
            raise OSError("simulated disk write failure")
        return real(self, number, section, *args, **kwargs)

    monkeypatch.setattr(Project, "save", fail_second)
    with pytest.raises(OSError):
        project.create_experiment("2", {"id": "second"}, {"crop": "True"}, project.digests)
    assert path.read_bytes() == original
    backups = list((tmp_path / ".ace-gui-backups").glob("*.csv"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
