"""Read the existing CLI defaults without importing heavy pipeline modules."""

import ast
import csv
import io
from pathlib import Path

import pandas as pd

from aceneurotools.shared import config_utils
from aceneurotools.shared.cli_utils import apply_headless_policy
from aceneurotools.shared.csv_worker import CSVWorker

PIPELINES = {
    "compute": "Mean fluorescence",
    "preprocess": "Crop and preprocess movie",
    "miniscope": "Calcium imaging (preprocessing and CNMF-E)",
    "ephys": "Electrophysiology",
}


def specification(kind):
    if not isinstance(kind, str) or kind not in PIPELINES:
        raise ValueError("Choose a supported analysis.")
    if kind == "compute":
        return {"crop": True}, {"crop"}
    module = "miniscope" if kind == "preprocess" else kind
    source = Path(config_utils.__file__).parent.parent / "pipelines" / f"{module}.py"
    tree = ast.parse(source.read_text())
    run = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "run")
    allowed = {
        arg.arg for arg in run.args.args if arg.arg not in {"self", "line_num", "project_path", "data_path", "headless"}
    }
    default_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "defaults" for target in node.targets)
    )
    defaults = ast.literal_eval(default_node.value)
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
    parsed = config_utils.parse_analysis_params(converted)
    params = dict(defaults)
    sources = {key: "CLI default" for key in defaults}
    for key, value in parsed.items():
        if key in allowed:
            params[key], sources[key] = value, "Saved CSV"
    # Include supported run flags that the current source CSV mapper omits.
    for key in allowed:
        if key in converted and converted[key] is not None:
            value = converted[key]
            if key == "crop" and not isinstance(value, bool):
                if isinstance(value, (list, tuple)) and len(value) == 4:
                    params["crop_coords"], sources["crop_coords"] = value, "Legacy crop column"
                continue
            params[key], sources[key] = value, "Saved CSV"
    if kind != "ephys" and converted.get("crop_coords") is not None:
        params["crop_coords"], sources["crop_coords"] = converted["crop_coords"], "Saved CSV"
    forced = {"headless": True}
    apply_headless_policy(pipeline_name=kind, run_params=forced)
    for key, value in forced.items():
        if key in params and params[key] != value:
            sources[key] = "GUI: no separate windows"
            params[key] = value
    return params, sources


def settings_keys():
    return {"crop_coords", *specification("miniscope")[1], *specification("ephys")[1]}


def validate_settings(kind, changes):
    """Reject invalid newly edited run flags before adding them to a CSV."""
    defaults, allowed = specification(kind)
    converted = CSVWorker.convert_data_types(changes)
    for key, value in converted.items():
        if value is None:
            continue
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
