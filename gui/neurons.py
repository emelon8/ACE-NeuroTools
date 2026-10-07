"""Embedded CNMF-E curation using unchanged CaImAn loading and selection APIs."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from gui.csv_projects import ProjectError


def load_estimates(path):
    from caiman.source_extraction.cnmf.cnmf import load_CNMF

    return load_CNMF(str(path))


def positive(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ProjectError(f"Enter a positive {label}.") from None
    if not math.isfinite(number) or number <= 0:
        raise ProjectError(f"Enter a positive {label}.")
    return number


def signature(path):
    info = path.stat()
    return {"path": str(path), "size": info.st_size, "mtime_ns": info.st_mtime_ns}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".review-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, allow_nan=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def png(values, cmap):
    from matplotlib import colormaps

    values = np.asarray(values, dtype=float)
    peak = np.max(values)
    normalized = np.clip(values / (peak + 1e-9), 0, 1) if peak > 0 else np.zeros_like(values)
    rgba = (colormaps[cmap](normalized) * 255).astype(np.uint8)
    output = io.BytesIO()
    Image.fromarray(rgba).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode()


def footprint_outline(values):
    """Highlight the component's spatial support above 20% of its peak weight."""
    peak = float(np.max(values))
    mask = values >= peak * 0.2 if peak > 0 else np.zeros(values.shape, dtype=bool)
    interior = np.zeros_like(mask)
    interior[1:-1, 1:-1] = mask[1:-1, 1:-1] & mask[:-2, 1:-1] & mask[2:, 1:-1] & mask[1:-1, :-2] & mask[1:-1, 2:]
    overlay = np.zeros((*values.shape, 4), dtype=np.uint8)
    overlay[mask] = (255, 207, 48, 50)
    overlay[mask & ~interior] = (255, 232, 79, 255)
    output = io.BytesIO()
    Image.fromarray(overlay).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode()


