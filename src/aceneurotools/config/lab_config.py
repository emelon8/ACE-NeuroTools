"""LabConfig — channel identity, study design, paths, and run settings loaded from lab_config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aceneurotools.shared.exceptions import ConfigurationError

if TYPE_CHECKING:
    from aceneurotools.config.stats_config import StudyMetadata

_VALID_MODES = {"compute", "stats", "all"}


@dataclass
class ConditionSpec:
    """A single experimental condition with its subject list and drug flag."""

    subjects: list[int]
    is_drug: bool


@dataclass
class PathsConfig:
    """File system paths for a lab project."""

    project_path: str
    data_path: str | None = None
    output_dir: str | None = None
    calcium_signal_dir: str | None = None


@dataclass
class RunConfig:
    """Pipeline execution settings."""

    mode: str = "all"
    analyses: list[str] | None = None
    line_nums: list[int] | None = None
    headless: bool = False
    verbose: bool = False
    history: bool = False


@dataclass
class LabConfig:
    """Lab-level configuration: channel identity, study design, paths, and run settings."""

    primary_channel: str
    freq_range: list[float]
    conditions: dict[str, ConditionSpec]
    time_windows: dict[int, list[list[float]]]
    secondary_channel: str | None = None
    paths: PathsConfig | None = None
    run: RunConfig | None = None

    def all_line_nums(self) -> list[int]:
        """Return all subject line numbers across all conditions, sorted."""
        nums: list[int] = []
        for spec in self.conditions.values():
            nums.extend(spec.subjects)
        return sorted(set(nums))

    def to_json(self, path: str | Path) -> None:
        """Write to JSON. Int time-window keys become strings; _-prefixed doc fields are dropped."""
        payload: dict[str, Any] = {
            "primary_channel": self.primary_channel,
            "secondary_channel": self.secondary_channel,
            "freq_range": self.freq_range,
            "conditions": {
                name: {"subjects": spec.subjects, "is_drug": spec.is_drug} for name, spec in self.conditions.items()
            },
            "time_windows": {str(k): v for k, v in self.time_windows.items()},
        }
        if self.paths is not None:
            payload["paths"] = {
                "project_path": self.paths.project_path,
                "data_path": self.paths.data_path,
                "output_dir": self.paths.output_dir,
                "calcium_signal_dir": self.paths.calcium_signal_dir,
            }
        if self.run is not None:
            payload["run"] = {
                "mode": self.run.mode,
                "analyses": self.run.analyses,
                "line_nums": self.run.line_nums,
                "headless": self.run.headless,
                "verbose": self.run.verbose,
                "history": self.run.history,
            }
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=2)

    @classmethod
    def from_json(cls, path: str | Path) -> LabConfig:
        """Load and validate a lab_config.json, collecting all errors before raising."""
        path = Path(path)
        if not path.exists():
            raise ConfigurationError(
                f"Lab config file not found: {path}\n"
                "Generate a template with:\n"
                "  python -m aceneurotools.init --project-path <your-project-directory>",
                hint="Run 'python -m aceneurotools.init' to create lab_config.json.",
            )

        try:
            with open(path) as fh:
                raw: dict[str, Any] = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                f"lab_config.json is not valid JSON: {exc}\n"
                "Common causes: trailing comma after the last item, "
                "missing comma between items, or unquoted string values.",
                hint="Validate your JSON at https://jsonlint.com or with: "
                "python -c \"import json; json.load(open('lab_config.json'))\"",
            ) from exc

        # Strip documentation-only keys (those starting with '_') before parsing.
        data = {k: v for k, v in raw.items() if not k.startswith("_")}

        # Collect all validation errors before raising.
        errors: list[str] = []

        primary_channel: str = _require_str(data, "primary_channel", errors)
        secondary_channel: str | None = _parse_optional_str(data, "secondary_channel", errors)
        freq_range: list[float] = _parse_freq_range(data, errors)
        conditions: dict[str, ConditionSpec] = _parse_conditions(data, errors)
        time_windows: dict[int, list[list[float]]] = _parse_time_windows(data, errors)
        paths: PathsConfig | None = _parse_paths(data, errors) if "paths" in data else None
        run: RunConfig | None = _parse_run(data, errors) if "run" in data else None

        # Cross-validation: every subject in conditions must have a time window.
        if conditions and time_windows:
            for cond_name, spec in conditions.items():
                for subj in spec.subjects:
                    if subj not in time_windows:
                        errors.append(
                            f"[time_windows] Subject {subj} "
                            f"(listed under conditions.{cond_name!r}) "
                            "has no time_windows entry."
                        )

        # Cross-validation: no subject may appear in more than one condition.
        seen_subjects: dict[int, str] = {}
        for cond_name, spec in conditions.items():
            for subj in spec.subjects:
                if subj in seen_subjects:
                    errors.append(
                        f"[conditions] Subject {subj} appears in both "
                        f"{seen_subjects[subj]!r} and {cond_name!r}. "
                        "Each subject may belong to exactly one condition."
                    )
                else:
                    seen_subjects[subj] = cond_name

        if errors:
            bullet_list = "\n".join(f"  • {e}" for e in errors)
            raise ConfigurationError(
                f"lab_config.json has {len(errors)} error(s):\n{bullet_list}\n\n"
                "Fix all errors above, then re-run.  To regenerate a valid "
                "template:  python -m aceneurotools.init --project-path <dir>",
                hint="Fix the listed field(s) and re-run.",
            )

        return cls(
            primary_channel=primary_channel,
            secondary_channel=secondary_channel,
            freq_range=freq_range,
            conditions=conditions,
            time_windows=time_windows,
            paths=paths,
            run=run,
        )

    def to_study_metadata(self) -> StudyMetadata:
        """Convert to StudyMetadata for use with the analysis engines."""
        from aceneurotools.config.stats_config import StudyMetadata  # local to avoid circular import

        drug_groups: dict[str, list[int]] = {name: list(spec.subjects) for name, spec in self.conditions.items()}
        no_drug_conditions: set[str] = {name for name, spec in self.conditions.items() if not spec.is_drug}
        return StudyMetadata(
            drug_groups=drug_groups,
            selections={k: [list(w) for w in v] for k, v in self.time_windows.items()},
            no_drug_conditions=no_drug_conditions,
        )


def _require_str(data: dict[str, Any], key: str, errors: list[str]) -> str:
    val = data.get(key)
    if not isinstance(val, str) or not val.strip():
        errors.append(f"[{key}] Must be a non-empty string.  Got: {val!r}")
        return ""
    return val.strip()


def _parse_optional_str(data: dict[str, Any], key: str, errors: list[str]) -> str | None:
    val = data.get(key)
    if val is None:
        return None
    if isinstance(val, str):
        stripped = val.strip()
        return stripped if stripped else None
    errors.append(f"[{key}] Must be a string or null.  Got: {val!r}")
    return None


def _parse_freq_range(data: dict[str, Any], errors: list[str]) -> list[float]:
    val = data.get("freq_range")
    default = [0.5, 4.0]
    if not isinstance(val, list) or len(val) != 2:
        errors.append(f"[freq_range] Must be a list of exactly two numbers, e.g. [0.5, 4.0].  Got: {val!r}")
        return default
    try:
        low, high = float(val[0]), float(val[1])
    except (TypeError, ValueError):
        errors.append(f"[freq_range] Both values must be numbers.  Got: {val!r}")
        return default
    if low <= 0:
        errors.append(f"[freq_range] lowcut must be > 0 Hz.  Got: {low}")
    if high <= 0:
        errors.append(f"[freq_range] highcut must be > 0 Hz.  Got: {high}")
    if low >= high:
        errors.append(f"[freq_range] lowcut ({low}) must be less than highcut ({high}).")
    return [low, high]


def _parse_conditions(data: dict[str, Any], errors: list[str]) -> dict[str, ConditionSpec]:
    raw = data.get("conditions")
    if not isinstance(raw, dict) or not raw:
        errors.append(
            "[conditions] Must be a non-empty object mapping condition names "
            'to {"subjects": [...], "is_drug": true/false}.  '
            f"Got: {type(raw).__name__ if raw is not None else 'missing'}"
        )
        return {}

    result: dict[str, ConditionSpec] = {}
    for name, entry in raw.items():
        if name.startswith("_"):
            continue  # skip documentation keys
        if not isinstance(entry, dict):
            errors.append(
                f'[conditions.{name!r}] Must be an object with "subjects" and "is_drug" keys.  Got: {entry!r}'
            )
            continue

        cond_errors: list[str] = []

        # Parse subjects list
        subjects_raw = entry.get("subjects")
        subjects: list[int] = []
        if not isinstance(subjects_raw, list) or not subjects_raw:
            cond_errors.append(
                f"[conditions.{name!r}.subjects] Must be a non-empty list of integers.  Got: {subjects_raw!r}"
            )
        else:
            for idx, s in enumerate(subjects_raw):
                try:
                    subjects.append(int(s))
                except (TypeError, ValueError):
                    cond_errors.append(f"[conditions.{name!r}.subjects[{idx}]] Must be an integer.  Got: {s!r}")

        # Parse is_drug flag
        is_drug_raw = entry.get("is_drug")
        if not isinstance(is_drug_raw, bool):
            cond_errors.append(
                f"[conditions.{name!r}.is_drug] Must be true or false (JSON boolean).  Got: {is_drug_raw!r}"
            )
            is_drug = True
        else:
            is_drug = is_drug_raw

        errors.extend(cond_errors)
        if subjects:  # only add if we have at least some valid subjects
            result[name] = ConditionSpec(subjects=subjects, is_drug=is_drug)

    return result


def _parse_time_windows(data: dict[str, Any], errors: list[str]) -> dict[int, list[list[float]]]:
    raw = data.get("time_windows")
    if not isinstance(raw, dict) or not raw:
        errors.append(
            "[time_windows] Must be a non-empty object mapping subject line "
            "numbers (as strings) to "
            "[[ctrl_start, ctrl_end], [treat_start, treat_end]] in minutes.  "
            f"Got: {type(raw).__name__ if raw is not None else 'missing'}"
        )
        return {}

    result: dict[int, list[list[float]]] = {}
    for key_str, windows in raw.items():
        if key_str.startswith("_"):
            continue  # skip documentation keys
        try:
            subj = int(key_str)
        except (ValueError, TypeError):
            errors.append(
                f"[time_windows] Key {key_str!r} is not a valid subject line "
                "number.  Keys must be integers represented as strings "
                '(e.g. "97").'
            )
            continue

        if not isinstance(windows, list) or len(windows) != 2:
            errors.append(
                f"[time_windows.{subj}] Must be exactly two windows: "
                "[[ctrl_start, ctrl_end], [treat_start, treat_end]].  "
                f"Got: {windows!r}"
            )
            continue

        parsed_windows: list[list[float]] = []
        window_ok = True
        for window_idx, window in enumerate(windows):
            label = "control" if window_idx == 0 else "treatment"
            if not isinstance(window, list) or len(window) != 2:
                errors.append(f"[time_windows.{subj}] {label} window must be [start, end] in minutes.  Got: {window!r}")
                window_ok = False
                parsed_windows.append([0.0, 0.0])
                continue
            try:
                start, end = float(window[0]), float(window[1])
            except (TypeError, ValueError):
                errors.append(f"[time_windows.{subj}] {label} window values must be numbers.  Got: {window!r}")
                window_ok = False
                parsed_windows.append([0.0, 0.0])
                continue
            if start < 0:
                errors.append(f"[time_windows.{subj}] {label} start must be >= 0.  Got: {start}")
                window_ok = False
            if start >= end:
                errors.append(f"[time_windows.{subj}] {label} start ({start}) must be less than end ({end}).")
                window_ok = False
            parsed_windows.append([start, end])

        if window_ok:
            result[subj] = parsed_windows

    return result


def _parse_paths(data: dict[str, Any], errors: list[str]) -> PathsConfig | None:
    raw = data.get("paths")
    if not isinstance(raw, dict):
        errors.append(
            "[paths] Must be an object with project_path and optional "
            f"data_path, output_dir, calcium_signal_dir.  Got: {raw!r}"
        )
        return None

    # Strip documentation keys.
    raw = {k: v for k, v in raw.items() if not k.startswith("_")}

    # project_path is required when paths section is present.
    project_path_raw = raw.get("project_path")
    if not isinstance(project_path_raw, str) or not project_path_raw.strip():
        errors.append(f"[paths.project_path] Must be a non-empty string path.  Got: {project_path_raw!r}")
        project_path = ""
    else:
        project_path = project_path_raw.strip()

    def _opt_path(key: str) -> str | None:
        val = raw.get(key)
        if val is None:
            return None
        if not isinstance(val, str):
            errors.append(f"[paths.{key}] Must be a string or null.  Got: {val!r}")
            return None
        return val.strip() or None

    return PathsConfig(
        project_path=project_path,
        data_path=_opt_path("data_path"),
        output_dir=_opt_path("output_dir"),
        calcium_signal_dir=_opt_path("calcium_signal_dir"),
    )


def _parse_run(data: dict[str, Any], errors: list[str]) -> RunConfig | None:
    raw = data.get("run")
    if not isinstance(raw, dict):
        errors.append(f"[run] Must be an object with mode, analyses, line_nums, headless, verbose.  Got: {raw!r}")
        return None

    # Strip documentation keys.
    raw = {k: v for k, v in raw.items() if not k.startswith("_")}

    # mode
    mode_raw = raw.get("mode", "all")
    if mode_raw not in _VALID_MODES:
        errors.append(f"[run.mode] Must be one of {sorted(_VALID_MODES)}.  Got: {mode_raw!r}")
        mode = "all"
    else:
        mode = str(mode_raw)

    # analyses
    analyses_raw = raw.get("analyses")
    analyses: list[str] | None = None
    if analyses_raw is not None:
        if not isinstance(analyses_raw, list):
            errors.append(f"[run.analyses] Must be a list of analysis key strings or null.  Got: {analyses_raw!r}")
        elif analyses_raw:
            analyses = [str(a) for a in analyses_raw]

    # line_nums
    line_nums_raw = raw.get("line_nums")
    line_nums: list[int] | None = None
    if line_nums_raw is not None:
        if not isinstance(line_nums_raw, list):
            errors.append(f"[run.line_nums] Must be a list of integers or null.  Got: {line_nums_raw!r}")
        elif line_nums_raw:
            try:
                line_nums = [int(n) for n in line_nums_raw]
            except (TypeError, ValueError):
                errors.append(f"[run.line_nums] All values must be integers.  Got: {line_nums_raw!r}")

    # headless
    headless_raw = raw.get("headless", False)
    if not isinstance(headless_raw, bool):
        errors.append(f"[run.headless] Must be true or false (JSON boolean).  Got: {headless_raw!r}")
        headless = False
    else:
        headless = headless_raw

    # verbose
    verbose_raw = raw.get("verbose", False)
    if not isinstance(verbose_raw, bool):
        errors.append(f"[run.verbose] Must be true or false (JSON boolean).  Got: {verbose_raw!r}")
        verbose = False
    else:
        verbose = verbose_raw

    # history (experiment version control opt-in; off by default until D07/D08)
    history_raw = raw.get("history", False)
    if not isinstance(history_raw, bool):
        errors.append(f"[run.history] Must be true or false (JSON boolean).  Got: {history_raw!r}")
        history = False
    else:
        history = history_raw

    return RunConfig(
        mode=mode,
        analyses=analyses,
        line_nums=line_nums,
        headless=headless,
        verbose=verbose,
        history=history,
    )
