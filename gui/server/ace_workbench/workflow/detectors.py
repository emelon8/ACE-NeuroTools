"""Explainable, dependency-free probes; format evidence never supplies biology."""

from __future__ import annotations

import csv
import hashlib
import math
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from pathlib import Path, PurePosixPath

from .models import Candidate


def natural_key(value: str) -> list:
    return [int(piece) if piece.isdigit() else piece.lower() for piece in re.split(r"(\d+)", value)]


def positive(value) -> float | None:
    try:
        result = float(str(value).removesuffix("FPS").strip())
        return result if math.isfinite(result) and result > 0 else None
    except (ValueError, TypeError):
        return None


def small_json(path: Path) -> dict:
    if path.stat().st_size > 2 * 1024**2:
        raise ValueError("Metadata JSON exceeds 2 MiB.")
    from ..documents import parse_document

    value = parse_document("acquisition-metadata", path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Metadata JSON must be an object.")
    return value


class Detector(ABC):
    format: str
    label: str

    @abstractmethod
    def probe(self, root: Path, directory: str, names: list[str]) -> Candidate | None: ...

    def candidate(self, directory: str, names: list[str]) -> Candidate:
        key = hashlib.sha256(f"{self.format}:{directory}:{','.join(names)}".encode()).hexdigest()[:24]
        return Candidate(key, self.format, self.label, directory, names)


class UCLADetector(Detector):
    format = "ucla-miniscope"
    label = "UCLA miniscope recording"

    def probe(self, root: Path, directory: str, names: list[str]) -> Candidate | None:
        metadata = [n for n in names if re.fullmatch(r"metaData.*\.json", Path(n).name)]
        stamps = [n for n in names if re.fullmatch(r"timeStamps.*\.csv", Path(n).name)]
        movies = sorted([n for n in names if n.endswith(".avi")], key=natural_key)
        if not metadata and not stamps:
            return None
        item = self.candidate(directory, names)
        item.evidence = [
            f"{len(metadata)} metadata JSON, {len(stamps)} timestamp CSV, {len(movies)} AVI segments in this folder"
        ]
        if not movies:
            item.blockers.append("No AVI movie segments in the recording folder.")
        if len(stamps) != 1:
            item.blockers.append("Exactly one timeStamps CSV is required per recording folder.")
        if len(metadata) > 1:
            item.blockers.append("Multiple metadata JSON files are ambiguous; select one recording folder.")
        if len(metadata) == 1:
            try:
                data = small_json(root / metadata[0])
                device = str(data.get("deviceType", data.get("deviceName", ""))).lower()
                item.metadata["calcium_evidence"] = "miniscope" in device or "calcium" in device
                if "behav" in device or "webcam" in device:
                    item.blockers.append("Metadata identifies a behavior camera, not a calcium imaging recording.")
                rate = positive(data.get("frameRate"))
                if rate:
                    item.metadata.update(frame_rate=rate, frame_rate_source=metadata[0] + ": frameRate")
                item.metadata["metadata_file"] = metadata[0]
            except (ValueError, OSError) as exc:
                item.blockers.append(f"Invalid acquisition metadata: {exc}")
        item.metadata.update(movies=movies, timestamps=stamps[0] if len(stamps) == 1 else None)
        return item


class OnixDetector(Detector):
    format = "onix-miniscope"
    label = "ONIX miniscope recording"

    def probe(self, root: Path, directory: str, names: list[str]) -> Candidate | None:
        starts = [n for n in names if re.fullmatch(r"start-time_.+_miniscope\.csv", Path(n).name)]
        if not starts:
            return None
        item = self.candidate(directory, names)
        item.evidence = ["ONIX miniscope start-time metadata"]
        movies = sorted([n for n in names if n.endswith(".avi")], key=natural_key)
        item.metadata["movies"] = movies
        if len(starts) != 1:
            item.blockers.append("Multiple ONIX recording starts in one folder; import one recording at a time.")
            return item
        suffix = Path(starts[0]).name.removeprefix("start-time_").removesuffix("_miniscope.csv")
        clock = str(PurePosixPath(directory) / f"ucla-miniscope-v4-clock_{suffix}.raw")
        item.metadata.update(start_file=starts[0], clock_file=clock)
        item.blockers.extend(validate_start(root / starts[0], item.metadata))
        if clock not in names:
            item.blockers.append(f"Missing companion clock: {Path(clock).name}")
        if not movies:
            item.blockers.append("No AVI movie segments in the recording folder.")
        return item


def validate_start(path: Path, metadata: dict) -> list[str]:
    try:
        if path.stat().st_size > 65536:
            raise ValueError("Start-time file exceeds 64 KiB.")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        if len(rows) != 1 or len(rows[0]) != 4 or not positive(rows[0][1]):
            raise ValueError("Expected one start-time row: timestamp, clock Hz, read size, write size.")
        metadata["clock_hz"] = float(rows[0][1])
        return []
    except (ValueError, OSError, UnicodeError) as exc:
        return [f"Invalid acquisition clock metadata: {exc}"]


class NeuralynxDetector(Detector):
    format = "neuralynx"
    label = "Neuralynx continuous recording"

    def probe(self, root: Path, directory: str, names: list[str]) -> Candidate | None:
        signals = [n for n in names if n.endswith(".ncs")]
        events = [n for n in names if Path(n).name.startswith("Events") and n.endswith(".nev")]
        if not signals and not events:
            return None
        item = self.candidate(directory, names)
        item.evidence = [f"{len(signals)} NCS channels and {len(events)} event files"]
        item.metadata["channels"] = [Path(n).stem for n in signals]
        if not signals or len(events) != 1:
            item.blockers.append("The existing Neuralynx reader requires NCS channels and one Events.nev file.")
        for name in signals + events:
            with (root / name).open("rb") as stream:
                header = stream.read(16384)
            if not header.startswith(b"######## Neuralynx Data File Header") or (root / name).stat().st_size <= 16384:
                item.blockers.append(f"Invalid or empty Neuralynx header/data: {Path(name).name}")
        return item


class RHSDetector(Detector):
    format = "rhs2116"
    label = "ONIX RHS2116 electrophysiology"

    def probe(self, root: Path, directory: str, names: list[str]) -> Candidate | None:
        analog = [n for n in names if re.fullmatch(r"rhs2116pair-ac_.+\.raw", Path(n).name)]
        if not analog:
            return None
        item = self.candidate(directory, names)
        item.evidence = ["RHS2116 pair AC stream filename; companion files checked separately"]
        if len(analog) != 1:
            item.blockers.append("Multiple RHS recordings in one folder; import one recording at a time.")
            return item
        suffix = Path(analog[0]).stem.removeprefix("rhs2116pair-ac_")
        expected = {
            kind: str(PurePosixPath(directory) / f"rhs2116pair-{kind}_{suffix}.raw") for kind in ("ac", "dc", "clock")
        }
        start = str(PurePosixPath(directory) / f"start-time_{suffix}.csv")
        item.metadata.update(streams=expected, start_file=start, channels=[f"RHS2116_AC_{i}" for i in range(32)])
        for name in [*expected.values(), start]:
            if name not in names:
                item.blockers.append(f"Missing RHS companion: {Path(name).name}")
        if start in names:
            item.blockers.extend(validate_start(root / start, item.metadata))
        if all(n in names for n in expected.values()):
            sizes = {k: (root / n).stat().st_size for k, n in expected.items()}
            count = sizes["clock"] // 8
            if count < 2 or sizes["clock"] % 8 or sizes["ac"] != count * 32 * 2 or sizes["dc"] != count * 32 * 2:
                item.blockers.append(
                    "RHS AC/DC/clock sample counts disagree or contain partial samples; truncation is not allowed."
                )
        return item


class TraceDetector(Detector):
    format = "trace-csv"
    label = "Numeric trace table"

    def probe(self, root: Path, directory: str, names: list[str]) -> Candidate | None:
        # Called per CSV by the registry; no inference from an extension alone.
        name = names[0]
        if not name.endswith(".csv") or Path(name).name.startswith(
            ("timeStamps", "start-time", "notes", "port-status")
        ):
            return None
        try:
            with (root / name).open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                columns = next(reader)
                row = next(reader)
            if (
                not 2 <= len(columns) <= 128
                or len(set(columns)) != len(columns)
                or not all(columns)
                or len(row) != len(columns)
            ):
                return None
            if not all(math.isfinite(float(c)) for c in row):
                return None
        except (OSError, UnicodeError, ValueError, StopIteration, csv.Error):
            return None
        item = self.candidate(directory, names)
        item.label = f"Trace table · {Path(name).name}"
        item.evidence = ["Unique CSV column names and numeric first data row; full validation occurs at preflight"]
        item.metadata = {"columns": columns, "table": name}
        return item


class DetectorRegistry:
    def __init__(self, detectors: list[Detector] | None = None):
        self.detectors = (
            detectors if detectors is not None else [UCLADetector(), OnixDetector(), NeuralynxDetector(), RHSDetector()]
        )

    def inspect(self, root: Path, files: list[dict]) -> list[Candidate]:
        groups: dict[str, list[str]] = defaultdict(list)
        for item in files:
            groups[str(PurePosixPath(item["path"]).parent)].append(item["path"])
        found = []
        for directory, names in sorted(groups.items()):
            for detector in self.detectors:
                candidate = detector.probe(root, directory, sorted(names))
                if candidate:
                    found.append(candidate)
            for name in sorted(names):
                candidate = TraceDetector().probe(root, directory, [name])
                if candidate:
                    found.append(candidate)
        if not found:
            found = [
                Candidate(
                    "unrecognized",
                    "unknown",
                    "Unrecognized files",
                    ".",
                    [f["path"] for f in files],
                    ["No supported acquisition signature was found"],
                    blockers=["No scientific reader is available for these files."],
                )
            ]
        return found
