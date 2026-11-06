"""Run plans describe reviewed runs, and their commands reproduce the GUI's pipeline calls."""

import ast
import importlib
import inspect
import json
import subprocess
import sys
import threading

import pytest

from aceneurotools.gui import run_plan
from aceneurotools.gui.csv_projects import Project
from aceneurotools.gui.run_specs import PIPELINES, effective_parameters
from aceneurotools.gui.server import ProjectServer
from tests.test_gui_parity import PROBE, environment, gui_parameters, write_settings


def review(kind="miniscope", number="1", **extra):
    return {
        "number": number,
        "kind": kind,
        "label": PIPELINES[kind],
        "metadata": {"id": "R1", "calcium imaging directory": "Rat01/ca", "ephys directory": "Rat01/ep"},
        "parameters": {"miniscope_filenames": ["0.avi"], "crop": False, "n_processes": 2},
        "parameter_sources": {"crop": "Saved CSV"},
        "files": [{"path": "0.avi", "size": 10, "mtime": 1}],
        "ephys_files": [],
        "input_bytes": 10,
        "blockers": [],
        "data_path": "/data",
        **extra,
    }


def plan_with(*entries, mode="sequential", limit=1):
    return run_plan.new_plan(
        project_id="p",
        project_path="/project",
        versions={"experiments.csv": "abc"},
        entries=[run_plan.entry_from_review(item) for item in entries],
        mode=mode,
        max_concurrent=limit,
    )


def test_entries_keep_csv_recording_values_not_local_paths():
    assert run_plan.entry_from_review(review("ephys"))["recordings"] == {"ephys directory": "Rat01/ep"}
    both = run_plan.entry_from_review(review("multimodal"))["recordings"]
    assert both == {"calcium imaging directory": "Rat01/ca", "ephys directory": "Rat01/ep"}
    assert "recording_path" not in run_plan.entry_from_review(review())


@pytest.mark.parametrize(
    "change,message",
    [
        ({"mode": "sequential", "limit": 2}, "one analysis at a time"),
        ({"mode": "parallel", "limit": 0}, "at least 1"),
        ({"mode": "cluster", "limit": 1}, "sequential or parallel"),
    ],
)
def test_plan_execution_settings_are_validated(change, message):
    with pytest.raises(ValueError, match=message):
        plan_with(review(), mode=change["mode"], limit=change["limit"])
    assert plan_with(review(), review(number="2"), mode="parallel", limit=2)["execution"]["max_concurrent"] == 2


def test_plan_entries_are_validated():
    with pytest.raises(ValueError, match="listed twice"):
        plan_with(review(), review())
    with pytest.raises(ValueError, match="non-negative integers"):
        plan_with(review(number="01"))
    with pytest.raises(ValueError, match="at least one"):
        run_plan.new_plan(project_id="p", project_path="/p", versions={}, entries=[])
    plan = plan_with(review(), review("ephys", blockers=["No supported recording files were found in this folder."]))
    assert run_plan.blockers(plan) == [
        "Experiment 1 (Electrophysiology): No supported recording files were found in this folder."
    ]
    assert json.loads(json.dumps(plan)) == plan, "plans are plain JSON"


def test_commands_name_the_existing_entry_points():
    entry = run_plan.entry_from_review(review())
    result = run_plan.invocation(entry, project_path="/my project", data_path="/data root")
    assert result["cli"] == [
        "python",
        "-m",
        "aceneurotools.pipelines.calcium_imaging",
        "--line-num",
        "1",
        "--project-path",
        "/my project",
        "--data-path",
        "/data root",
        "--headless",
    ]
    assert result["cli_posix"].endswith("--project-path '/my project' --data-path '/data root' --headless")
    assert "--project-path '/my project'" in result["cli_powershell"]
    assert "--data-path" not in run_plan.cli_argv(entry, project_path="/p", data_path=None)
    assert result["notes"] == [run_plan.OUTPUTS_NOTE]
    for kind in ["compute", "preprocess"]:
        missing = run_plan.invocation(run_plan.entry_from_review(review(kind)), project_path="/p", data_path="/d")
        assert missing["cli"] is None and missing["cli_posix"] is None and missing["cli_powershell"] is None
        assert missing["cli_note"]


