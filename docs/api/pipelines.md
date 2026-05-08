# Pipelines API

This section details the high-level entry points for running the analysis workflows.

**How to pass arguments:** each class exposes `run(...)`. Pass **keyword arguments** matching the parameters documented below. Typical flows:

1. Call `run(line_num=..., project_path=..., data_path=..., **other_kwargs)` from Python.
2. Optionally load per-line defaults from `analysis_parameters.csv` with `load_analysis_params` and merge: `run(**{**csv_params, "line_num": n, ...})`.
3. CLI modules (`python -m aceneurotools.pipelines.*`) only expose a few flags; they merge CSV + defaults internally — see [Getting started](../getting_started.md) §3a.

## Miniscope Pipeline
::: aceneurotools.pipelines.miniscope.MiniscopePipeline

## Ephys Pipeline
::: aceneurotools.pipelines.ephys.EphysPipeline

## Multimodal Pipeline
::: aceneurotools.pipelines.multimodal.MultimodalPipeline
