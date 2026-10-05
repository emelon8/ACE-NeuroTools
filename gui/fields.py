"""Presentation and input checks for existing columns; no new analysis defaults."""

import ast
import math
from datetime import datetime

# label, group, input kind, optional help; original CSV keys remain unchanged.
FIELDS = {
    "line number": ("Experiment number", "Experiment", "identity", ""),
    "id": ("Subject", "Experiment", "text", ""),
    "date (YYMMDD)": ("Recording date", "Experiment", "date", ""),
    "calcium imaging directory": ("Calcium recording folder", "Recordings", "folder", ""),
    "ephys directory": ("Electrophysiology recording folder", "Recordings", "folder", ""),
    "box calcium folder id": (
        "Calcium Box folder ID",
        "Recordings",
        "box",
        "The number at the end of a Box folder URL.",
    ),
    "box ephys folder id": (
        "Electrophysiology Box folder ID",
        "Recordings",
        "box",
        "The number at the end of a Box folder URL.",
    ),
    "rat weight (kg)": ("Subject weight (kg)", "Treatment", "number", ""),
    "systemic drug": ("Drug", "Treatment", "text", ""),
    "systemic dose (% or mg/kg/min)": ("Dose (% or mg/kg/min)", "Treatment", "text", ""),
    "systemic drug concentration (mg/mL)": ("Drug concentration (mg/mL)", "Treatment", "number", ""),
    "total systemic time (min)": ("Treatment duration (min)", "Treatment", "number", ""),
    "emg channel": ("EMG channel", "Channels and events", "text", ""),
    "events filename": ("Events file", "Channels and events", "text", ""),
    "LFP and EEG CSCs": (
        "LFP and EEG channels",
        "Channels and events",
        "text",
        "Separate channel names with semicolons.",
    ),
    "comments": ("Notes", "Notes", "notes", ""),
    "indices of TTL events to delete": ("TTL event indices to remove", "Timing", "list", "Use a list, e.g. [0, 2]."),
    "zero time (s)": ("Time zero (s)", "Timing", "number", ""),
    "baseline period (min)": ("Baseline period (min)", "Timing", "text", ""),
    "periods of high slow wave power (s)": ("High slow-wave periods (s)", "Timing", "text", ""),
    "control periods (s)": ("Control periods (s)", "Timing", "text", ""),
    "crop": (
        "Crop selection (legacy)",
        "Cropping and previews",
        "text",
        "Stored exactly as entered; this project uses the legacy crop column.",
    ),
    "crop_coords": ("Crop coordinates", "Cropping and previews", "quad", "Four coordinates: (x0, y0, x1, y1)."),
    "crop_square": ("Square crop (legacy)", "Cropping and previews", "text", ""),
    "ca_ephys_baseline_video_num": ("Baseline preview video", "Cropping and previews", "number", ""),
    "ca_ephys_slow_wave_video_num": ("Slow-wave preview video", "Cropping and previews", "number", ""),
    "ca_ephys_burst_suppression_video_num": ("Burst-suppression preview video", "Cropping and previews", "number", ""),
}

for key, label in {
    "decay_time": "Calcium decay time (s)",
    "K": "Initial component count (K)",
    "tsub": "Temporal downsampling",
    "ssub": "Spatial downsampling",
    "ssub_B": "Background spatial downsampling",
    "ring_size_factor": "Background ring size factor",
    "min_corr": "Minimum correlation",
    "min_pnr": "Minimum peak-to-noise ratio",
    "nb": "Background component count",
    "p": "Autoregressive order",
    "border_pix": "Excluded border width (pixels)",
    "rf": "Patch radius (rf)",
    "stride": "Patch overlap (stride)",
    "nb_patch": "Background components per patch",
    "min_SNR": "Minimum signal-to-noise ratio",
    "rval_thr": "Spatial correlation threshold",
    "merge_thr": "Component merge threshold",
    "max_deviation_rigid": "Maximum shift deviation (pixels)",
}.items():
    FIELDS[key] = (label, "Neuron detection", "number", "")

