from aceneurotools.shared.calcium_imaging_names import options_for_keys

"""Read the existing CLI defaults without importing heavy pipeline modules."""

import csv
import io

import pandas as pd

from aceneurotools.shared import config_utils
from aceneurotools.shared.cli_utils import apply_headless_policy
from aceneurotools.shared.csv_worker import CSVWorker
from aceneurotools.shared.pipeline_defaults import pipeline_defaults, pipeline_keys

PIPELINES = {
    "compute": "Mean fluorescence",
    "preprocess": "Crop and preprocess movie",
    "miniscope": "Calcium imaging (preprocessing and CNMF-E)",
    "ephys": "Electrophysiology",
    "multimodal": "Calcium imaging + electrophysiology alignment",
}


def specification(kind):
    if not isinstance(kind, str) or kind not in PIPELINES:
        raise ValueError("Choose a supported analysis.")
    if kind == "compute":
        return pipeline_defaults("compute"), pipeline_keys("compute")
    module = "miniscope" if kind == "preprocess" else kind
    allowed = pipeline_keys(module)
    defaults = pipeline_defaults(module)
    # Headless policy is the existing CLI's policy, including deferred neuron selection.
    defaults["headless"] = True
    apply_headless_policy(pipeline_name=kind, run_params=defaults)
    defaults.pop("headless")
    if kind == "preprocess":
        allowed &= {
            "filenames",
            "crop",
            "crop_coords",
            "detrend_method",
            "df_over_f",
            "secs_window",
            "quantile_min",
            "df_over_f_method",
        }
        defaults = {key: value for key, value in defaults.items() if key in allowed}
        defaults["filenames"] = []
    return defaults, allowed


def effective_parameters(kind, raw):
    defaults, allowed = specification(kind)
    # Match the existing CSV reader's missing-value handling. GUI rows retain raw
    # strings; the CLI reads through pandas, which treats nan/NA/NULL as blanks.
    if raw:
        table = io.StringIO(newline="")
        writer = csv.DictWriter(table, fieldnames=list(raw))
        writer.writeheader()
        writer.writerow(raw)
        table.seek(0)
        values = pd.read_csv(table, dtype=str).iloc[0].to_dict()
    else:
        values = {}
    converted = CSVWorker.convert_data_types(values)
    parsed = options_for_keys(config_utils.parse_analysis_params(converted), allowed)
    params = dict(defaults)
    sources = {key: "CLI default" for key in defaults}
    for key, value in parsed.items():
        if key in allowed:
            params[key], sources[key] = value, "Saved CSV"
    # Values are interpreted by the same mapper used by the CLI.
    forced = {"headless": True}
    apply_headless_policy(pipeline_name=kind, run_params=forced)
    for key, value in forced.items():
        if key in params and params[key] != value:
            sources[key] = "GUI: no separate windows"
            params[key] = value
    return params, sources


def settings_keys():
    return {"crop_coords", *specification("miniscope")[1], *specification("ephys")[1], *specification("multimodal")[1]}


def validate_settings(kind, changes):
    """Reject invalid newly edited run flags before adding them to a CSV."""
    defaults, allowed = specification(kind)
    converted = CSVWorker.convert_data_types(changes)
    for key, value in converted.items():
        if value is None:
            continue
        if key == "time_range":
            import math

            if (
                not isinstance(value, (list, tuple))
                or len(value) != 2
                or any(
                    isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item)
                    for item in value
                )
                or value[0] >= value[1]
            ):
                raise ValueError("time_range: enter [start, end] in seconds, with end after start.")
        default = defaults.get(key)
        if isinstance(default, bool) and not isinstance(value, bool):
            raise ValueError(f"{key}: choose Yes or No.")
        if isinstance(default, (int, float)) and not isinstance(default, bool):
            import math

            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key}: enter a finite number.")
            if key in {"n_processes", "n"} and (value < 1 or int(value) != value):
                raise ValueError(f"{key}: enter a positive whole number.")
        if isinstance(default, list) and not isinstance(value, (list, tuple)):
            raise ValueError(f"{key}: enter a list, such as {default}.")