def trace_points(values, fr, start=0, end=None, limit=1800):
    """Min/max envelope retains narrow peaks while bounding browser payloads."""
    end = len(values) if end is None else end
    size = end - start
    if size <= limit:
        indices = np.arange(start, end)
    else:
        indices = []
        for left, right in zip(
            np.linspace(start, end, limit // 2 + 1, dtype=int)[:-1],
            np.linspace(start, end, limit // 2 + 1, dtype=int)[1:],
        ):
            part = values[left:right]
            indices.extend(sorted({left + int(np.argmin(part)), left + int(np.argmax(part))}))
        indices = np.asarray(indices, dtype=int)
    return [[int(index) / fr, float(values[index])] for index in indices]


class Neurons:
    def __init__(self, loader=load_estimates):
        self.loader = loader
        self.lock = threading.RLock()
        self.sessions = {}
        self.jobs = {}

    def sources(self, project, number, data_path=None, runs=None):
        from gui.runs import recording_path

        detail = project.inspect(number)
        paths = {}

        def add(path, origin):
            try:
                if path.is_file() and path.suffix.lower() in {".hdf5", ".h5"}:
                    path = path.resolve()
                    paths[str(path)] = {
                        "path": str(path),
                        "name": path.name,
                        "modified": path.stat().st_mtime_ns,
                        "origin": origin,
                    }
            except OSError:
                pass

        try:
            raw = recording_path(
                project, detail["metadata"], data_path or str(project.path), "calcium imaging directory"
            )
            for folder in [raw, raw / "saved_movies"]:
                if folder.is_dir():
                    for path in folder.iterdir():
                        add(path, "Experiment recording")
        except (ProjectError, OSError):
            pass
        for run in (runs or {}).get("runs", []):
            if run["kind"] in {"miniscope", "multimodal"} and run["state"] == "completed":
                for item in run["files"]:
                    add(Path(run["directory"]) / item["name"], "Completed CNMF-E run")
        sources = sorted(paths.values(), key=lambda item: (-item["modified"], item["path"]))
        return {"sources": sources, "latest": sources[0]["path"] if sources else None}

    def _session(self, project, body):
        session = self.sessions.get(body.get("session")) if isinstance(body.get("session"), str) else None
        if not session or session["project"] != project.id or session["number"] != body.get("number"):
            raise ProjectError("Load this experiment's neuron estimates before reviewing them.")
        if signature(session["source"]) != session["signature"]:
            raise ProjectError("The estimates file changed. Load it again before continuing.")
        return session

    def _summary(self, session):
        decisions = session["decisions"]
        return {
            key: session[key]
            for key in [
                "session",
                "number",
                "source_path",
                "dims",
                "fr",
                "window",
                "count",
                "frames",
                "decisions",
                "revision",
                "current",
                "review_path",
                "event_parameters",
            ]
        } | {"kept": decisions.count(True), "rejected": decisions.count(False), "undecided": decisions.count(None)}

    def _persist(self, session):
        write_json(
            Path(session["review_path"]),
            {
                "source": session["signature"],
                "decisions": session["decisions"],
                "fr": session["fr"],
                "window": session["window"],
                "current": session["current"],
                "revision": session["revision"],
                "updated": datetime.now(timezone.utc).isoformat(),
            },
        )

    def open(self, project, body):
        from gui.run_specs import effective_parameters

        detail = project.inspect(body["number"])
        params, _ = effective_parameters("miniscope", detail["parameters"])
        event_parameters = {"derivative": params["derivative_for_estimates"], "event_height": params["event_height"]}
        value = body.get("path")
        if not isinstance(value, str) or not value.strip():
            raise ProjectError("Choose a CNMF-E estimates HDF5 file.")
        path = Path(value).expanduser().resolve()
        if path.suffix.lower() not in {".hdf5", ".h5"} or not path.is_file():
            raise ProjectError("Choose an existing .hdf5 or .h5 estimates file.")
        stamp = signature(path)
        key = hashlib.sha256(json.dumps([body["number"], stamp], sort_keys=True).encode()).hexdigest()[:24]
        review = project.path / ".ace-neuron-reviews" / key / "review.json"
        try:
            obj = self.loader(path)
            dims = tuple(int(value) for value in obj.dims)
            A, C = obj.estimates.A, obj.estimates.C
            if (
                len(dims) != 2
                or min(dims) <= 0
                or np.prod(dims) != A.shape[0]
                or C is None
                or C.ndim != 2
                or A.shape[1] != C.shape[0]
                or not A.shape[1]
                or not C.shape[1]
            ):
                raise ProjectError("This file needs 2-D spatial footprints and matching, nonempty neuron traces.")
            if np.prod(dims) > 16_000_000:
                raise ProjectError("The footprint image exceeds the embedded review's 16-million-pixel limit.")
            background = np.asarray(A.sum(axis=1)).reshape(dims, order="F")
            if not np.isfinite(background).all():
                raise ProjectError("The spatial footprints contain invalid numeric values.")
            fr = obj.params.get("data", "fr")
        except ProjectError:
            raise
        except Exception:
            raise ProjectError(
                "Could not load CNMF-E estimates. Use an estimates file saved by CaImAn in the ACE analysis environment."
            ) from None
        saved = {}
        if review.exists():
            try:
                saved = json.loads(review.read_text())
                if (
                    saved["source"] != stamp
                    or len(saved["decisions"]) != A.shape[1]
                    or any(value is not None and type(value) is not bool for value in saved["decisions"])
                    or type(saved.get("current")) is not int
                    or not 0 <= saved["current"] < A.shape[1]
                    or type(saved.get("revision")) is not int
                    or saved["revision"] < 0
                ):
                    raise ValueError()
            except (OSError, ValueError, KeyError, TypeError):
                raise ProjectError(
                    "The saved review is invalid. Its review.json is retained; choose a separate estimates copy or repair that review before continuing."
                ) from None
        fr = positive(body["fr"] if body.get("fr") is not None else saved.get("fr", fr), "frame rate in Hz")
        window = positive(
            body["window"] if body.get("window") is not None else saved.get("window", 30), "trace window in seconds"
        )
        if signature(path) != stamp:
            raise ProjectError("The estimates changed while loading. Open them again.")
        with self.lock:
            # Reopening the same source shares its latest decisions, not a stale second journal.
            existing = next((item for item in self.sessions.values() if item["review_path"] == str(review)), None)
            if existing:
                existing["revision"] += int(existing["fr"] != fr or existing["window"] != window)
                existing["fr"], existing["window"] = fr, window
                existing["event_parameters"] = event_parameters
                self._persist(existing)
                return self._summary(existing) | {"background": existing["background"]}
            if len(self.sessions) >= 3:
                self.sessions.pop(next(iter(self.sessions)))
            token = uuid.uuid4().hex
            session = dict(
                session=token,
                project=project.id,
                number=body["number"],
                source=path,
                source_path=str(path),
                signature=stamp,
                obj=obj,
                dims=list(dims),
                fr=fr,
                window=window,
                count=A.shape[1],
                frames=C.shape[1],
                decisions=saved.get("decisions", [None] * A.shape[1]),
                revision=saved.get("revision", 0),
                current=min(saved.get("current", 0), A.shape[1] - 1),
                review_path=str(review),
                background=png(background, "inferno"),
                event_parameters=event_parameters,
            )
            self._persist(session)
            self.sessions[token] = session
            return self._summary(session) | {"background": session["background"]}

    def component(self, project, body):
        with self.lock:
            session = self._session(project, body)
            if "revision" in body and body["revision"] != session["revision"]:
                raise ProjectError(
                    "This review changed in another tab. Reload the estimates to use the latest settings and decisions."
                )
            index = body.get("index")
            if type(index) is not int or not 0 <= index < session["count"]:
                raise ProjectError("Choose a neuron number in this estimates file.")
            fr = positive(body.get("fr", session["fr"]), "frame rate in Hz")
            window = positive(body.get("window", session["window"]), "trace window in seconds")
            if session["fr"] != fr or session["window"] != window or session["current"] != index:
                updated = {
                    **session,
                    "fr": fr,
                    "window": window,
                    "current": index,
                    "revision": session["revision"] + int(session["fr"] != fr or session["window"] != window),
                }
                self._persist(updated)
                self.sessions[session["session"]] = session = updated
            obj, dims = session["obj"], session["dims"]
            column = obj.estimates.A[:, index]
            footprint = np.asarray(column.toarray() if hasattr(column, "toarray") else column).reshape(dims, order="F")
            trace = np.asarray(obj.estimates.C[index], dtype=float)
            if not np.isfinite(trace).all() or not np.isfinite(footprint).all():
                raise ProjectError("This neuron's footprint or trace contains invalid numeric values.")
            duration = (len(trace) - 1) / fr
            peak = int(np.argmax(trace)) / fr
            start = body.get("start")
            if body.get("full") is True:
                start, window = 0, len(trace) / fr
            if start is None:
                start = max(0, min(peak - window / 2, duration - window))
            else:
                try:
                    start = float(start)
                except (ValueError, TypeError):
                    raise ProjectError("Enter a trace start time in seconds.") from None
                if not math.isfinite(start):
                    raise ProjectError("Enter a finite trace start time.")
                start = max(0, min(start, max(0, duration - window)))
            end = min(duration, start + window)
            left, right = int(start * fr), min(len(trace), int(end * fr) + 1)
            y, x = np.unravel_index(int(np.argmax(footprint)), dims)
            return self._summary(session) | {
                "index": index,
                "footprint": png(footprint, "hot"),
                "outline": footprint_outline(footprint),
                "peak_pixel": [int(x), int(y)],
                "trace": trace_points(trace, fr, left, right),
                "overview": trace_points(trace, fr, limit=600),
                "start": start,
                "end": end,
                "duration": duration,
                "peak_s": peak,
                "fr": fr,
                "window": session["window"],
                "trace_min": float(trace.min()),
                "trace_max": float(trace.max()),
            }

    def decide(self, project, body):
        with self.lock:
            session = self._session(project, body)
            if body.get("revision") != session["revision"]:
                raise ProjectError(
                    "This review changed in another tab. Reload the estimates to use the latest decisions."
                )
            decisions = list(session["decisions"])
            if "bulk" in body:
                if body["bulk"] not in {"keep", "reject"}:
                    raise ProjectError("Choose Keep or Reject for undecided neurons.")
                decisions = [body["bulk"] == "keep" if value is None else value for value in decisions]
            else:
                index, decision = body.get("index"), body.get("decision")
                if (
                    type(index) is not int
                    or not 0 <= index < session["count"]
                    or (decision is not None and type(decision) is not bool)
                ):
                    raise ProjectError("Choose a neuron and a Keep, Reject, or Undecided decision.")
                decisions[index] = decision
            updated = {
                **session,
                "decisions": decisions,
                "revision": session["revision"] + 1,
                "current": body.get("current", session["current"]),
            }
            if type(updated["current"]) is not int or not 0 <= updated["current"] < session["count"]:
                raise ProjectError("Choose a valid neuron to continue reviewing.")
            self._persist(updated)
            self.sessions[session["session"]] = updated
            return self._summary(updated)

    def export(self, project, body):
        with self.lock:
            session = self._session(project, body)
            if body.get("confirmed") is not True or body.get("revision") != session["revision"]:
                raise ProjectError("Review and confirm the current neuron decisions before exporting.")
            if None in session["decisions"]:
                raise ProjectError("Keep or reject every undecided neuron before exporting.")
            events = body.get("event_analysis")
            if events is not None:
                if (
                    not isinstance(events, dict)
                    or not isinstance(events.get("derivative"), str)
                    or events["derivative"] not in {"zeroth", "first", "second"}
                ):
                    raise ProjectError("Choose zeroth, first, or second derivative for event detection.")
                try:
                    height = float(events["event_height"])
                    if isinstance(events["event_height"], bool) or not math.isfinite(height):
                        raise ValueError()
                except (KeyError, TypeError, ValueError):
                    raise ProjectError("Enter a finite event height threshold.") from None
                events = {"derivative": events["derivative"], "event_height": height}
            filename = body.get("filename", "estimates_curated.hdf5")
            if (
                not isinstance(filename, str)
                or not filename.strip()
                or Path(filename).name != filename
                or "\\" in filename
                or Path(filename).suffix.lower() not in {".hdf5", ".h5"}
            ):
                raise ProjectError("Enter a curated estimates filename ending in .hdf5 or .h5, without a folder path.")
            parent = Path(body.get("output_path") or (project.path / ".ace-curations")).expanduser().resolve()
            if parent.exists() and not parent.is_dir():
                raise ProjectError("Choose a local output folder.")
            parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
            job = dict(
                id=stamp,
                project=project.id,
                number=session["number"],
                state="saving",
                directory=str(parent / stamp),
                kept=[i for i, value in enumerate(session["decisions"]) if value is True],
                files=[],
                filename=filename,
                event_analysis=events,
                message="Saving curated estimates…",
            )
            self.jobs[stamp] = job
            snapshot = {**session, "decisions": list(session["decisions"])}
            threading.Thread(target=self._save_export, args=(job, snapshot, parent), daemon=True).start()
            return dict(job)

    def export_status(self, project, job_id):
        with self.lock:
            job = self.jobs.get(job_id)
            if not job or job["project"] != project.id:
                raise ProjectError("This curation export is unavailable.")
            return dict(job)

    def _save_export(self, job, session, parent):
        try:
            if signature(session["source"]) != session["signature"]:
                raise ProjectError("Estimates changed before export. Reload and review the new file.")
            with tempfile.TemporaryDirectory(prefix=".curation-", dir=parent) as folder:
                stage = Path(folder)
                write_json(
                    stage / "decisions.json",
                    {
                        "source": session["signature"],
                        "experiment": session["number"],
                        "decisions": session["decisions"],
                        "neuron_ids": job["kept"],
                        "fr": session["fr"],
                        "revision": session["revision"],
                        "estimates_filename": job["filename"],
                        "event_analysis": job["event_analysis"],
                    },
                )
                if job["kept"]:
                    obj = self.loader(session["source"])  # Never trim the live review object.
                    obj.estimates.select_components(idx_components=job["kept"])
                    obj.params.set("data", {"fr": session["fr"]})
                    # CaImAn loads .h5 too, but its save API requires .hdf5.
                    # Save with its supported extension, then name the staged copy.
                    saved_estimates = stage / "estimates.hdf5"
                    obj.save(str(saved_estimates))
                    if job["filename"] != saved_estimates.name:
                        saved_estimates.rename(stage / job["filename"])
                    estimates = obj.estimates
                    values = {"C": estimates.C, "neuron_ids": np.asarray(job["kept"], dtype=int), "fr": session["fr"]}
                    A = estimates.A
                    if A.shape[0] * A.shape[1] * A.dtype.itemsize <= 128 * 1024**2:
                        values["A_dense"] = A.toarray() if hasattr(A, "toarray") else np.asarray(A)
                    else:
                        values.update(
                            A_data=A.data, A_indices=A.indices, A_indptr=A.indptr, A_shape=np.asarray(A.shape)
                        )
                        job["message"] = (
                            "Dense footprints exceeded 128 MB; sparse footprints were included in the NPZ instead."
                        )
                    np.savez_compressed(stage / "C_curated.npz", **values)
                    if job["event_analysis"] is not None:
                        from aceneurotools.miniscope.miniscope_postprocessor import MiniscopePostprocessor

                        job["message"] = "Detecting calcium events from saved curated estimates…"
                        curated_path = stage / job["filename"]
                        curated = self.loader(curated_path).estimates
                        if not np.isfinite(curated.C).all():
                            raise ProjectError(
                                "Curated traces contain invalid numeric values; events cannot be detected."
                            )
                        events = MiniscopePostprocessor.find_calcium_events_with_derivatives(
                            curated, **job["event_analysis"]
                        )
                        write_json(
                            stage / "calcium-events.json",
                            {
                                "experiment": session["number"],
                                "source": session["signature"],
                                "estimates": signature(curated_path)
                                | {"path": str(Path(job["directory"]) / job["filename"])},
                                "revision": session["revision"],
                                "fr": session["fr"],
                                "frames": session["frames"],
                                "neuron_ids": job["kept"],
                                "parameters": job["event_analysis"],
                                "index_convention": "Zero-based peak indices in C (zeroth) or np.diff(C, n=1 or 2); no frame offset added.",
                                "ca_events_idx": {str(key): value.tolist() for key, value in events.items()},
                            },
                        )
                if signature(session["source"]) != session["signature"]:
                    raise ProjectError("Estimates changed during export. No curation output was installed.")
                files = [item.name for item in stage.iterdir()]
                shutil.move(str(stage), job["directory"])
                with self.lock:
                    job.update(
                        state="saved",
                        files=files,
                        message=job["message"]
                        if "sparse" in job["message"]
                        else "Curated copies and calcium events saved. Earlier run results are unchanged."
                        if job["kept"] and job["event_analysis"] is not None
                        else "Curated copies saved; original estimates unchanged."
                        if job["kept"]
                        else "All neurons rejected. Decisions saved; no curated estimates were produced.",
                    )
        except Exception as exc:
            with self.lock:
                job.update(
                    state="failed",
                    message=f"Could not save curated estimates ({type(exc).__name__}: {str(exc)[:180]}). Original estimates and saved decisions are retained.",
                )
