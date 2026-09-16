"""Phase 2 pointer manifests: results are provable without being stored —
one manifest per run, tamper detection names exactly the guilty file."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import pytest

from aceneurotools.evc.errors import ManifestError
from aceneurotools.evc.pointers import (
    MANIFEST_NAME,
    read_manifest,
    verify_manifest,
    write_manifest,
)
from aceneurotools.evc.porcelain import ExperimentVersionControl


@pytest.fixture()
def run_dir(tmp_path):
    """A run output directory with two artifacts (one nested)."""
    run = tmp_path / "run-001"
    run.mkdir()
    (run / "meanFluorescence_97.npz").write_bytes(b"npz-bytes-" * 100)
    (run / "figures").mkdir()
    (run / "figures" / "scatter.png").write_bytes(b"png-bytes")
    return run


# -- write/read round-trip ----------------------------------------------------


def test_manifest_round_trip(run_dir):
    manifest_path = write_manifest(run_dir, pipeline="stats", revision="abc123")
    assert manifest_path == run_dir / MANIFEST_NAME
    pointers = {p.relpath: p for p in read_manifest(run_dir)}
    assert set(pointers) == {"meanFluorescence_97.npz", "figures/scatter.png"}
    npz = pointers["meanFluorescence_97.npz"]
    assert npz.sha256 == hashlib.sha256(b"npz-bytes-" * 100).hexdigest()
    assert npz.size == len(b"npz-bytes-" * 100)
    assert npz.producer == {"pipeline": "stats", "revision": "abc123"}


def test_manifest_excludes_itself_and_is_stable(run_dir):
    write_manifest(run_dir)
    first = (run_dir / MANIFEST_NAME).read_text()
    relpaths = [p.relpath for p in read_manifest(run_dir)]
    assert MANIFEST_NAME not in relpaths
    # re-manifesting unchanged artifacts yields identical pointers
    write_manifest(run_dir)
    second = (run_dir / MANIFEST_NAME).read_text()
    a, b = json.loads(first), json.loads(second)
    for entry in a["artifacts"] + b["artifacts"]:
        entry.pop("created")
    assert a == b


def test_empty_run_manifest(tmp_path):
    run = tmp_path / "empty-run"
    run.mkdir()
    write_manifest(run)
    assert read_manifest(run) == ()
    report = verify_manifest(run)
    assert report.clean and report.verified == ()


# -- verification -------------------------------------------------------------


def test_verify_clean_run(run_dir):
    write_manifest(run_dir)
    report = verify_manifest(run_dir)
    assert report.clean
    assert set(report.verified) == {"meanFluorescence_97.npz", "figures/scatter.png"}


def test_tampered_byte_names_exactly_that_file(run_dir):
    write_manifest(run_dir)
    artifact = run_dir / "figures" / "scatter.png"
    data = bytearray(artifact.read_bytes())
    data[0] ^= 0xFF  # flip one bit of one byte; size unchanged
    artifact.write_bytes(bytes(data))
    report = verify_manifest(run_dir)
    assert report.modified == ("figures/scatter.png",)
    assert report.missing == ()
    assert report.verified == ("meanFluorescence_97.npz",)


def test_missing_artifact_is_reported(run_dir):
    write_manifest(run_dir)
    (run_dir / "meanFluorescence_97.npz").unlink()
    report = verify_manifest(run_dir)
    assert report.missing == ("meanFluorescence_97.npz",)
    assert not report.clean


def test_verify_without_manifest_raises(tmp_path):
    with pytest.raises(ManifestError):
        verify_manifest(tmp_path)


def test_mirrored_manifest_resolves_artifacts_via_base_dir(run_dir, tmp_path):
    """Phase 3 mirrors manifests into the versioned results/<run-id>/ dir."""
    mirror = tmp_path / "workspace" / "results" / "run-001"
    write_manifest(run_dir, manifest_dir=mirror)
    report = verify_manifest(mirror)
    assert report.clean and len(report.verified) == 2
    (run_dir / "figures" / "scatter.png").write_bytes(b"tampered!")
    assert verify_manifest(mirror).modified == ("figures/scatter.png",)


# -- CLI ----------------------------------------------------------------------


def test_cli_verify_run_id(tmp_path):
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir()
    ExperimentVersionControl.init(exp_dir, workspace=True)
    run = exp_dir / "results" / "run-042"
    run.mkdir()
    (run / "result.txt").write_text("payload")
    write_manifest(run)

    def run_cli(*args):
        return subprocess.run(
            [sys.executable, "-m", "aceneurotools.evc", "--dir", str(exp_dir), *args],
            capture_output=True, text=True,
        )

    ok = run_cli("verify", "run-042")
    assert ok.returncode == 0 and "1 artifact(s) verified" in ok.stdout
    (run / "result.txt").write_text("tampered")
    bad = run_cli("verify", "run-042")
    assert bad.returncode == 1 and "modified  result.txt" in bad.stdout
    absent = run_cli("verify", "no-such-run")
    assert absent.returncode == 1 and "error:" in absent.stderr
