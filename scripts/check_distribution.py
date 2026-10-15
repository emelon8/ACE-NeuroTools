"""Check release wheel contents and dependency metadata without installing it."""

from __future__ import annotations

import sys
from email.parser import Parser
from pathlib import Path
from tarfile import open as open_tar
from zipfile import ZipFile


def check_wheel(path: Path) -> None:
    with ZipFile(path) as wheel:
        names = set(wheel.namelist())
        assert "aceneurotools/py.typed" in names, "wheel lacks the typed-package marker"
        for expected in (
            "aceneurotools/evc/schemas/experiment.v1.schema.json",
            "aceneurotools/evc/schemas/analysis.cnmfe.v1.schema.json",
            "aceneurotools/shared/metadata_templates/experiments_template.csv",
            "aceneurotools/shared/metadata_templates/analysis_parameters_template.csv",
        ):
            assert expected in names, f"wheel lacks backend resource {expected}"
        assert not any(name.startswith(("data/", "gui/")) for name in names), "wheel contains lab data or GUI files"
        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        assert len(metadata_paths) == 1, "wheel must contain exactly one METADATA file"
        metadata = Parser().parsestr(wheel.read(metadata_paths[0]).decode("utf-8"))
        dependencies = metadata.get_all("Requires-Dist", [])
        assert not any(item.split(";", 1)[0].strip().lower().startswith("caiman") for item in dependencies), (
            "wheel asks pip to install the unrelated PyPI caiman project"
        )
        assert metadata["Name"] == "aceneurotools"


def check_sdist(path: Path) -> None:
    with open_tar(path, "r:gz") as archive:
        names = {Path(name).relative_to(Path(name).parts[0]).as_posix() for name in archive.getnames()}
        for expected in (
            "environment.yml",
            "conda-lock.yml",
            "CITATION.cff",
            "docs/releasing.md",
            "tests/conftest.py",
            "tests/compiled_stack/test_miniscope_optional_params_csv.py",
            "ci/coverage-policy.json",
            "ci/requirements-test.txt",
            "ci/windows/environment.yml",
            "docs/backend_testing.md",
            ".github/workflows/checks.yml",
            "scripts/run_backend_checks.py",
            "scripts/check_coverage.py",
            "scripts/ci_environment.py",
        ):
            assert expected in names, f"source distribution lacks {expected}"
        assert not any(name.startswith("data/") for name in names), "source distribution contains lab data"


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        artifact = Path(argument)
        if artifact.suffix == ".whl":
            check_wheel(artifact)
        elif artifact.name.endswith(".tar.gz"):
            check_sdist(artifact)
        else:
            raise ValueError(f"unsupported distribution artifact: {artifact}")
