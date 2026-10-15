"""Verify portable exports, allocation matching, and unchanged project inputs."""

import base64
import csv
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from gui.csv_projects import Project, ProjectChangedError, ProjectError
from gui.job_scripts import generate


@pytest.fixture
def job(tmp_path):
    (tmp_path / "experiments.csv").write_text(
        "line number,id,calcium imaging directory,ephys directory\n1,R1,missing,mystery\n2,R2,other,other\n"
    )
    (tmp_path / "analysis_parameters.csv").write_text(
        "line number,crop,crop_coords,n_processes,run_CNMFE,save_estimates,filenames\n"
        '1,True,"(1, 2, 30, 40)",99,True,True,"[\'0.avi\']"\n2,False,,6,False,False,[]\n'
    )
    project = Project.open(tmp_path)
    return project, {
        "number": "1",
        "kind": "miniscope",
        "versions": project.digests,
        "cluster": {
            "recording_path": "/scratch/rat one",
            "output_path": "/scratch/results",
            "cpus": "8",
            "memory_gb": "150",
            "time": "1-12:00:00",
            "python": "/cluster/env's/bin/python",
            "account": "lab",
            "partition": "bigmem",
        },
    }


def unpack(result):
    return zipfile.ZipFile(io.BytesIO(base64.b64decode(result["archive"])))


@pytest.mark.parametrize("kind", ["compute", "preprocess", "miniscope", "ephys", "multimodal"])
def test_exports_saved_parameters_and_only_selected_rows(job, kind):
    project, body = job
    body["kind"] = kind
    if kind == "multimodal":
        body["cluster"]["ephys_recording_path"] = "/scratch/ephys/rat one"
    before = {
        name: (project.path / name).read_bytes() if (project.path / name).exists() else None for name in project.digests
    }
    result = generate(project, body)
    assert result["config"]["recording_path"] == "/scratch/rat one"
    assert result["config"]["parameters"].get("crop_coords") == ([1, 2, 30, 40] if kind != "ephys" else None)
    if kind in {"miniscope", "multimodal"}:
        assert result["config"]["parameters"]["n_processes"] == 8
        assert result["config"]["parameters"]["parallel"] is True
        assert result["config"]["parameters"]["remove_components_with_gui"] is False
    if kind == "multimodal":
        assert result["config"]["ephys_recording_path"] == "/scratch/ephys/rat one"
    with unpack(result) as archive:
        for name in ["experiments.csv", "analysis_parameters.csv"]:
            rows = list(csv.DictReader(io.StringIO(archive.read(name).decode())))
            assert len(rows) == 1 and rows[0]["line number"] == "1"
            assert (project.path / name).read_bytes() == before[name]
        assert (
            archive.read("gui/run_worker.py")
            == (Path(__file__).resolve().parents[1] / "gui/run_worker.py").read_bytes()
        )
        for name in archive.namelist():
            if name.endswith(".py"):
                compile(archive.read(name), name, "exec")
    assert "#SBATCH --cpus-per-task=8" in result["slurm"]
    assert "#SBATCH --mem=150G" in result["slurm"]
    checked = subprocess.run(["bash", "-n"], input=result["slurm"], text=True, capture_output=True)
    assert checked.returncode == 0, checked.stderr
    assert {
        name: (project.path / name).read_bytes() if (project.path / name).exists() else None for name in before
    } == before


@pytest.mark.parametrize(
    "key,value",
    [
        ("cpus", 0),
        ("cpus", True),
        ("cpus", "1.5"),
        ("memory_gb", "0"),
        ("time", "00:00:00"),
        ("time", "1-24:00:00"),
        ("time", "12:60:00"),
        ("account", "lab\n#SBATCH --exclusive"),
        ("partition", "x;touch bad"),
        ("recording_path", "relative/path"),
        ("recording_path", "/scratch\nnewline"),
        ("python", "python;rm -rf something"),
    ],
)
def test_invalid_cluster_options_rejected(job, key, value):
    project, body = job
    body["cluster"][key] = value
    with pytest.raises(ProjectError):
        generate(project, body)


