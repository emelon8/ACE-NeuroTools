"""StatsConfig and StudyMetadata — algorithm parameters and study design for the stats pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from aceneurotools.shared.exceptions import ConfigurationError


@dataclass
class StatsConfig:
    """Tunable algorithm parameters for the statistical analysis pipeline."""

    # bandpass filter
    lowcut: float = 0.5
    highcut: float = 4.0
    filter_order: int = 2
    edge_trim_seconds: float = 5.0

    # normalisation
    normalization_method: str = "zscore"  # 'zscore' | 'none'
    global_normalization: bool = True

    # single-subject statistics
    correct_autocorrelation: bool = True
    confidence_level: float = 0.95
    max_acf_lags: int = 100

    # population statistics
    bootstrap_iterations: int = 10_000
    paired_test: str = "wilcoxon"  # 'wilcoxon' | 'ttest'
    min_subjects_for_stats: int = 4

    # Welch coherence
    coherence_nperseg_seconds: float | None = None
    # Window length for scipy.signal.coherence via Welch's method.
    # None → scipy default (256 samples, matching the legacy scripts).
    # Set explicitly (e.g. 5.0) for a time-based nperseg.

    # coherogram
    coherogram_window_length: float = 5.0   # seconds
    coherogram_window_step: float = 2.5     # seconds
    coherogram_nrolling: int = 8

    # multitaper spectrogram
    spectrogram_window_length: float = 60.0
    spectrogram_window_step: float = 3.0
    spectrogram_time_bandwidth: float = 2.0
    spectrogram_freq_lims: list[float] = field(default_factory=lambda: [0.0, 20.0])

    # output
    plot_formats: list[str] = field(default_factory=lambda: ["svg", "tiff"])
    color_dpi: int = 300
    headless: bool = False

    def to_json(self, path: str | Path) -> None:
        with open(path, "w") as fh:
            json.dump(asdict(self), fh, indent=2)

    @classmethod
    def from_json(cls, path: str | Path) -> StatsConfig:
        with open(path) as fh:
            data: dict[str, Any] = json.load(fh)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# default drug-group → subject mapping
#:
_DEFAULT_DRUG_GROUPS: dict[str, list[int]] = {
    "dexmedetomidine: 0.00045": [46, 47, 64, 88, 97, 101],
    "dexmedetomidine: 0.0003":  [40, 41, 48, 87, 93, 94],
    "propofol":                 [36, 43, 44, 86, 99, 103],
    "ketamine":                 [39, 42, 45, 85, 96, 112],
}

# default time windows per subject: { line_num: [[ctrl_start, ctrl_end], [treat_start, treat_end]] } minutes
_DEFAULT_SELECTIONS: dict[int, list[list[float]]] = {
    # dexmedetomidine 0.00045
    46:  [[1,    20],    [28.24, 75]],
    47:  [[1,    20],    [28.24, 75]],
    64:  [[4,    17],    [28.24, 75]],
    88:  [[1,     8],    [28.24, 83.24]],
    97:  [[1,    13],    [28.24, 83.24]],
    101: [[1,    25],    [37,    90]],
    # dexmedetomidine 0.0003
    40:  [[8,    20],    [55,    75]],
    41:  [[10,   19],    [60,    68]],
    48:  [[1,    20],    [25,    35]],
    87:  [[5,    13],    [73,    85]],
    93:  [[18,   28],    [75,    95]],
    94:  [[1,    20],    [75,    90]],
    # propofol
    36:  [[1,    11],    [55,    67]],
    43:  [[15,   20],    [40,    60]],
    44:  [[0,    21],    [40,    65]],
    86:  [[5,    16],    [33,    65]],
    99:  [[0,    19],    [33,    45]],
    103: [[1,    17],    [38,    65]],
    # ketamine
    39:  [[10,   20],    [38,    50]],
    42:  [[1,    20],    [40,    51]],
    45:  [[1,    15],    [40,    60]],
    85:  [[14,   24],    [30,    50]],
    96:  [[1,    12],    [38,    55]],
    112: [[1,    10],    [40,    60]],
}


class StudyMetadata:
    """Drug groups and per-subject control/treatment time windows (in minutes).

    Build from a LabConfig with lab.to_study_metadata() rather than constructing directly.
    """

    def __init__(
        self,
        drug_groups: dict[str, list[int]],
        selections: dict[int, list[list[float]]],
        no_drug_conditions: set[str] | None = None,
    ) -> None:
        self.drug_groups = drug_groups
        self.selections = selections
        self.no_drug_conditions: set[str] = no_drug_conditions or {"sleep"}
        # Build reverse lookup: line_num → drug label
        self._number_to_drug: dict[int, str] = {
            n: drug
            for drug, nums in drug_groups.items()
            for n in nums
        }

    def drug_of(self, line_num: int) -> str | None:
        return self._number_to_drug.get(line_num)

    def has_drug_event(self, line_num: int) -> bool:
        drug = self.drug_of(line_num)
        return drug is not None and drug not in self.no_drug_conditions

    def all_line_nums(self) -> list[int]:
        return sorted(self._number_to_drug.keys())

    def line_nums_for(self, drug: str) -> list[int]:
        return list(self.drug_groups.get(drug, []))

    @classmethod
    def default(cls) -> StudyMetadata:
        """Always raises ConfigurationError. Use LabConfig.from_json() instead."""
        raise ConfigurationError(
            "StudyMetadata.default() is no longer available.\n\n"
            "ACE-NeuroTools requires a lab_config.json specific to your study — "
            "the package does not bundle default subject data.\n\n"
            "Quick start:\n"
            "  python -m aceneurotools.init --project-path /your/project\n\n"
            "Then pass the generated file at runtime:\n"
            "  python -m aceneurotools.pipelines.stats "
            "--lab-config lab_config.json ...",
            hint="Run 'python -m aceneurotools.init --project-path /your/project'.",
        )

    @classmethod
    def example(cls) -> StudyMetadata:
        """Bundled example study (24 subjects, 4 drug conditions). For tests only."""
        return cls(
            drug_groups=dict(_DEFAULT_DRUG_GROUPS),
            selections={k: [list(w) for w in v] for k, v in _DEFAULT_SELECTIONS.items()},
        )

    @classmethod
    def from_json(cls, path: str | Path) -> StudyMetadata:
        with open(path) as fh:
            raw: dict[str, Any] = json.load(fh)

        # JSON keys are always strings; convert int-keyed dicts back.
        drug_groups: dict[str, list[int]] = raw["drug_groups"]
        selections: dict[int, list[list[float]]] = {
            int(k): v for k, v in raw["selections"].items()
        }
        no_drug = set(raw.get("no_drug_conditions", ["sleep"]))
        return cls(drug_groups=drug_groups, selections=selections, no_drug_conditions=no_drug)

    def to_json(self, path: str | Path) -> None:
        payload = {
            "drug_groups": self.drug_groups,
            "selections": {str(k): v for k, v in self.selections.items()},
            "no_drug_conditions": list(self.no_drug_conditions),
        }
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=2)
