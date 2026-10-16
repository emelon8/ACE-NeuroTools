"""Derive build versions from git; tags must also have a changelog entry."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

from setuptools_scm import get_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--github-env", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = get_version(root=str(root), local_scheme="no-local-version")
    ref = os.environ.get("GITHUB_REF", "")
    if ref.startswith("refs/tags/v"):
        expected = ref.removeprefix("refs/tags/v")
        if version != expected:
            raise SystemExit(f"Tag {expected} does not match the git-derived version {version}.")
        changelog = (root / "CHANGELOG.md").read_text()
        if not re.search(r"^## \[?" + re.escape(expected) + r"\]?(?:\s|$)", changelog, re.MULTILINE):
            raise SystemExit(f"Add a CHANGELOG.md heading for {expected} before tagging.")
        if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
            raise SystemExit("Tagged releases must build from a clean checkout.")
    if args.github_env:
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as handle:
            handle.write(f"ACE_VERSION={version}\n")
    print(version)


if __name__ == "__main__":
    main()
