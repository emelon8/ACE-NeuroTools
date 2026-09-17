"""Synthetic, reproducible demonstration using the actual EVC backend."""

import json
import math
from pathlib import Path

from aceneurotools.evc.api import ExperimentVersionControl, write_manifest


def create_demo(directory: Path) -> list[Path]:
    directory = directory.expanduser().resolve()
    marker = directory / ".ace-demo"
    if directory.exists() and any(directory.iterdir()) and not marker.exists():
        raise ValueError("Demo directory is not empty and was not created by this workbench.")
    directory.mkdir(parents=True, exist_ok=True)
    marker.write_text("Synthetic ACENeuroTools example. No acquired research data.\n")
    roots = []
    for number, name in enumerate(("01-calcium-demo", "02-paired-recording-demo"), 1):
        root = directory / name
        roots.append(root)
        if (root / ".evc").is_dir():
            continue
        evc = ExperimentVersionControl.init(root, workspace=True)
        experiment = {
            "schema": "aceneuro-experiment-v1", "line_number": number,
            "id": f"DEMO-{number:02d}", "date": "260916",
            "calcium_imaging_directory": None, "ephys_directory": None,
            "comments": "SYNTHETIC EXAMPLE — no acquired recordings or scientific conclusions.",
            "_csv": {"columns": [], "raw": {}},
        }
        analysis = {
            "schema": "aceneuro-analysis-cnmfe-v1", "line_number": number,
            "params": {"decay_time": 0.4, "gSig": [3, 3], "gSiz": [13, 13],
                       "min_corr": 0.8, "min_pnr": 10, "min_SNR": 2.5,
                       "merge_thr": 0.8, "pw_rigid": True, "max_shifts": [6, 6],
                       "method_init": "corr_pnr", "method_deconvolution": "oasis",
                       "tsub": 2, "ssub": 1, "use_cnn": False},
            "_csv": {"columns": [], "raw": {}},
        }
        (root / "parameters/experiment.json").write_text(json.dumps(experiment, indent=2) + "\n")
        config = root / "parameters/analysis.cnmfe.json"
        config.write_text(json.dumps(analysis, indent=2) + "\n")
        evc.record("Initialize synthetic example parameters", author="ACENeuroTools example fixture", author_time=1789560000)
        analysis["params"]["min_corr"] = 0.85
        config.write_text(json.dumps(analysis, indent=2) + "\n")
        revision = evc.record("Adjust correlation threshold to 0.85", author="ACENeuroTools example fixture", author_time=1789560600)
        artifacts = root / "artifacts/synthetic-traces"
        artifacts.mkdir(parents=True)
        lines = ["time_s,cell_01,cell_02,cell_03"]
        for index in range(400):
            t = index / 20
            values = [0.06 * math.sin(t * (k + 1) * 2) + sum(
                math.exp(-(t - peak) / (0.6 + k * 0.2)) if t >= peak else 0
                for peak in (2.4 + k, 7.2 + k * 0.4, 13.1 + k, 17.8 - k)
            ) for k in range(3)]
            lines.append(f"{t:.2f}," + ",".join(f"{v:.5f}" for v in values))
        (artifacts / "synthetic-traces.csv").write_text("\n".join(lines) + "\n")
        write_manifest(artifacts, pipeline="synthetic-example (not a scientific run)", revision=revision,
                       manifest_dir=root / "results/synthetic-traces")
        evc.record("Register synthetic trace artifacts and provenance", author="ACENeuroTools example fixture", author_time=1789561200)
        evc.comment(revision, "Example only. Edit min_corr, save, and record a revision to explore EVC.")
    return roots