for key, label in {
    "update_background_components": "Update background components",
    "normalize_init": "Normalize before initialization",
    "center_psf": "Center the point-spread function",
    "del_duplicates": "Remove duplicate components",
    "low_rank_background": "Use a low-rank background",
    "only_init": "Initialization only",
    "use_cnn": "Use CNN component evaluation",
    "pw_rigid": "Use patchwise motion correction",
    "shifts_opencv": "Apply shifts with OpenCV",
}.items():
    group = "Motion correction" if key in {"pw_rigid", "shifts_opencv"} else "Neuron detection"
    FIELDS[key] = (label, group, "boolean", "")

for key, label in {
    "gSig": "Neuron radius (gSig)",
    "gSiz": "Neuron filter size (gSiz)",
    "max_shifts": "Maximum motion shifts (pixels)",
    "gSig_filt": "Motion filter size",
    "strides": "Motion patch spacing (pixels)",
    "overlaps": "Motion patch overlap (pixels)",
}.items():
    group = "Neuron detection" if key in {"gSig", "gSiz"} else "Motion correction"
    FIELDS[key] = (label, group, "pair", "Two numbers, e.g. (7, 7).")

FIELDS.update(
    {
        "method_deconvolution": ("Deconvolution method", "Neuron detection", "text", ""),
        "method_init": ("Initialization method", "Neuron detection", "text", ""),
        "border_nan": ("Motion border handling", "Motion correction", "text", ""),
    }
)
# This option belongs to motion correction even though it takes a number.
FIELDS["max_deviation_rigid"] = ("Maximum shift deviation (pixels)", "Motion correction", "number", "")


def describe(column: str, settings: bool = False) -> dict:
    label, group, kind, help_text = FIELDS.get(
        column, FIELDS.get(column.lower(), (column.replace("_", " "), "Other fields", "text", ""))
    )
    if settings and group in {"Experiment", "Recordings"}:
        group = "Recording details in settings"
    return {"key": column, "label": label, "group": group, "kind": kind, "help": help_text}


def validate(column: str, value: str) -> None:
    """Check only edited values; retain legacy blanks and missing-value markers."""
    kind = describe(column)["kind"]
    text = value.strip()
    if not text or text.lower() in {"none", "na", "nan", "null"}:
        return
    label = describe(column)["label"]
    try:
        if kind == "number" and not math.isfinite(float(text)):
            raise ValueError
        if kind == "date":
            if len(text) != 6 or not text.isascii() or not text.isdigit():
                raise ValueError
            datetime.strptime(text, "%y%m%d")
        if kind == "box" and (not text.isascii() or not text.isdigit()):
            raise ValueError
        if kind == "boolean" and text.lower() not in {"true", "false"}:
            raise ValueError
        if kind in {"pair", "quad", "list"}:
            parsed = ast.literal_eval(text)
            if not isinstance(parsed, (list, tuple)):
                raise ValueError
            length = {"pair": 2, "quad": 4}.get(kind)
            if length and len(parsed) != length:
                raise ValueError
            if not all(type(item) in {int, float} and math.isfinite(item) for item in parsed):
                raise ValueError
    except (ValueError, SyntaxError, TypeError, OverflowError) as exc:
        instructions = {
            "number": "Enter a number.",
            "date": "Choose a valid recording date.",
            "box": "Enter the numeric Box folder ID.",
            "boolean": "Choose Yes or No.",
            "pair": "Enter two numbers, e.g. (7, 7).",
            "quad": "Enter four coordinates, e.g. (0, 0, 100, 100).",
            "list": "Enter a list of numbers, e.g. [0, 2].",
        }
        raise ValueError(f"{label}: {instructions.get(kind, 'Check this value.')}") from exc
