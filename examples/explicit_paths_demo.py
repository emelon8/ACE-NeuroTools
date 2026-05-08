#!/usr/bin/env python3
"""Demonstrate ACE-NeuroTools's explicit-path API (no hidden env vars or .env).

Replace the placeholder paths with your ``project_path`` (directory containing
``experiments.csv`` and ``analysis_parameters.csv``) and ``data_path`` (raw
recordings root). See the user guide: https://aceneurotools.readthedocs.io/en/latest/getting_started/
"""

from __future__ import annotations

from pathlib import Path

from aceneurotools.pipelines.ephys import EphysPipeline
from aceneurotools.pipelines.miniscope import MiniscopePipeline
from aceneurotools.pipelines.multimodal import MultimodalPipeline

# --- edit these ---
PROJECT = Path("/path/to/project")
DATA = Path("/path/to/raw_data")
LINE_MINISCOPE = 96
LINE_EPHYS = 96
LINE_MULTIMODAL = 97


def main() -> None:
    """Run each pipeline once with explicit paths (comment out what you do not need)."""
    # MiniscopePipeline().run(
    #     line_num=LINE_MINISCOPE,
    #     project_path=PROJECT,
    #     data_path=DATA,
    #     headless=True,
    # )
    # EphysPipeline().run(
    #     line_num=LINE_EPHYS,
    #     project_path=PROJECT,
    #     data_path=DATA,
    #     headless=True,
    # )
    # MultimodalPipeline().run(
    #     line_num=LINE_MULTIMODAL,
    #     project_path=PROJECT,
    #     data_path=DATA,
    #     headless=True,
    # )
    print(
        "Uncomment the pipeline(s) you want to run and set PROJECT / DATA. "
        "See docstring at top of this file."
    )


if __name__ == "__main__":
    main()