def test_powershell_rendering_quotes_shell_metacharacters():
    argv = ["python", "-m", "mod", "--project-path", r"C:\Data\R&D", "--data-path", r"C:\Bob's %PATH% data"]
    assert run_plan.powershell_join(argv) == (
        r"python -m mod --project-path 'C:\Data\R&D' --data-path 'C:\Bob''s %PATH% data'"
    )
    assert run_plan.powershell_join(["$env:x", "a;b", "@x"]) == "'$env:x' 'a;b' '@x'"


def test_restricted_selection_and_reviewed_versions_travel_with_the_entry():
    entry = run_plan.entry_from_review(review(selection_restricted=True, versions={"experiments.csv": "v1"}))
    assert entry["selection_restricted"] is True and entry["versions"] == {"experiments.csv": "v1"}
    notes = run_plan.invocation(entry, project_path="/p", data_path="/d")["notes"]
    assert notes == [run_plan.SELECTION_NOTE, run_plan.OUTPUTS_NOTE]


@pytest.mark.parametrize("field,value", [("label", None), ("recordings", None), ("blockers", "none"), ("blockers", [1])])
def test_plan_entries_need_labels_recordings_and_text_problems(field, value):
    plan = plan_with(review())
    plan["entries"][0][field] = value
    with pytest.raises(ValueError):
        run_plan.validate_plan(plan)
    plan = plan_with(review())
    del plan["project"]["versions"]
    with pytest.raises(ValueError, match="file versions"):
        run_plan.validate_plan(plan)


def run_kwargs(snippet):
    """The literal keyword dictionary passed with ``**`` in a generated pipeline call."""
    for node in ast.walk(ast.parse(snippet)):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "run":
            (keywords,) = node.keywords
            return ast.literal_eval(keywords.value)
    raise AssertionError("No run() call in the snippet")


@pytest.mark.parametrize("kind", ["compute", "preprocess", "miniscope", "ephys", "multimodal"])
def test_every_python_snippet_compiles(kind):
    entry = run_plan.entry_from_review(review(kind, parameters={"crop_coords": [1, 2, 3, 4], "filenames": []}))
    compile(run_plan.python_snippet(entry, project_path="/p", data_path=None), f"<{kind}>", "exec")


def test_pipeline_snippets_use_canonical_option_names_and_reviewed_values():
    entry = run_plan.entry_from_review(review("multimodal"))
    kwargs = run_kwargs(run_plan.python_snippet(entry, project_path="/p", data_path="/d"))
    assert kwargs == {
        "line_num": 1,
        "project_path": "/p",
        "data_path": "/d",
        "calcium_imaging_filenames": ["0.avi"],
        "crop": False,
        "n_processes": 2,
        "headless": True,
    }


def test_preprocess_snippet_passes_settings_like_the_gui_worker():
    params, _ = effective_parameters("preprocess", {"crop_coords": "(2, 3, 20, 15)", "df_over_f": "True"})
    entry = run_plan.entry_from_review(review("preprocess", parameters=params))
    tree = ast.parse(run_plan.python_snippet(entry, project_path="/p", data_path="/d"))
    calls = {getattr(node.func, "attr", ""): node for node in ast.walk(tree) if isinstance(node, ast.Call)}
    options = calls["preprocess_calcium_movie"]
    coords = next(item for item in options.keywords if item.arg == "coords_dict")
    rest = next(item for item in options.keywords if item.arg is None)
    assert ast.literal_eval(coords.value) == {"x0": 2, "y0": 3, "x1": 20, "y1": 15}
    # gui.run_worker adds headless=True, then passes every setting except these unchanged.
    skipped = {"line_num", "project_path", "data_path", "filenames", "crop_coords"}
    expected = {key: value for key, value in {**params, "headless": True}.items() if key not in skipped}
    assert ast.literal_eval(rest.value) == expected
    filenames = next(item for item in calls["create"].keywords if item.arg == "filenames")
    assert ast.literal_eval(filenames.value) == params["filenames"]


# Parity with the real pipelines: these import the scientific stack.


@pytest.fixture
def project_folder(tmp_path):
    (tmp_path / "experiments.csv").write_text("line number,id\n1,Parity subject\n")
    return tmp_path


PARITY_SETTINGS = {
    "miniscope": {"n_processes": "3", "filenames": "['0.avi', '2.avi']", "run_CNMFE": "False", "cut": "[0.2, 1.3]"},
    "ephys": {"channel_name": "RHS2116_AC_0", "filter_type": "butter", "filter_range": "[0.5, 4]"},
    "multimodal": {"channel_name": "RHS2116_AC_0", "miniscope_filenames": "['0.avi']", "time_range": "[1.0, 5.0]"},
}


