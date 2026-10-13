"""The distribution gate rejects missing schemas, missing templates, and lab data."""

from __future__ import annotations

import io
import tarfile
from zipfile import ZipFile

import pytest
from scripts.check_distribution import check_sdist, check_wheel

RESOURCES = [
    "aceneurotools/py.typed",
    "aceneurotools/evc/schemas/experiment.v1.schema.json",
    "aceneurotools/evc/schemas/analysis.cnmfe.v1.schema.json",
    "aceneurotools/shared/metadata_templates/experiments_template.csv",
    "aceneurotools/shared/metadata_templates/analysis_parameters_template.csv",
]


def wheel(tmp_path, *, omitted=None, extra=(), dependency="numpy>=1.23"):
    path = tmp_path / "aceneurotools.whl"
    with ZipFile(path, "w") as archive:
        for name in [*RESOURCES, *extra]:
            if name != omitted:
                archive.writestr(name, "resource")
        archive.writestr(
            "aceneurotools-0.1.0.dist-info/METADATA",
            f"Name: aceneurotools\nVersion: 0.1.0\nRequires-Dist: {dependency}\n\n",
        )
    return path


def test_complete_wheel_passes_backend_resource_check(tmp_path):
    check_wheel(wheel(tmp_path))


@pytest.mark.parametrize("omitted", RESOURCES)
def test_wheel_missing_backend_resources_is_rejected(tmp_path, omitted):
    with pytest.raises(AssertionError):
        check_wheel(wheel(tmp_path, omitted=omitted))


@pytest.mark.parametrize("extra", ["data/recording.raw", "gui/server.py"])
def test_wheel_must_not_include_lab_data_or_unpackaged_gui(tmp_path, extra):
    with pytest.raises(AssertionError):
        check_wheel(wheel(tmp_path, extra=[extra]))


def test_wheel_never_installs_the_unrelated_pypi_caiman(tmp_path):
    with pytest.raises(AssertionError, match="unrelated"):
        check_wheel(wheel(tmp_path, dependency="caiman>=1.13"))


def sdist(tmp_path, extra=(), omitted=None):
    path = tmp_path / "aceneurotools.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        for name in [
            "environment.yml",
            "conda-lock.yml",
            "CITATION.cff",
            "docs/releasing.md",
            "tests/conftest.py",
            "tests/compiled_stack/test_miniscope_optional_params_csv.py",
            "ci/coverage-policy.json",
            "ci/requirements-test.txt",
            "docs/backend_testing.md",
            ".github/workflows/checks.yml",
            "scripts/run_backend_checks.py",
            "scripts/check_coverage.py",
            "scripts/ci_environment.py",
            *extra,
        ]:
            if name == omitted:
                continue
            content = b"resource"
            member = tarfile.TarInfo(f"aceneurotools-0.1.0/{name}")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return path


def test_sdist_provenance_files_pass(tmp_path):
    check_sdist(sdist(tmp_path))


@pytest.mark.parametrize("omitted", ["tests/conftest.py", "tests/compiled_stack/test_miniscope_optional_params_csv.py"])
def test_sdist_cannot_drop_backend_test_collection_support(tmp_path, omitted):
    with pytest.raises(AssertionError, match="source distribution lacks"):
        check_sdist(sdist(tmp_path, omitted=omitted))


def test_sdist_rejects_lab_data(tmp_path):
    with pytest.raises(AssertionError, match="lab data"):
        check_sdist(sdist(tmp_path, extra=["data/experiments.csv"]))