def test_rejects_stale_exports(job):
    project, body = job
    body["versions"] = {}
    with pytest.raises(ProjectError, match="reload"):
        generate(project, body)
    body["versions"] = project.digests
    (project.path / "experiments.csv").write_text("line number,id\n1,changed\n")
    with pytest.raises(ProjectChangedError):
        generate(project, body)


def test_preserves_confirmed_subset_and_rejects_bad_receipt(job):
    project, body = job
    recording = project.path / "missing"
    recording.mkdir()
    receipt = recording / ".ace-box.json"
    receipt.write_text(json.dumps({"selection": ["0.avi", "metaData.json"]}))
    assert generate(project, body)["config"]["selected_files"] == ["0.avi", "metaData.json"]
    receipt.write_text('{"selection": "invalid"}')
    with pytest.raises(ProjectError, match="selection"):
        generate(project, body)


def test_exported_entry_point_uses_bundled_worker_and_fresh_output(job, tmp_path):
    project, body = job
    source, outputs, bundle = tmp_path / "raw", tmp_path / "outputs", tmp_path / "export"
    source.mkdir()
    (source / "0.avi").write_bytes(b"recording")
    body["cluster"].update(recording_path=str(source), output_path=str(outputs))
    with unpack(generate(project, body)) as archive:
        archive.extractall(bundle)
    # Execute from outside the checkout; intercept only the expensive science call.
    probe = """import json, runpy
from pathlib import Path
import gui.run_worker
def execute(manifest):
    root = Path(manifest['directory'])
    assert manifest['parameters']['n_processes'] == 3
    assert manifest['files'][0]['path'] == '0.avi'
    assert (root / 'experiments.csv').exists()
    (root / 'called.json').write_text(json.dumps(manifest))
gui.run_worker.execute = execute
runpy.run_path('run_job.py', run_name='__main__')
"""
    env = {
        **os.environ,
        "PYTHONPATH": str(bundle) + os.pathsep + str(Path(__file__).resolve().parents[1] / "src"),
        "SLURM_CPUS_PER_TASK": "3",
    }
    for _ in range(2):
        result = subprocess.run([sys.executable, "-c", probe], cwd=bundle, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    runs = list(outputs.iterdir())
    assert len(runs) == 2
    assert all(json.loads((root / "outcome.json").read_text())["success"] for root in runs)
    assert (source / "0.avi").read_bytes() == b"recording"


def test_multimodal_export_stages_both_cluster_recordings(job, tmp_path):
    project, body = job
    calcium, ephys, output, bundle = [tmp_path / name for name in ("calcium", "ephys", "results", "bundle")]
    calcium.mkdir()
    ephys.mkdir()
    (calcium / "0.avi").write_bytes(b"movie")
    (ephys / "signal.raw").write_bytes(b"electrical")
    body["kind"] = "multimodal"
    body["cluster"].update(recording_path=str(calcium), ephys_recording_path=str(ephys), output_path=str(output))
    with unpack(generate(project, body)) as archive:
        archive.extractall(bundle)
    probe = """import json, runpy
from pathlib import Path
import gui.run_worker
def execute(manifest):
    root = Path(manifest['directory'])
    assert [item['path'] for item in manifest['files']] == ['0.avi']
    assert [item['path'] for item in manifest['ephys_files']] == ['signal.raw']
    assert manifest['parameters']['parallel'] is True
    (root / 'called.json').write_text(json.dumps(manifest))
gui.run_worker.execute = execute
runpy.run_path('run_job.py', run_name='__main__')
"""
    env = {**os.environ, "PYTHONPATH": str(bundle) + os.pathsep + str(Path(__file__).resolve().parents[1] / "src")}
    result = subprocess.run([sys.executable, "-c", probe], cwd=bundle, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    runs = list(output.iterdir())
    assert len(runs) == 1
    assert json.loads((runs[0] / "outcome.json").read_text())["success"] is True
