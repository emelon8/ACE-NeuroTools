"""Read-only GUI loading: raw values, joins, invalid files, and stale snapshots."""

import csv
from pathlib import Path

import pytest
from gui.csv_projects import Project, ProjectChangedError, ProjectError


def write_table(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


@pytest.fixture
def project_folder(tmp_path):
    write_table(
        tmp_path / "experiments.csv",
        ["line number", "id", "Box Calcium Folder ID", "comments", "extra field", "date (YYMMDD)"],
        [
            ["2", "R2", "90071992547409931234", "quoted, multiline\ncomment", "NA", "241001"],
            ["1", "R1", "", "", "", "241002"],
            ["", "", "", "", "", ""],
        ],
    )
    write_table(
        tmp_path / "analysis_parameters.csv",
        ["line number", "gSig", "crop"],
        [
            ["1", "(3, 3)", "False"],
            ["2", "(5, 5)", "True"],
        ],
    )
    return tmp_path


def test_whole_project_preserves_values_and_joins_by_number(project_folder):
    before = {path.name: path.read_bytes() for path in project_folder.iterdir()}
    project = Project.open(project_folder / "experiments.csv")
    assert [row["number"] for row in project.summary()["experiments"]] == ["2", "1"]
    assert project.summary()["count"] == 2
    detail = project.inspect("2")
    assert detail["metadata"]["comments"] == "quoted, multiline\ncomment"
    assert detail["metadata"]["extra field"] == "NA"
    assert detail["parameters"]["gSig"] == "(5, 5)"
    assert detail["recordings"][0]["box_url"] == "https://app.box.com/folder/90071992547409931234"
    assert detail["interpreted"]["analysis_parameters.csv"]["gSig"] == [5, 5]
    assert {path.name: path.read_bytes() for path in project_folder.iterdir()} == before


def test_default_experiment_persists_and_rejects_stale_changes(project_folder):
    project = Project.open(project_folder)
    updated = project.set_default_experiment("2", project.digests.copy())
    assert updated.summary()["default_experiment"] == "2"
    assert Project.open(project_folder).default_experiment == "2"
    with pytest.raises(ProjectChangedError, match="changed"):
        project.set_default_experiment("1", project.digests)
    with pytest.raises(ProjectError, match="saved analysis settings"):
        updated.set_default_experiment("99", updated.digests)


def test_new_experiment_uses_selected_parameters_without_source_identity(project_folder):
    project = Project.open(project_folder)
    source = project.parameters["2"]
    copied = {key: value for key, value in source.items() if key != "line number"}
    updated, backup = project.create_experiment(
        "3", {"id": "R3", "date (YYMMDD)": "241003"}, copied, project.digests.copy()
    )
    assert updated.experiments["3"]["id"] == "R3"
    assert updated.parameters["3"] == {"line number": "3", **copied}
    assert Path(backup).exists()
    with pytest.raises(ProjectError, match="unique"):
        updated.create_experiment("3", {}, {}, updated.digests)


def test_missing_settings_are_explicit(project_folder):
    (project_folder / "analysis_parameters.csv").unlink()
    project = Project.open(project_folder)
    assert "absent" in project.warnings[0]
    assert project.inspect("1")["parameters"] is None
    write_table(project_folder / "analysis_parameters.csv", ["line number", "crop"], [["2", "True"], ["7", "False"]])
    with pytest.raises(ProjectChangedError, match="changed"):
        project.inspect("1")
    reloaded = Project.open(project_folder)
    assert reloaded.inspect("1")["parameters"] is None
    assert "no matching analysis-parameter record: 1" in reloaded.warnings[0]
    assert "no matching experiment: 7" in reloaded.warnings[1]


def test_invalid_settings_do_not_hide_metadata(project_folder):
    (project_folder / "analysis_parameters.csv").write_text("line number,crop\n1,False,extra\n")
    project = Project.open(project_folder)
    detail = project.inspect("1")
    assert detail["metadata"]["id"] == "R1"
    assert detail["parameters"] is None
    assert "expected 2 columns, found 3" in detail["parameter_error"]
    assert project.summary()["experiments"][0]["parameter_error"] is True


@pytest.mark.parametrize(
    "content, message",
    [
        ("id\nR1\n", "exact column"),
        ("line number,id,id\n1,R1,R1\n", "repeated column"),
        ("line number,id\n1,R1\n1,R2\n", "occurs more than once"),
        ("line number,id\n,R1\n", "blank or contains outer spaces"),
        ("line number,id\n 1,R1\n", "blank or contains outer spaces"),
        ("line number,id\n1,R1,extra\n", "expected 2 columns"),
        ('line number,id\n1,"unterminated\n', "invalid CSV"),
    ],
)
def test_invalid_metadata_is_rejected(tmp_path, content, message):
    (tmp_path / "experiments.csv").write_text(content)
    with pytest.raises(ProjectError, match=message):
        Project.open(tmp_path)


def test_encoding_error_does_not_rewrite_original(tmp_path):
    path = tmp_path / "experiments.csv"
    content = b"line number,id\n1,R\xff\n"
    path.write_bytes(content)
    with pytest.raises(ProjectError, match="not UTF-8"):
        Project.open(tmp_path)
    assert path.read_bytes() == content


def test_changed_files_require_reload(project_folder):
    project = Project.open(project_folder)
    path = project_folder / "experiments.csv"
    path.write_text(path.read_text().replace("R1", "Rnew"))
    with pytest.raises(ProjectChangedError, match="experiments.csv changed"):
        project.inspect("1")
    assert Project.open(project_folder).inspect("1")["metadata"]["id"] == "Rnew"


def test_bad_box_id_is_not_a_link(project_folder):
    path = project_folder / "experiments.csv"
    path.write_text(path.read_text().replace("90071992547409931234", "123.0"))
    assert Project.open(project_folder).inspect("2")["recordings"][0]["box_url"] is None


def test_zero_padded_number_remains_visible_when_existing_reader_cannot_match(tmp_path):
    write_table(tmp_path / "experiments.csv", ["line number", "id"], [["001", "R1"]])
    detail = Project.open(tmp_path).inspect("001")
    assert detail["metadata"]["line number"] == "001"
    assert "not found" in detail["reader_errors"][0]


def test_selected_unknown_number_is_a_helpful_error(project_folder):
    with pytest.raises(ProjectError, match="was not found"):
        Project.open(project_folder).inspect("99")


def test_save_reuses_writer_preserves_other_rows_and_backs_up(project_folder):
    project = Project.open(project_folder)
    before_metadata = (project_folder / "experiments.csv").read_bytes()
    before_settings = (project_folder / "analysis_parameters.csv").read_bytes()
    untouched = project.experiments["1"].copy()
    updated, backup = project.save(
        "2", "metadata", {"comments": "new, note\nsecond line", "extra field": "custom"}, project.digests.copy()
    )
    assert updated.experiments["2"]["comments"] == "new, note\nsecond line"
    assert updated.experiments["1"] == untouched
    assert updated.experiments["2"]["Box Calcium Folder ID"] == "90071992547409931234"
    assert updated.metadata_columns == project.metadata_columns
    assert (project_folder / "analysis_parameters.csv").read_bytes() == before_settings
    assert Path(backup).read_bytes() == before_metadata
    assert not list(project_folder.glob(".ace-edit-*"))
    assert updated.inspect("2")["metadata"]["extra field"] == "custom"


def test_save_refuses_external_edits_and_stale_client(project_folder):
    project = Project.open(project_folder)
    versions = project.digests.copy()
    updated, _ = project.save("1", "metadata", {"comments": "saved"}, versions)
    with pytest.raises(ProjectChangedError, match="saved elsewhere"):
        updated.save("1", "metadata", {"comments": "stale"}, versions)
    path = project_folder / "experiments.csv"
    path.write_text(path.read_text().replace("saved", "external"))
    before = path.read_bytes()
    with pytest.raises(ProjectChangedError, match="changed"):
        updated.save("1", "metadata", {"comments": "overwrite"}, updated.digests)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "section, changes",
    [
        ("metadata", {"line number": "99"}),
        ("metadata", {"unknown column": "x"}),
        ("metadata", {"Box Calcium Folder ID": "123.0"}),
        ("metadata", {"date (YYMMDD)": "not a date"}),
        ("parameters", {"gSig": "(3,)"}),
        ("parameters", {"gSig": "danger()"}),
        ("parameters", {"crop": 1}),
    ],
)
def test_invalid_save_never_changes_files(project_folder, section, changes):
    project = Project.open(project_folder)
    before = {path.name: path.read_bytes() for path in project_folder.iterdir()}
    with pytest.raises(ProjectError):
        project.save("2", section, changes, project.digests)
    assert {path.name: path.read_bytes() for path in project_folder.iterdir()} == before


