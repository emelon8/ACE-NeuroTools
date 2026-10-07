#!/usr/bin/env python3
"""Regenerate pipeline tutorial notebooks (used during development)."""

from __future__ import annotations

import json
from pathlib import Path


def make_nb(cells: list[tuple[str, str]]) -> dict:
    out: dict = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python"},
        },
        "cells": [],
    }
    for kind, text in cells:
        if kind == "md":
            lines = text.splitlines(keepends=True) or [text]
            out["cells"].append({"cell_type": "markdown", "metadata": {}, "source": lines})
        else:
            lines = [ln + "\n" for ln in text.split("\n")]
            if lines and lines[-1] == "\n":
                lines.pop()
            out["cells"].append(
                {
                    "cell_type": "code",
                    "metadata": {},
                    "execution_count": None,
                    "outputs": [],
                    "source": lines,
                }
            )
    return out


def save(name: str, data: dict) -> None:
    root = Path(__file__).resolve().parent.parent
    p = root / "notebooks" / name
    p.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print("wrote", p)


def ephys_cells() -> list[tuple[str, str]]:
    return [
        (
            "md",
            """# ACE-NeuroTools: Ephys pipeline tutorial

Hands-on walkthrough of **electrophysiology** loading and analysis: metadata from your project CSVs, raw data under `data_path`, channel extraction, optional filtering and Hilbert phase, and plots via `ChannelWorker`.

**Audience:** You have a project directory with `experiments.csv` and `analysis_parameters.csv`, plus Neuralynx (or compatible) data under a shared raw-data root.

**Documentation preview:** after syncing notebooks ([getting started](https://github.com/emelon8/ACE-NeuroTools/blob/main/docs/getting_started.md)), these render under the site *Tutorials* tab.
""",
        ),
        (
            "md",
            """## Prerequisites

- Python **3.10+** and ACE-NeuroTools: `pip install -e .` from the repository root.
- **`project_path`**: folder that contains **`experiments.csv`** and **`analysis_parameters.csv`** at its top level.
- **`line_num`**: same experiment row in **both** CSVs.
- **`data_path`**: base folder for **raw** recordings; path fields in `experiments.csv` are resolved under this root.
""",
        ),
        (
            "md",
            """## Project layout: `project_path` vs `data_path`

| Variable | Role |
|----------|------|
| **`project_path`** | Experiment **project** (CSVs only live here). |
| **`data_path`** | **Raw** ephys tree (e.g. `.ncs` files). |

Example:

```
my_project/                 ← project_path
  experiments.csv
  analysis_parameters.csv
shared_raw/                 ← data_path
  session_01/
    CSCxy.ncs
```

If you omit `data_path` when constructing `ExperimentDataManager`, the package falls back to an internal default under the repo — **always pass `data_path` explicitly** in real workflows.
""",
        ),
        (
            "code",
            """from pathlib import Path

# --- edit for your machine ---
project_path = Path("/path/to/your/project")
data_path = Path("/path/to/your/raw_data")
line_num = 96
channel_name = "PFCLFPvsCBEEG"

ex_csv = project_path / "experiments.csv"
ap_csv = project_path / "analysis_parameters.csv"
for label, p in ("experiments.csv", ex_csv), ("analysis_parameters.csv", ap_csv):
    if not p.is_file():
        raise FileNotFoundError(
            f"Missing {label} at {p}\\n"
            f"project_path must be the directory that contains both CSVs (not the raw-data root)."
        )
print("OK: found both CSVs under project_path.")
""",
        ),
        (
            "code",
            """from aceneurotools.shared.experiment_data_manager import ExperimentDataManager

edm = ExperimentDataManager(
    line_num,
    project_path=project_path,
    data_path=data_path,
    logging_level="INFO",
)
print("metadata id:", edm.metadata.get("id") if edm.metadata else None)
print("ephys directory (resolved):", edm.get_ephys_directory())
""",
        ),
        (
            "md",
            """## Table of contents

0. Setup — paths and CSVs (above)
1. Verify raw ephys for this line
2. Create `EphysDataManager` and import block
3. Process block → channels (artifacts + channel list)
4. Bandpass filter (`filter_type`, `filter_range`)
5. Hilbert phase
6. Plots via `ChannelWorker`
7. One-shot `EphysPipeline.run`
8. Troubleshooting
""",
        ),
        (
            "md",
            """### Step 1 — Verify raw data (`file_downloader.verify_file_by_line`)

Mirrors [EphysPipeline.run](https://github.com/emelon8/ACE-NeuroTools/blob/main/docs/api/pipelines.md). Ensures ephys files for this `line_num` exist under `data_path`.
""",
        ),
        (
            "code",
            """from aceneurotools.shared import file_downloader

experiments_csv = project_path / "experiments.csv"
file_downloader.verify_file_by_line(
    line_num=line_num,
    csv_path=experiments_csv,
    do_type="ephys",
    base_file_path=data_path,
)
""",
        ),
        (
            "md",
            """### Step 2 — Import ephys block (`EphysDataManager.create`)

Auto-selects backend from the folder layout. Processing is a separate step so you can see the object between import and channel extraction.
""",
        ),
        (
            "code",
            """from aceneurotools.ephys.ephys_data_manager import EphysDataManager

ephys_directory = edm.get_ephys_directory()
if ephys_directory is None:
    raise ValueError("ephys directory could not be determined from experiment metadata.")

ephys_dm = EphysDataManager.create(
    ephys_directory=ephys_directory,
    auto_import_ephys_block=True,
    auto_process_block=False,
    auto_compute_phases=False,
)
""",
        ),
        (
            "md",
            """### Step 3 — `process_ephys_block_to_channels`

Builds `Channel` objects for each requested CSC name (`channel_name` must exist in metadata).
""",
        ),
        (
            "code",
            """ephys_dm.process_ephys_block_to_channels(
    remove_artifacts=True,
    channels=[channel_name],
)
ch0 = ephys_dm.get_channel(channel_name)
print("has signal:", ch0.signal is not None, "n:", len(ch0.signal) if ch0.signal is not None else None)
""",
        ),
        (
            "md",
            """### Step 4 — Bandpass (`filter_ephys`)

**`EphysPipeline.run` only filters when `filter_type` is not `None`.** Here we call `filter_ephys` directly with `replace_signal=False` (pipeline default): filtered samples go to `signal_filtered`.
""",
        ),
        (
            "code",
            """ephys_dm.filter_ephys(channel_name, ftype="butter", cut=[0.5, 4.0], replace_signal=False)
ch = ephys_dm.get_channel(channel_name)
assert ch.signal_filtered is not None
""",
        ),
        (
            "md",
            """### Step 5 — Phase (`compute_phases_all_channels`)

Typically run **after** bandpass so phase reflects the band of interest.
""",
        ),
        (
            "code",
            """ephys_dm.compute_phases_all_channels()
ch = ephys_dm.get_channel(channel_name)
""",
        ),
        (
            "md",
            """### Step 6 — `ChannelWorker` plots

`plot_channel`, `plot_spectrogram`, and `plot_phases` match the flags on `EphysPipeline.run`. Uncomment in a desktop session if your backend is interactive.
""",
        ),
        (
            "code",
            """from aceneurotools.ephys.channel_worker import ChannelWorker

cw = ChannelWorker(ch)
# cw.plot_channel(use_filtered=True)
# cw.plot_spectrogram(use_filtered=True, plot_events=False)
# cw.plot_phases()
print("Uncomment plot_* in a GUI-capable environment.")
""",
        ),
        (
            "md",
            """### Step 7 — One-shot API

`headless=True` disables interactive pipeline plots; use earlier steps or set `plot_*` True with a GUI backend.
""",
        ),
        (
            "code",
            """from aceneurotools.pipelines.ephys import EphysPipeline

pipeline = EphysPipeline()
pipeline.run(
    line_num=line_num,
    project_path=project_path,
    data_path=data_path,
    channel_name=channel_name,
    remove_artifacts=True,
    filter_type="butter",
    filter_range=[0.5, 4.0],
    compute_phases=True,
    plot_channel=False,
    plot_spectrogram=False,
    plot_phases=False,
    headless=True,
)
ch = pipeline.ephys_data_manager.get_channel(channel_name)
print("filtered:", ch.signal_filtered is not None)
""",
        ),
        (
            "md",
            """### Step 8 — Quick time-domain check (notebook)

Uses `signal_filtered` when present.
""",
        ),
        (
            "code",
            """import matplotlib.pyplot as plt
import numpy as np

ch = ephys_dm.get_channel(channel_name)
vec = ch.signal_filtered if ch.signal_filtered is not None else ch.signal
t = np.asarray(ch.time_vector)
dt = float(np.median(np.diff(t[:5000]))) if len(t) > 1 else 1.0
n = min(len(vec), int(30.0 / dt))
plt.figure(figsize=(12, 3))
plt.plot(t[:n], vec[:n])
plt.title(f"{channel_name} (~first 30 s)")
plt.xlabel("Time (s)")
plt.show()
""",
        ),
        (
            "md",
            """## Troubleshooting

- **CSVs not found:** `project_path` must be the folder **containing** both files, not `data_path`.
- **`verify_file_by_line` fails:** Wrong `data_path`, missing downloads, or bad line — see data management guide / Box credentials.
- **`signal_filtered` is None:** No `filter_type` / no `filter_ephys` — filtering is opt-in.
- **`run_all_channels`:** Incomplete in the library; loop channels explicitly.
""",
        ),
    ]


