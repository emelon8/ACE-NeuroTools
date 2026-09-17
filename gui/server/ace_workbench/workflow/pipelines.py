"""Operation strategies: minimal questions, validated values and effective settings."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from .models import Candidate, Question


def choices(values: list[str]) -> list[dict[str, str]]:
    return [{"value": value, "label": value} for value in values]


class Pipeline(ABC):
    id: str
    label: str
    description: str
    formats: set[str]
    scientific = True

    @abstractmethod
    def questions(self, candidate: Candidate) -> list[Question]: ...

    def effective(self, candidate: Candidate, answers: dict) -> dict:
        return dict(answers)

    def supports(self, candidate: Candidate) -> bool:
        return candidate.format in self.formats


class InventoryPipeline(Pipeline):
    id = "inventory"
    label = "Inspect recording integrity"
    description = "Hash and inventory the copied files. No signal processing or biological conclusions."
    formats = set()
    scientific = False

    def supports(self, candidate: Candidate) -> bool:
        return True

    def questions(self, candidate: Candidate) -> list[Question]:
        return []


class TracePipeline(Pipeline):
    id = "trace-summary"
    label = "Summarize numeric traces"
    description = "Validate timing and summarize each signal (count, range, mean, sample SD); preserve original values."
    formats = {"trace-csv"}

    def questions(self, candidate: Candidate) -> list[Question]:
        columns = candidate.metadata["columns"]
        known = [c for c in columns if c in {"time_s", "time_ms"}]
        result = []
        if len(known) != 1:
            result.extend(
                [
                    Question(
                        "time_column",
                        "Time column",
                        "select",
                        "Select acquisition time, not a signal or row number.",
                        choices=choices(columns),
                    ),
                    Question(
                        "time_unit",
                        "Time unit",
                        "select",
                        "Units of the selected time column.",
                        choices=choices(["seconds", "milliseconds"]),
                    ),
                ]
            )
        result.append(
            Question(
                "signal_unit",
                "Signal unit",
                help="Applies to every signal column. Use the recorded unit (for example µV or ΔF/F); split tables with different units. Enter 'arbitrary units' only if appropriate.",
            )
        )
        return result

    def effective(self, candidate: Candidate, answers: dict) -> dict:
        known = [c for c in candidate.metadata["columns"] if c in {"time_s", "time_ms"}]
        timing = (
            {"time_column": known[0], "time_unit": "seconds" if known[0] == "time_s" else "milliseconds"}
            if len(known) == 1
            else {}
        )
        return {**timing, **answers, "missing_values": "reject", "filter": "none", "statistics": "descriptive only"}


class CNMFEPipeline(Pipeline):
    id = "cnmfe"
    label = "Extract calcium components (CNMF-E)"
    description = (
        "Use the existing ACENeuroTools CaImAn processing stage. Components require scientific quality review."
    )
    formats = {"ucla-miniscope", "onix-miniscope"}

    def questions(self, candidate: Candidate) -> list[Question]:
        result = []
        if candidate.format == "ucla-miniscope" and not candidate.metadata.get("calcium_evidence"):
            result.append(
                Question(
                    "recording_content",
                    "Recording content",
                    "select",
                    "Metadata does not identify a calcium imaging device. Confirm what the movie contains before CNMF-E.",
                    choices=choices(["calcium imaging"]),
                )
            )
        if candidate.format == "ucla-miniscope" and not candidate.metadata.get("frame_rate"):
            result.append(
                Question(
                    "frame_rate",
                    "Acquisition frame rate (Hz)",
                    "number",
                    "No valid frameRate in acquisition metadata. Match the recording, not playback speed.",
                    minimum=0.01,
                    maximum=10000,
                )
            )
        result.extend(
            [
                Question(
                    "decay_time",
                    "Indicator decay time (seconds)",
                    "number",
                    "Use the indicator's measured/validated transient decay; this is not inferred from filenames.",
                    minimum=0.001,
                    maximum=60,
                ),
                Question(
                    "cell_radius",
                    "Neuron spatial scale gSig (pixels)",
                    "integer",
                    "Gaussian spatial scale in each image axis; choose from your recording's cell size.",
                    minimum=1,
                    maximum=100,
                ),
                Question(
                    "min_corr",
                    "Seed correlation threshold",
                    "number",
                    "Starting value only; review against a correlation image for this recording.",
                    0.8,
                    minimum=0,
                    maximum=1,
                ),
                Question(
                    "min_pnr",
                    "Seed peak-to-noise threshold",
                    "number",
                    "Starting value only; review against a PNR image for this recording.",
                    10,
                    minimum=0.01,
                    maximum=1000,
                ),
                Question(
                    "motion_correct",
                    "Rigid motion correction",
                    "select",
                    "Choose whether to correct XY drift before extraction.",
                    "off",
                    choices=choices(["off", "on"]),
                ),
            ]
        )
        return result

    def effective(self, candidate: Candidate, answers: dict) -> dict:
        radius = answers["cell_radius"]
        return {
            "frame_rate": candidate.metadata.get("frame_rate", answers.get("frame_rate")),
            "decay_time": answers["decay_time"],
            "gSig": [radius, radius],
            "gSiz": [4 * radius + 1] * 2,
            "min_corr": answers["min_corr"],
            "min_pnr": answers["min_pnr"],
            "motion_correct": answers["motion_correct"] == "on",
            "max_shifts": [6, 6],
            "pw_rigid": False,
            "method_init": "corr_pnr",
            "method_deconvolution": "oasis",
            "p": 0,
            "K": None,
            "nb": 0,
            "rf": max(40, 4 * radius),
            "stride": max(20, 2 * radius),
            "tsub": 1,
            "ssub": 1,
            "merge_thr": 0.8,
            "min_SNR": 2.5,
            "use_cnn": False,
            "ring_size_factor": 1.4,
            "normalize_init": False,
            "center_psf": True,
            "crop": False,
            "detrend": None,
            "df_over_f": False,
            "workers": 1,
            "curation": "required after extraction",
        }


class EphysPipeline(Pipeline):
    id = "ephys-export"
    label = "Load and export electrophysiology"
    description = "Use the existing reader to export calibrated channels and acquisition timestamps, without filtering or artifact removal."
    formats = {"neuralynx", "rhs2116"}

    def questions(self, candidate: Candidate) -> list[Question]:
        return [
            Question(
                "channel",
                "Channel to export",
                "select",
                "Anatomical identity is not inferred from the filename.",
                choices=choices(candidate.metadata.get("channels", [])),
            )
        ]

    def effective(self, candidate: Candidate, answers: dict) -> dict:
        return {**answers, "filter": "none", "artifact_removal": False, "truncate": False, "time_unit": "seconds"}


class PipelineRegistry:
    def __init__(self, pipelines: list[Pipeline] | None = None):
        self.pipelines = (
            pipelines
            if pipelines is not None
            else [CNMFEPipeline(), EphysPipeline(), TracePipeline(), InventoryPipeline()]
        )

    def get(self, key: str, candidate: Candidate) -> Pipeline:
        for pipeline in self.pipelines:
            if pipeline.id == key and pipeline.supports(candidate):
                return pipeline
        raise ValueError("The selected operation does not support this recording.")

    def describe(self, candidate: Candidate) -> list[dict]:
        return [
            {"id": p.id, "label": p.label, "description": p.description, "scientific": p.scientific}
            for p in self.pipelines
            if p.supports(candidate)
        ]


class QuestionEngine:
    """Deterministic questions and authoritative server-side answer validation."""

    def validate(self, pipeline: Pipeline, candidate: Candidate, answers: dict) -> dict:
        questions = pipeline.questions(candidate)
        unexpected = set(answers) - {q.key for q in questions}
        if unexpected:
            raise ValueError(f"Unexpected answers for this recording/operation: {', '.join(sorted(unexpected))}")
        result = {}
        for q in questions:
            value = answers.get(q.key, q.default)
            if value is None or value == "":
                if q.required:
                    raise ValueError(f"Answer required: {q.label}")
                continue
            if q.kind in {"number", "integer"}:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"{q.label} must be a finite number.")
                if q.kind == "integer" and int(value) != value:
                    raise ValueError(f"{q.label} must be an integer.")
                if (q.minimum is not None and value < q.minimum) or (q.maximum is not None and value > q.maximum):
                    raise ValueError(f"{q.label} is outside the allowed range.")
                value = int(value) if q.kind == "integer" else value
            else:
                if not isinstance(value, str) or not value.strip() or len(value) > 160:
                    raise ValueError(f"Invalid answer: {q.label}")
                value = value.strip()
                if q.choices and value not in {c["value"] for c in q.choices}:
                    raise ValueError(f"Choose a listed value for {q.label}.")
            result[q.key] = value
        return result