def test_create_missing_settings_record_preserves_existing_records(project_folder):
    (project_folder / "analysis_parameters.csv").write_text('line number,gSig,crop\n2,"(5, 5)",True')
    project = Project.open(project_folder)
    with pytest.raises(ProjectError, match="Add settings"):
        project.save("1", "parameters", {"gSig": "(3, 3)"}, project.digests)
    updated, _ = project.save("1", "parameters", {"gSig": "(3, 3)"}, project.digests, create=True)
    assert updated.parameters["2"] == project.parameters["2"]
    assert updated.parameters["1"] == {"line number": "1", "gSig": "(3, 3)", "crop": ""}
    assert not updated.summary()["missing_parameters"]


def test_create_missing_settings_file_uses_existing_schema_without_defaults(project_folder):
    (project_folder / "analysis_parameters.csv").unlink()
    project = Project.open(project_folder)
    detail = project.inspect("1")
    assert any(field["key"] == "decay_time" for field in detail["fields"]["parameters"])
    updated, backup = project.save("1", "parameters", {"decay_time": "0.5"}, project.digests, create=True)
    assert backup is None
    assert updated.parameters["1"]["decay_time"] == "0.5"
    assert updated.parameters["1"]["gSig"] == ""
    assert updated.parameters["1"]["id"] == ""