def parity_entry(root, kind):
    write_settings(root, PARITY_SETTINGS[kind])
    params, sources = effective_parameters(kind, Project.open(root).inspect("1")["parameters"])
    return run_plan.entry_from_review(
        {
            "number": "1",
            "kind": kind,
            "label": PIPELINES[kind],
            "metadata": {},
            "parameters": params,
            "parameter_sources": sources,
        }
    )


@pytest.mark.parametrize("kind", ["miniscope", "ephys", "multimodal"])
def test_generated_command_reaches_the_cli_with_the_gui_parameters(project_folder, kind):
    entry = parity_entry(project_folder, kind)
    argv = run_plan.cli_argv(entry, project_path=str(project_folder), data_path=str(project_folder))
    capture = project_folder / "cli-parameters.json"
    completed = subprocess.run(
        [sys.executable, str(PROBE), "parameters", kind, str(project_folder), str(capture), json.dumps(argv)],
        env=environment(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(capture.read_text()) == gui_parameters(project_folder, kind)


@pytest.mark.parametrize("kind", ["miniscope", "ephys", "multimodal"])
def test_generated_python_calls_run_with_the_gui_parameters(project_folder, kind, monkeypatch):
    entry = parity_entry(project_folder, kind)
    module_name, class_name = run_plan.PIPELINE_CLASSES[kind]
    cls = getattr(importlib.import_module(module_name), class_name)
    original = cls.run
    expected = gui_parameters(project_folder, kind)  # Reads run()'s signature, so before patching it.
    captured = {}
    monkeypatch.setattr(cls, "run", lambda self, **kwargs: captured.update(kwargs))
    snippet = run_plan.python_snippet(entry, project_path=str(project_folder), data_path=str(project_folder))
    exec(compile(snippet, "<output script>", "exec"), {})
    bound = inspect.signature(original).bind(None, **captured)
    bound.apply_defaults()
    arguments = json.loads(json.dumps({key: value for key, value in bound.arguments.items() if key != "self"}))
    assert captured, "the snippet did not call run()"
    assert arguments == expected


# The HTTP route builds plans only from this server's unexpired reviews.


def test_preview_route_builds_a_plan_from_reviews(tmp_path):
    from tests.test_gui_analysis import make_recording

    root, _ = make_recording(tmp_path)
    server = ProjectServer(("127.0.0.1", 0), str(root))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        from tests import test_gui_server

        base = f"http://127.0.0.1:{server.server_address[1]}"
        test_gui_server.TOKENS[base] = server.token
        project = next(iter(server.projects.values()))
        status, reviewed = test_gui_server.request(
            base, "/api/run/review", {"project": project.id, "number": "1", "kind": "compute", "versions": project.digests}
        )
        assert status == 200 and not reviewed["blockers"]
        status, result = test_gui_server.request(
            base, "/api/run-plan/preview", {"project": project.id, "reviews": [reviewed["review"]]}
        )
        assert status == 200, result
        (entry,) = result["plan"]["entries"]
        assert entry["number"] == "1" and entry["recordings"] == {"calcium imaging directory": "raw"}
        assert result["plan"]["project"]["versions"] == project.digests
        (command,) = result["invocations"]
        assert command["cli"] is None and "lab-config" in command["cli_note"]
        assert "ComputePipeline().run(" in command["python"]
        status, error = test_gui_server.request(base, "/api/run-plan/preview", {"project": project.id, "reviews": ["x"]})
        assert status == 400 and "expired" in error["error"]
        status, error = test_gui_server.request(
            base,
            "/api/run-plan/preview",
            {"project": project.id, "reviews": [reviewed["review"]], "mode": "sequential", "max_concurrent": 3},
        )
        assert status == 400 and "one analysis at a time" in error["error"]

        # A review whose settings were saved again afterwards is rejected, as Start does.
        status, saved = test_gui_server.request(
            base,
            "/api/experiment/save",
            {
                "project": project.id,
                "number": "1",
                "section": "parameters",
                "changes": {"unknown_lab_field": "changed"},
                "versions": project.digests,
            },
        )
        assert status == 200, saved
        status, error = test_gui_server.request(
            base, "/api/run-plan/preview", {"project": project.id, "reviews": [reviewed["review"]]}
        )
        assert status == 400 and "changed after it was reviewed" in error["error"]

        # A fresh review is accepted, until the CSV changes on disk outside ACE.
        status, fresh = test_gui_server.request(
            base,
            "/api/run/review",
            {"project": project.id, "number": "1", "kind": "compute", "versions": saved["project"]["versions"]},
        )
        assert status == 200, fresh
        status, result = test_gui_server.request(
            base, "/api/run-plan/preview", {"project": project.id, "reviews": [fresh["review"]]}
        )
        assert status == 200 and result["plan"]["entries"][0]["versions"] == saved["project"]["versions"]
        with (root / "analysis_parameters.csv").open("a") as handle:
            handle.write("2,False,edited elsewhere\n")
        status, error = test_gui_server.request(
            base, "/api/run-plan/preview", {"project": project.id, "reviews": [fresh["review"]]}
        )
        assert status == 409 and error["reload"] is True
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_review_reports_when_a_confirmed_selection_limits_the_files(tmp_path):
    from aceneurotools.gui.runs import Runs
    from tests.test_gui_analysis import make_recording, payload

    root, _ = make_recording(tmp_path)
    (root / "raw" / "notes.txt").write_text("not part of the confirmed download")
    project = Project.open(root)
    assert Runs().review(project, payload(project, kind="compute"))["selection_restricted"] is False
    selection = ["0.avi", "metaData.json", "timeStamps.csv"]
    (root / "raw" / ".ace-box.json").write_text(json.dumps({"selection": selection}))
    reviewed = Runs().review(project, payload(project, kind="compute"))
    assert reviewed["selection_restricted"] is True
    assert sorted(item["path"] for item in reviewed["files"]) == sorted(selection)
    entry = run_plan.entry_from_review(reviewed)
    assert run_plan.SELECTION_NOTE in run_plan.invocation(entry, project_path=str(root), data_path=str(root))["notes"]


def test_malformed_reviews_and_plans_are_rejected():
    with pytest.raises(ValueError, match="Unsupported analysis"):
        run_plan.entry_from_review(review(kind="miniscope") | {"kind": "spikes"})
    for broken in [None, [], {"schema": "other"}]:
        with pytest.raises(ValueError, match="run plan"):
            run_plan.validate_plan(broken)
    plan = plan_with(review())
    plan["entries"][0]["kind"] = "spikes"
    with pytest.raises(ValueError, match="supported analysis"):
        run_plan.validate_plan(plan)
    plan = plan_with(review())
    plan["entries"][0]["parameters"] = None
    with pytest.raises(ValueError, match="no reviewed settings"):
        run_plan.validate_plan(plan)


def test_preview_rejects_missing_or_too_many_reviews(tmp_path):
    from tests import test_gui_server

    (tmp_path / "experiments.csv").write_text("line number,id\n1,R1\n")
    server = ProjectServer(("127.0.0.1", 0), str(tmp_path))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        test_gui_server.TOKENS[base] = server.token
        project = next(iter(server.projects.values()))
        for reviews in [[], "token", [1], None]:
            status, error = test_gui_server.request(base, "/api/run-plan/preview", {"project": project.id, "reviews": reviews})
            assert status == 400 and error["error"] == "Review at least one experiment first."
        status, error = test_gui_server.request(
            base, "/api/run-plan/preview", {"project": project.id, "reviews": ["t"] * 501}
        )
        assert status == 400 and error["error"] == "Plan at most 500 runs at once."
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_reviews_belong_to_the_project_that_made_them(tmp_path):
    from aceneurotools.gui.csv_projects import ProjectError
    from aceneurotools.gui.runs import Runs
    from tests.test_gui_analysis import make_recording, payload

    first, _ = make_recording(tmp_path / "first")
    second, _ = make_recording(tmp_path / "second")
    runs = Runs()
    token = runs.review(Project.open(first), payload(Project.open(first), kind="compute"))["review"]
    assert runs.reviewed(Project.open(first), token)["number"] == "1"
    with pytest.raises(ProjectError, match="selected project's experiment"):
        runs.reviewed(Project.open(second), token)
    with pytest.raises(ProjectError, match="expired"):
        runs.reviewed(Project.open(first), "unknown")
