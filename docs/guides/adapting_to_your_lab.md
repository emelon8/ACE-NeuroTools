# Adapting ACE-NeuroTools to your lab

ACE-NeuroTools is built so that **different acquisition setups** can be supported without rewriting the whole pipeline. This page explains what is **configuration-only**, what requires **small code extensions**, and where to plug them in.

---

## Design goal

- **Same pipelines** (`EphysPipeline`, `MiniscopePipeline`, `MultimodalPipeline`) for interactive and batch runs.
- **Lab-specific details** isolated in **data managers** and **metadata**, not scattered through processors.
- **Explicit paths and parameters** (`project_path`, `data_path`, `analysis_parameters.csv`) so runs are reproducible and shareable across groups.

---

## Step 1: Try configuration first

Many differences between labs are handled without changing Python code:

| What varies | Where to set it |
|-------------|-----------------|
| Raw data layout under a shared root | `data_path` + columns in `experiments.csv` (e.g. **ephys directory**, **calcium imaging directory**) |
| Per-session analysis choices | `analysis_parameters.csv` and kwargs to `run()` (see [Getting started](../getting_started.md) §3a) |
| Imaging frame rate and file layout | Miniscope **metadata** (e.g. `frameRate`, paths to movies). TTL gap logic scales with `frameRate` when present (see [Multimodal integration](multimodal.md#ttl-synchronization-and-gap-detection)) |
| Headless / cluster runs | `headless=True` and the same kwargs you would use locally |

If your files match an existing **on-disk pattern** already recognized by the library, the factory will pick the right manager automatically (see Step 2).

---

## Step 2: How new systems plug in (code)

The library uses **abstract base classes** and a **registry + factory** pattern:

### Miniscope: `MiniscopeDataManager`

- **Subclass** `MiniscopeDataManager` for your miniscope export format (see [Miniscope API](../api/miniscope.md) and the `aceneurotools.miniscope` package).
- Implement **`can_handle(directory)`** so the factory chooses your class when it sees your folder layout.
- Implement **`_get_miniscope_metadata`**, **`_get_timestamps`**, **`_get_movies`**, and (as needed) **`sync_timestamps`** — the exact split depends on whether you rely on **TTL sync**, **native hardware clocks**, or something else.
- Registration happens automatically when the subclass is defined (`__init_subclass__` adds it to the registry).
- Entry point: **`MiniscopeDataManager.create(...)`** walks registered subclasses until `can_handle` returns true.

Shipped examples you can copy from include **UCLA V3** (`UCLADataManager`) and **UCLA V4 / ONIX-style** (`OnixMiniscopeDataManager`).

### Ephys: `EphysDataManager`

- **Subclass** `EphysDataManager` for your acquisition system’s files (see [Ephys API](../api/ephys.md) and the `aceneurotools.ephys` package).
- Implement **`can_handle(directory)`** and the import path for your format (`import_ephys_block`, `process_ephys_block_to_channels`, etc., as required by your backend).
- For **multimodal TTL alignment**, implement **`get_sync_timestamps(channel_name)`** so it returns **frame-acquisition pulse times in the same time base** as the rest of the ephys stream (see existing **Neuralynx** and **RHS2116** managers).

Entry point: **`EphysDataManager.create(ephys_directory=...)`**.

---

## Step 3: Multimodal alignment contract

For **ephys + miniscope** runs, your managers should agree on:

1. **Time base** — Calcium frame times and ephys `channel.time_vector` must be comparable (e.g. both in seconds from recording start, or both aligned to a common clock).
2. **Sync events** — `get_sync_timestamps` should return times of **pulses that correspond to frames** (or your documented convention), so gap detection and index mapping stay meaningful.
3. **Frame rate in metadata** — Supply **`frameRate`** where possible so TTL gap thresholds stay **rate-adaptive** rather than assuming a fixed Hz.

Details and defaults are documented under [TTL synchronization and gap detection](multimodal.md#ttl-synchronization-and-gap-detection).

---

## Step 4: Validate your adapter

- Use **`pytest`** with small fixtures under your miniscope/ephys directories, or extend the project’s sample recording patterns (see **Development and testing** in the repository README).
- Run a **short headless** `MultimodalPipeline.run(...)` on one session and inspect `t_ca_im`, `low_confidence_periods`, and channel alignment before scaling to full cohorts.

---

## Summary

| Approach | Best for |
|----------|-----------|
| CSV + metadata + kwargs only | Same code paths; different paths, filters, and session notes |
| New `MiniscopeDataManager` / `EphysDataManager` subclass | New folder layouts, file formats, or acquisition hardware |
| Adjust `sync_timestamps` / `get_sync_timestamps` | New sync strategies while keeping the same high-level multimodal API |

For modality-specific usage, see the [Miniscope](miniscope.md), [Ephys](ephys.md), and [Multimodal](multimodal.md) guides.
