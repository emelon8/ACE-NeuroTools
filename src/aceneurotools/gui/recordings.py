"""Resolve recordings already available on the local filesystem."""

from pathlib import Path, PureWindowsPath

from aceneurotools.gui.csv_projects import ProjectError
from aceneurotools.gui.runs import inventory


class Recordings:
    def prepare(self, project, body):
        detail = project.inspect(body["number"])
        if detail["versions"] != body.get("versions"):
            raise ProjectError("Save or reload the experiment before loading its recording.")
        ephys = body.get("kind") == "ephys"
        column = "ephys directory" if ephys else "calcium imaging directory"
        value = detail["metadata"].get(column, "").strip()
        if not value or ";" in value or (PureWindowsPath(value).is_absolute() and not Path(value).is_absolute()):
            raise ProjectError(f"Choose one local {column} in Data & settings.")
        base = Path(body.get("data_path") or project.path).expanduser().resolve()
        target = (base / value).resolve()
        suffixes = {".ncs", ".rhs", ".rhd", ".dat", ".bin", ".raw"} if ephys else {".avi"}
        if not target.is_dir() or not any(Path(item["path"]).suffix.lower() in suffixes for item in inventory(target)):
            raise ProjectError(
                "Recording files are missing. Download them from Box first, then choose their local folder."
            )
        return {
            "project": project.id,
            "number": body["number"],
            "data_path": str(base),
            "recording_path": str(target),
            "state": "ready",
        }
