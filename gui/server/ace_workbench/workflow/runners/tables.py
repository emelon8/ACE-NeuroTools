"""Streaming descriptive statistics; reject malformed data rather than dropping rows."""

import csv
import math
from pathlib import Path

from ..common import atomic_json
from .base import Runner


class InventoryRunner(Runner):
    def check(self, root: Path, configuration: dict) -> dict:
        return {
            "operation": "File integrity inspection only",
            "warnings": ["No scientific processing will be performed."],
        }

    def run(self, root: Path, configuration: dict, output: Path) -> None:
        atomic_json(
            output / "inventory.json",
            {
                "purpose": "Integrity inventory, not scientific analysis",
                "files": configuration["inputs"],
                "detection": configuration["candidate"],
            },
        )


class TraceRunner(Runner):
    def scan(self, root: Path, config: dict, preview: Path | None = None) -> dict:
        settings = config["effective"]
        path = root / config["candidate"]["metadata"]["table"]
        previous = None
        count = 0
        minimum_dt, maximum_dt = math.inf, 0.0
        preview_stream = preview.open("w", newline="", encoding="utf-8") if preview else None
        try:
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                columns = next(reader)
                if columns != config["candidate"]["metadata"]["columns"]:
                    raise ValueError("CSV columns changed after inspection.")
                time_index = columns.index(settings["time_column"])
                indices = [i for i in range(len(columns)) if i != time_index]
                stats = [
                    {
                        "channel": columns[i],
                        "unit": settings["signal_unit"],
                        "mean": 0.0,
                        "m2": 0.0,
                        "minimum": math.inf,
                        "maximum": -math.inf,
                    }
                    for i in indices
                ]
                writer = csv.writer(preview_stream) if preview_stream else None
                if writer:
                    writer.writerow(["time_s", *[columns[i] for i in indices]])
                for row_number, row in enumerate(reader, 2):
                    if len(row) != len(columns):
                        raise ValueError(f"CSV row {row_number} has an unexpected number of columns.")
                    try:
                        values = [float(cell) for cell in row]
                    except ValueError as exc:
                        raise ValueError(f"CSV row {row_number} contains a missing or nonnumeric value.") from exc
                    if not all(math.isfinite(v) for v in values):
                        raise ValueError(f"CSV row {row_number} contains non-finite data.")
                    time = values[time_index] / (1000 if settings["time_unit"] == "milliseconds" else 1)
                    if previous is not None:
                        if time <= previous:
                            raise ValueError(
                                f"Time must increase strictly; duplicate or reversed time at row {row_number}."
                            )
                        minimum_dt = min(minimum_dt, time - previous)
                        maximum_dt = max(maximum_dt, time - previous)
                    else:
                        first = time
                    previous = time
                    count += 1
                    for stat, index in zip(stats, indices):
                        value = values[index]
                        delta = value - stat["mean"]
                        stat["mean"] += delta / count
                        stat["m2"] += delta * (value - stat["mean"])
                        stat["minimum"], stat["maximum"] = min(stat["minimum"], value), max(stat["maximum"], value)
                    if writer and count <= 500:
                        writer.writerow([time, *[values[i] for i in indices]])
            if count < 3:
                raise ValueError("At least three data rows are required for a trace summary.")
            for stat in stats:
                stat["sample_sd"] = math.sqrt(max(0, stat.pop("m2") / (count - 1)))
                stat["count"] = count
                if not all(math.isfinite(v) for v in stat.values() if isinstance(v, (float, int))):
                    raise ValueError(
                        "Trace values overflow descriptive statistics; rescale the source data explicitly."
                    )
            warnings = []
            if maximum_dt > minimum_dt * 1.02:
                warnings.append(
                    "Irregular acquisition intervals detected; no resampling or interpolation is performed."
                )
            return {
                "rows": count,
                "duration_seconds": previous - first,
                "minimum_interval_seconds": minimum_dt,
                "maximum_interval_seconds": maximum_dt,
                "channels": stats,
                "warnings": warnings,
            }
        finally:
            if preview_stream:
                preview_stream.close()

    def check(self, root: Path, configuration: dict) -> dict:
        result = self.scan(root, configuration)
        return {**result, "estimated_output_bytes": 1024 * 1024}

    def run(self, root: Path, configuration: dict, output: Path) -> None:
        result = self.scan(root, configuration, output / "trace-preview-first-500.csv")
        result["preview"] = "First 500 samples only; summary uses all rows. No hypothesis testing or filtering."
        atomic_json(output / "trace-summary.json", result)
        with (output / "channel-summary.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(
                stream, fieldnames=["channel", "unit", "count", "minimum", "maximum", "mean", "sample_sd"]
            )
            writer.writeheader()
            writer.writerows(result["channels"])