def test_bom_and_zero_padded_identity_round_trip(tmp_path):
    path = tmp_path / "experiments.csv"
    path.write_bytes(b"\xef\xbb\xbfline number,id,comments\r\n001,R1,old\r\n002,R2,keep\r\n")
    project = Project.open(tmp_path)
    updated, _ = project.save("001", "metadata", {"comments": "new"}, project.digests)
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert updated.experiments["001"]["comments"] == "new"
    assert updated.experiments["002"]["comments"] == "keep"


def test_writer_failure_keeps_original_files(project_folder, monkeypatch):
    from gui import csv_projects

    project = Project.open(project_folder)
    original = (project_folder / "experiments.csv").read_bytes()

    def broken_writer(*args):
        raise OSError("simulated write failure")

    monkeypatch.setattr(csv_projects, "update_csv_cell", broken_writer)
    with pytest.raises(OSError):
        project.save("1", "metadata", {"comments": "new"}, project.digests)
    assert (project_folder / "experiments.csv").read_bytes() == original
    assert not list(project_folder.glob(".ace-edit-*"))


@pytest.mark.parametrize(
    "column, value",
    [
        ("date (YYMMDD)", "240230"),
        ("date (YYMMDD)", "20241001"),
        ("min_corr", "not a number"),
        ("min_corr", "inf"),
        ("use_cnn", "maybe"),
        ("gSig", "(3, 4, 5)"),
        ("crop_coords", "[0, 0, 100]"),
        ("indices of TTL events to delete", '["x"]'),
    ],
)
def test_known_field_validation_gives_named_error(column, value):
    from gui.fields import describe, validate

    with pytest.raises(ValueError, match=describe(column)["label"].replace("(", r"\(").replace(")", r"\)")):
        validate(column, value)


def test_metadata_save_does_not_replace_invalid_parameter_file(project_folder):
    path = project_folder / "analysis_parameters.csv"
    path.write_text("line number,crop\n1,False,extra\n")
    original = path.read_bytes()
    project = Project.open(project_folder)
    updated, _ = project.save("1", "metadata", {"comments": "new"}, project.digests)
    assert path.read_bytes() == original
    assert updated.experiments["1"]["comments"] == "new"
    with pytest.raises(ProjectError, match="file is repaired"):
        updated.save("1", "parameters", {"crop": "True"}, updated.digests, create=True)
