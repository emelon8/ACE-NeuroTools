"""The stable, standard-library-only API consumed by scripts and interfaces."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from aceneurotools.evc import api

ROOT = Path(__file__).resolve().parents[1]


def test_public_history_api_imports_without_any_site_packages():
    code = """
import sys
sys.path.insert(0, sys.argv[1])
from aceneurotools.evc import api
required = {
    'ExperimentVersionControl', 'ExperimentWorkspace', 'RunRecorder',
    'RevisionInfo', 'StatusReport', 'RestoreResult', 'FileDiff', 'ParamChange',
    'JournalEntry', 'PushResult', 'ManifestVerification', 'ArtifactPointer',
    'ImportResult', 'DEFAULT_IGNORE_PATTERNS', 'Remote', 'LocalDirectoryRemote',
    'write_manifest', 'read_manifest', 'verify_manifest', 'extract', 'writeback',
    'import_experiment', 'load_schema', 'validate_document', 'EVCError',
    'RepositoryNotFoundError', 'RepositoryExistsError', 'ObjectNotFoundError',
    'AmbiguousIdError', 'CorruptObjectError', 'InvalidObjectError', 'RefConflictError',
    'UnknownRevisionError', 'NothingToRecordError', 'OversizedSnapshotError',
    'PushRejectedError', 'ManifestError', 'CSVBridgeError',
}
assert required <= set(api.__all__)
assert all(hasattr(api, name) for name in required)
assert not any(name in sys.modules for name in ('numpy', 'pandas', 'caiman', 'matplotlib'))
"""
    result = subprocess.run(
        [sys.executable, "-S", "-c", code, str(ROOT / "src")], capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 0, result.stderr


def test_public_history_results_are_frozen_and_dirty_work_is_recoverable(tmp_path):
    params = tmp_path / "params.json"
    params.write_text('{"threshold": 1}')
    history = api.ExperimentVersionControl.init(tmp_path)
    initial = history.record("baseline", author="Synthetic test <test@example.invalid>")
    params.write_text('{"threshold": 2}')
    status = history.status()
    assert isinstance(status, api.StatusReport) and not status.clean
    assert isinstance(status.changes[0], api.FileDiff)
    with pytest.raises(dataclasses.FrozenInstanceError):
        status.clean = True
    restored = history.restore(initial)
    assert isinstance(restored, api.RestoreResult) and restored.safety_snapshot
    assert params.read_text() == '{"threshold": 1}'
    dirty_revision = history.show(restored.safety_snapshot)
    assert isinstance(dirty_revision, api.RevisionInfo)
    history.restore(restored.safety_snapshot)
    assert params.read_text() == '{"threshold": 2}'
