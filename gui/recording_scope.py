"""Restrict previews and private run copies to a confirmed recording selection."""

import json
from pathlib import Path

from gui.csv_projects import ProjectError


def apply_scope(path, files):
    receipt = Path(path) / ".ace-box.json"
    if not receipt.exists():
        return files
    try:
        value = json.loads(receipt.read_text())
        selected = value.get("selection")
        if selected is None:
            return files  # Older receipts described complete downloads.
        if (
            not isinstance(selected, list)
            or not selected
            or any(
                not isinstance(item, str) or Path(item).is_absolute() or ".." in Path(item).parts for item in selected
            )
        ):
            raise ValueError()
        return [item for item in files if item["path"] in selected]
    except (OSError, ValueError, TypeError, AttributeError):
        raise ProjectError(
            "The saved recording selection could not be read. Choose and confirm recording files again."
        ) from None
