#!/usr/bin/env python3
"""Check local Markdown link targets and heading anchors without site dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINKS = re.compile(r"\]\(([^)]+)\)")
HEADINGS = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
EXPLICIT_IDS = re.compile(r'<a\s+id=["\']([^"\']+)["\']\s*>', re.IGNORECASE)


def heading_anchors(path: Path) -> set[str]:
    """Return ordinary Markdown heading anchors for a local page."""
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    source = path.read_text(encoding="utf-8")
    anchors.update(EXPLICIT_IDS.findall(source))
    for heading in HEADINGS.findall(source):
        heading = re.sub(r"\s+#+$", "", heading)
        slug = re.sub(r"[^\w\s-]", "", heading.lower()).strip()
        slug = re.sub(r"\s+", "-", slug)
        number = counts.get(slug, 0)
        anchors.add(slug if number == 0 else f"{slug}_{number}")
        counts[slug] = number + 1
    return anchors


def markdown_files() -> list[Path]:
    return [
        *sorted(ROOT.glob("*.md")),
        *sorted((ROOT / "docs").rglob("*.md")),
        *sorted((ROOT / "examples").rglob("*.md")),
        *sorted((ROOT / "src/aceneurotools").rglob("README.md")),
    ]


def check_links() -> list[str]:
    errors: list[str] = []
    for source in markdown_files():
        if not source.exists():
            continue
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            for raw in LINKS.findall(line):
                target = unquote(raw.strip().split()[0].strip("<>"))
                if target.startswith(("https:", "http:", "mailto:", "data:")):
                    continue
                destination, _, anchor = target.partition("#")
                path = (source.parent / destination).resolve() if destination else source
                if not path.exists() and "docs/notebooks/" in str(path):
                    path = ROOT / "notebooks" / path.name
                if not path.exists():
                    errors.append(f"{source.relative_to(ROOT)}:{line_number}: missing {target}")
                elif anchor and path.suffix == ".md" and anchor not in heading_anchors(path):
                    errors.append(
                        f"{source.relative_to(ROOT)}:{line_number}: missing #{anchor} in {path.relative_to(ROOT)}"
                    )
    return errors


if __name__ == "__main__":
    failures = check_links()
    if failures:
        print("\n".join(failures), file=sys.stderr)
        sys.exit(1)
    print("Local documentation links and heading anchors are valid.")