def miniscope_cells() -> list[tuple[str, str]]:
    return [
        (
            "md",
            """# ACE-NeuroTools: Miniscope pipeline tutorial

Step-by-step **calcium imaging** path: same `project_path` / `data_path` story as ephys, then `MiniscopeDataManager` → `MiniscopePreprocessor` → `MiniscopeProcessor` → `MiniscopePostprocessor` (same order as `MiniscopePipeline.run`).
""",
        ),
        (
            "md",
            """## Prerequisites

- ACE-NeuroTools in an environment with **CaImAn** (see repo environment YAMLs).
- `project_path` with **`experiments.csv`** + **`analysis_parameters.csv`**.
- `data_path` where miniscope movies / metadata live for this `line_num`.
""",
        ),
        (
            "md",
            """## Project layout (same two-path rule)

| Path | Contents |
|------|----------|
| **`project_path`** | `experiments.csv`, `analysis_parameters.csv` |
| **`data_path`** | Raw miniscope files (e.g. `.avi`, `metaData.json`, etc.) |

**`analysis_parameters.csv`** supplies `crop_coords` when you pass `crop_coords=None` (or non-headless GUI flows).
""",
        ),
        (
            "code",
            """from pathlib import Path

project_path = Path("/path/to/your/project")
data_path = Path("/path/to/your/raw_data")
line_num = 96
filenames = ["0.avi"]  # match your session; CLI defaults to this pattern
headless = True  # True disables crop/curation GUIs (cluster / docs friendly)

for label, p in ("experiments.csv", project_path / "experiments.csv"), (
    "analysis_parameters.csv",
    project_path / "analysis_parameters.csv",
):
    if not p.is_file():
        raise FileNotFoundError(f"Missing {label} at {p}")
print("OK: project CSVs found.")
""",
        ),
        (
            "code",
            """from aceneurotools.shared.experiment_data_manager import ExperimentDataManager

edm = ExperimentDataManager(line_num, project_path=project_path, data_path=data_path)
print("calcium imaging dir:", edm.metadata.get("calcium imaging directory") if edm.metadata else None)
print("analysis params keys (sample):", list(edm.analysis_params.keys())[:12] if edm.analysis_params else [])
""",
        ),
        (
            "md",
            """## Table of contents

0. Paths + CSV validation
1. `filenames` and `headless`
2. `MiniscopeDataManager.create`
3. Preprocess (crop, detrend, ΔF/F)
4. Process (motion correction, CNMF-E)
5. Postprocess (events, phase, filter, spectrogram)
6. Inspect `MiniscopeDataManager`
7. One-shot `MiniscopePipeline.run`
8. Troubleshooting
""",
        ),
        (
            "md",
            """### Step 1 — `filenames` and `headless`

`filenames` must list movies to load (CLI default pattern: `["0.avi"]`). **`headless=True`** skips interactive crop and curation GUIs — use **`analysis_parameters.csv`** for `crop_coords` when headless.
""",
        ),
        (
            "code",
            """print("filenames:", filenames, "headless:", headless)
""",
        ),
        (
            "md",
            """### Step 2 — Create data manager (`MiniscopeDataManager.create`)

`ONIX` vs `UCLA`-style acquisition is inferred from your data layout.
""",
        ),
        (
            "code",
            """from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager

dm = MiniscopeDataManager.create(
    line_num=line_num,
    project_path=project_path,
    data_path=data_path,
    filenames=filenames,
    auto_import_data=True,
)
print("frame rate:", getattr(dm, "fr", None))
""",
        ),
        (
            "md",
            """### Step 3 — Preprocess (`MiniscopePreprocessor`)

Crop coordinates come from **`analysis_parameters.csv`** / GUI when `crop_coords` is None. Below mirrors pipeline defaults you can tune.
""",
        ),
        (
            "code",
            """from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor
from aceneurotools.shared.misc_functions import get_coords_dict_from_analysis_params

coords_dict, crop_job_name = get_coords_dict_from_analysis_params(dm)
pre = MiniscopePreprocessor(dm)
dm = pre.preprocess_calcium_movie(
    coords_dict,
    crop=True,
    detrend_method="median",
    df_over_f=False,
    crop_job_name_for_file=crop_job_name,
    secs_window=5.0,
    quantile_min=8.0,
    df_over_f_method="delta_f_over_sqrt_f",
    headless=headless,
)
""",
        ),
        (
            "md",
            """### Step 4 — Process (`MiniscopeProcessor`)

Heavy steps: motion correction (optional) and CNMF-E. For a quick notebook test, set `run_CNMFE=False` (you will not get spatial components until CNMF-E runs).
""",
        ),
        (
            "code",
            """from aceneurotools.miniscope.miniscope_processor import MiniscopeProcessor

proc = MiniscopeProcessor(dm)
dm = proc.process_calcium_movie(
    parallel=False,
    n_processes=4,
    apply_motion_correction=False,
    inspect_motion_correction=False,
    plot_params=False,
    run_CNMFE=True,
    save_estimates=True,
    save_CNMFE_estimates_filename="estimates.hdf5",
    save_CNMFE_params=False,
)
""",
        ),
        (
            "md",
            """### Step 5 — Postprocess (`MiniscopePostprocessor`)

Runs only if `dm.CNMFE_obj` is not None. With `headless=True`, component-removal GUI is skipped (see `MiniscopePipeline.run`).
""",
        ),
        (
            "code",
            """from aceneurotools.miniscope.miniscope_postprocessor import MiniscopePostprocessor

if dm.CNMFE_obj is None:
    print("Skip postprocess: CNMF-E object missing (run Step 4 with run_CNMFE=True).")
else:
    post = MiniscopePostprocessor(dm)
    dm = post.postprocess_calcium_movie(
        remove_components_with_gui=False,
        find_calcium_events=True,
        derivative_for_estimates="first",
        event_height=5.0,
        compute_miniscope_phase=True,
        filter_miniscope_data=True,
        n=2,
        cut=[0.1, 1.5],
        ftype="butter",
        btype="bandpass",
        inline=False,
        compute_miniscope_spectrogram=False,
        window_length=30.0,
        window_step=3.0,
        freq_lims=[0, 15],
        time_bandwidth=2.0,
    )
""",
        ),
        (
            "md",
            """### Step 6 — Inspect results

Common fields after a full run: `Cn`, `ca_events_idx`, `miniscope_phases`.
""",
        ),
        (
            "code",
            """import matplotlib.pyplot as plt

if getattr(dm, "Cn", None) is not None:
    plt.figure(figsize=(6, 6))
    plt.imshow(dm.Cn, cmap="gray")
    plt.title("Correlation image Cn")
    plt.show()
else:
    print("No Cn yet — complete CNMF-E and postprocessing.")
""",
        ),
        (
            "md",
            """### Step 7 — One-shot `MiniscopePipeline.run`

Equivalent to chaining the three stages with shared kwargs.
""",
        ),
        (
            "code",
            """from aceneurotools.pipelines.miniscope import MiniscopePipeline

pipe = MiniscopePipeline()
pipe.run(
    line_num=line_num,
    project_path=project_path,
    data_path=data_path,
    filenames=filenames,
    headless=headless,
)
dm2 = pipe.miniscope_data_manager
print("Cn:", getattr(dm2, "Cn", None) is not None)
""",
        ),
        (
            "md",
            """## Troubleshooting

- **Empty `filenames`:** Always pass movie names (e.g. `["0.avi"]`); defaults in code are empty.
- **Headless:** GUIs for crop and curation are disabled — provide `crop_coords` or pre-filled `analysis_parameters.csv`.
- **Memory:** CNMF-E is heavy; reduce `n_processes`, crop harder, or shorten movies for learning runs.
""",
        ),
    ]


