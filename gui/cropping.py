"""Embedded crop previews using the existing projection computation and CSV writer."""

from __future__ import annotations

import base64
import io
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

from aceneurotools.miniscope.projections import compute_projections
from aceneurotools.shared.csv_worker import CSVWorker
from gui.csv_projects import ProjectError
from gui.recording_scope import apply_scope
from gui.runs import inventory, recording_path


def validate_coords(coords, width, height):
    if not isinstance(coords, (list, tuple)) or len(coords) != 4 or any(type(value) is not int for value in coords):
        raise ProjectError("Enter four whole-pixel crop coordinates.")
    x0, y0, x1, y1 = coords
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ProjectError(
            f"The crop must have a positive width and height and fit inside the {width} × {height} image."
        )
    return coords


PREVIEW_FOLDER = ".ace-previews"


def normalized_image(array):
    lo, hi = float(np.min(array)), float(np.max(array))
    normalized = (
        np.zeros_like(array, dtype=np.uint8)
        if hi <= lo
        else np.clip((array - lo) * (255 / (hi - lo)), 0, 255).astype(np.uint8)
    )
    return Image.fromarray(normalized)


def grayscale_png(array):
    buffer = io.BytesIO()
    normalized_image(array).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def preview_file(project_path: Path, number: str) -> Path:
    """Thumbnail location for an experiment; hex names keep any experiment number filesystem-safe."""
    return Path(project_path) / PREVIEW_FOLDER / f"{number.encode('utf-8').hex()}.png"


def save_preview(project_path: Path, number: str, array, size: int = 320) -> Path:
    """Store a small projection image that the experiment grid shows as a thumbnail."""
    image = normalized_image(array)
    image.thumbnail((size, size))
    path = preview_file(project_path, number)
    path.parent.mkdir(exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    image.save(partial, format="PNG")
    partial.replace(path)
    return path


def saved_previews(project_path: Path) -> dict[str, int]:
    """Experiment numbers with a stored thumbnail, mapped to its modification time (ns)."""
    folder = Path(project_path) / PREVIEW_FOLDER
    found = {}
    if folder.is_dir():
        for item in folder.glob("*.png"):
            try:
                found[bytes.fromhex(item.stem).decode("utf-8")] = item.stat().st_mtime_ns
            except (ValueError, OSError):
                continue
    return found


class Cropping:
    def __init__(self):
        self.lock = threading.Lock()
        self.previews = {}

    def preview(self, project, body):
        import cv2

        detail = project.inspect(body.get("number"))
        if detail["versions"] != body.get("versions"):
            raise ProjectError("Save or reload your changes before loading a crop preview.")
        base = body.get("data_path") or str(project.path)
        if not isinstance(base, str):
            raise ProjectError("Choose a local data base folder.")
        path = recording_path(project, detail["metadata"], base, "calcium imaging directory")
        files = [item for item in apply_scope(path, inventory(path)) if item["path"].lower().endswith(".avi")]
        if not files:
            raise ProjectError(f"No AVI movies were found in {path}.")
        # Bounded previews: sample across the recording, never load a full movie into HTTP memory.
        chosen = [files[index] for index in np.linspace(0, len(files) - 1, min(8, len(files)), dtype=int)]
        frames = []
        shape = None
        for item in chosen:
            cap = cv2.VideoCapture(str(path / item["path"]))
            try:
                count = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
                pixels = max(1, int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) * int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
                per_file = max(1, min(16, 16_000_000 // (pixels * len(chosen))))
                for index in np.linspace(0, count - 1, min(count, per_file), dtype=int):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, int(index))
                    ok, frame = cap.read()
                    if not ok:
                        continue
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    if shape is not None and gray.shape != shape:
                        raise ProjectError(
                            "The recording contains movies with different image sizes. Choose a single consistent recording folder."
                        )
                    shape = gray.shape
                    if gray.size > 4_000_000:
                        raise ProjectError(
                            "This movie is too large for the embedded preview (maximum 4 million pixels per frame)."
                        )
                    frames.append(gray)
            finally:
                cap.release()
        if not frames:
            raise ProjectError(
                "The AVI movies could not be decoded. Check that the recording has downloaded completely."
            )
        projections = compute_projections(np.asarray(frames))
        images = {
            name: grayscale_png(getattr(projections, name)) for name in ["max", "min", "mean", "median", "std", "range"]
        }
        images["frame"] = grayscale_png(frames[len(frames) // 2])
        try:
            save_preview(project.path, detail["number"], projections.max)
        except OSError:
            pass  # A read-only project still previews; its grid card shows the type icon instead.
        height, width = shape
        settings = CSVWorker.convert_data_types(detail["parameters"] or {})
        coords = settings.get("crop_coords")
        legacy = False
        if coords is None and isinstance(settings.get("crop"), (list, tuple)):
            coords = settings["crop"]
            legacy = True
        warning = None
        if coords is not None:
            try:
                validate_coords(coords, width, height)
            except ProjectError as exc:
                warning = f"The saved crop is invalid for this recording: {exc} Draw a new crop before saving."
                coords = None
        token = uuid.uuid4().hex
        with self.lock:
            self.previews = {
                key: preview for key, preview in self.previews.items() if time.monotonic() - preview["time"] < 1800
            }
            if len(self.previews) >= 8:
                self.previews.pop(next(iter(self.previews)))
            self.previews[token] = {
                "project": project.id,
                "number": detail["number"],
                "versions": detail["versions"],
                "width": width,
                "height": height,
                "time": time.monotonic(),
                "path": path,
                "files": files,
            }
        return {
            "preview": token,
            "width": width,
            "height": height,
            "images": images,
            "coords": coords,
            "legacy": legacy,
            "warning": warning,
            "sample_frames": len(frames),
            "sample_files": len(chosen),
            "total_files": len(files),
        }

    def save(self, project, body):
        with self.lock:
            preview = self.previews.get(body.get("preview")) if isinstance(body.get("preview"), str) else None
        if not preview or time.monotonic() - preview["time"] >= 1800:
            raise ProjectError("Load the crop preview again before saving.")
        if preview["project"] != project.id or preview["number"] != body.get("number"):
            raise ProjectError("Load a preview for this experiment before saving its crop.")
        if preview["versions"] != body.get("versions"):
            raise ProjectError("Settings changed since this preview was loaded. Load the preview again before saving.")
        files = [
            item
            for item in apply_scope(preview["path"], inventory(preview["path"]))
            if item["path"].lower().endswith(".avi")
        ]
        if files != preview["files"]:
            raise ProjectError("Recording files changed since preview. Load the preview again before saving.")
        coords = validate_coords(body.get("coords"), preview["width"], preview["height"])
        return project.save(
            body["number"],
            "parameters",
            {"crop_coords": str(tuple(coords))},
            body["versions"],
            create=body["number"] not in project.parameters,
            new_columns=("crop_coords",),
        )