def multimodal_cells() -> list[tuple[str, str]]:
    return [
        (
            "md",
            """# ACE-NeuroTools: Multimodal alignment tutorial

Align **ephys** and **miniscope** for one `line_num` using TTL-based sync, then optional **phase-at-calcium-event** histograms.

Requires a session whose **metadata row** points to **both** modalities under `data_path`.
""",
        ),
        (
            "md",
            """## Project layout

Same as single-modality tutorials:

- **`project_path`**: `experiments.csv`, **`analysis_parameters.csv`**
- **`data_path`**: raw trees for **both** ephys and calcium for this line

Pick **`line_num`** only for recordings that actually have both streams populated in `experiments.csv`.
""",
        ),
        (
            "code",
            """from pathlib import Path

project_path = Path("/path/to/your/project")
data_path = Path("/path/to/your/raw_data")
line_num = 97
channel_name = "PFCLFPvsCBEEG"
miniscope_filenames = ["0.avi"]

for label, p in ("experiments.csv", project_path / "experiments.csv"), (
    "analysis_parameters.csv",
    project_path / "analysis_parameters.csv",
):
    if not p.is_file():
        raise FileNotFoundError(f"Missing {label} at {p}")

from aceneurotools.shared.experiment_data_manager import ExperimentDataManager

edm = ExperimentDataManager(line_num, project_path=project_path, data_path=data_path)
print("ephys dir:", edm.get_ephys_directory())
print("calcium dir:", edm.metadata.get("calcium imaging directory") if edm.metadata else None)
""",
        ),
        (
            "md",
            """## Table of contents

1. One-shot `MultimodalPipeline.run`
2. Inspect sub-pipelines and alignment outputs on the API object
3. Phase histograms (`ca_events=True`)
4. Concept map (what ran internally)
5. Troubleshooting
""",
        ),
        (
            "md",
            """### Step 1 — Full multimodal run

This runs ephys, then miniscope, then `sync_neuralynx_miniscope_timestamps`, index finding, and (if `ca_events=True`) phase histograms. Use **`headless=True`** on servers.
""",
        ),
        (
            "code",
            """from aceneurotools.pipelines.multimodal import MultimodalPipeline

mm = MultimodalPipeline()
mm.run(
    line_num=line_num,
    project_path=project_path,
    data_path=data_path,
    channel_name=channel_name,
    miniscope_filenames=miniscope_filenames,
    ca_events=True,
    headless=True,
    run_CNMFE=True,
    remove_components_with_gui=False,
    inspect_motion_correction=False,
)
print("Alignment timestamps shape:", None if mm.t_ca_im is None else getattr(mm.t_ca_im, "shape", len(mm.t_ca_im)))
""",
        ),
        (
            "md",
            """### Step 2 — Outputs on `MultimodalPipeline`

After `run()`, use **`mm.ephys_pipeline`** / **`mm.miniscope_pipeline`** for modality-specific state, and the alignment fields below for cross-modal analysis.
""",
        ),
        (
            "code",
            """print("ephys channel object:", mm.ephys_pipeline.ephys_data_manager.get_channel(channel_name))
print("ephys_idx_all_TTL_events:", mm.ephys_idx_all_TTL_events is not None)
print("ephys_idx_ca_events:", mm.ephys_idx_ca_events is not None)
print("ca_frame_num_of_ephys_idx:", mm.ca_frame_num_of_ephys_idx is not None)
""",
        ),
        (
            "md",
            """### Step 3 — Phase histograms (ephys vs miniscope bands)

Populated when `ca_events=True` and event detection succeeded. Uses **`mm.phase_hist_ephys`** / **`mm.phase_bin_edges_ephys`** (and miniscope counterparts).
""",
        ),
        (
            "code",
            """import matplotlib.pyplot as plt
import numpy as np

if mm.phase_hist_ephys is not None and mm.phase_bin_edges_ephys is not None:
    centers = (mm.phase_bin_edges_ephys[:-1] + mm.phase_bin_edges_ephys[1:]) / 2.0
    plt.figure(figsize=(8, 4))
    plt.bar(centers, mm.phase_hist_ephys, width=np.diff(mm.phase_bin_edges_ephys).mean(), alpha=0.7, label="ephys phase @ CA")
    plt.xlabel("Phase (rad)")
    plt.legend()
    plt.title("Calcium events vs ephys phase")
    plt.show()
else:
    print("No ephys phase histogram (enable ca_events and ensure CNMF-E + events ran).")

if mm.phase_hist_miniscope is not None and mm.phase_bin_edges_miniscope is not None:
    centers = (mm.phase_bin_edges_miniscope[:-1] + mm.phase_bin_edges_miniscope[1:]) / 2.0
    plt.figure(figsize=(8, 4))
    plt.bar(centers, mm.phase_hist_miniscope, width=np.diff(mm.phase_bin_edges_miniscope).mean(), alpha=0.7, color="C1", label="miniscope phase @ CA")
    plt.xlabel("Phase (rad)")
    plt.legend()
    plt.show()
""",
        ),
        (
            "md",
            """## Internals (same as `MultimodalPipeline.run`)

1. `EphysPipeline.run` → `MiniscopePipeline.run`
2. `sync_neuralynx_miniscope_timestamps` — `delete_TTLs`, `fix_TTL_gaps`, `only_experiment_events`
3. `find_ephys_idx_of_TTL_events`, optional `find_ca_movie_frame_num_of_ephys_idx`
4. `ephys_phase_ca_events` / `miniscope_phase_ca_events` → `phase_ca_events_histogram`

Optional movie export: `create_ca_ephys_movie` in `aceneurotools.multimodal.calcium_ephys_visualizer` (resource-heavy).

## Troubleshooting

- **Wrong directory:** Same CSV rules as other tutorials — if `project_path` is wrong, both modalities fail metadata lookup.
- **No histograms:** Need `ca_events=True`, detected `ca_events_idx`, and phases computed on the miniscope side.
- **CNMF-E in multimodal:** Turning off `run_CNMFE` prevents downstream postprocess-dependent steps.
""",
        ),
    ]


def main() -> None:
    save("ephys_pipeline_tutorial.ipynb", make_nb(ephys_cells()))
    save("miniscope_pipeline_tutorial.ipynb", make_nb(miniscope_cells()))
    save("multimodal_alignment_tutorial.ipynb", make_nb(multimodal_cells()))


if __name__ == "__main__":
    main()
