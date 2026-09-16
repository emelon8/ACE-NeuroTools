# API Reference

This section contains the automatically generated documentation for the ACE-NeuroTools codebase. It is extracted directly from the Python docstrings using `mkdocstrings`.

ACE-NeuroTools is organized into several key modules:

- **[Pipelines](pipelines.md)**: High-level entry points for standard workflows.
- **[Miniscope](miniscope.md)**: Tools for calcium imaging data extraction and processing.
- **[Ephys](ephys.md)**: Multi-channel electrophysiology data management and signal processing.
- **[Multimodal](multimodal.md)**: Miniscope ↔ ephys alignment and the multimodal pipeline API.
- **[Stats](stats.md)**: Statistical engines (coherence, scatter) and the modular analysis toolbox.
- **[Config](config.md)**: Loading of lab_config.json, stats_config.json, and analysis_parameters.csv.
- **[Shared](shared.md)**: Core utilities: CSV, paths, filtering, plotting, data managers.

## Package Structure

```text
aceneurotools/
├── config/       # Configuration loading (lab_config, stats_config, analysis params)
├── ephys/        # Electrophysiology pipeline & managers
├── miniscope/    # Calcium imaging pipeline & processing
├── multimodal/   # Miniscope ↔ ephys alignment & phase-locking
├── stats/        # Statistical engines & modular analysis toolbox
├── pipelines/    # High-level CLI & API entry points
└── shared/       # Common utilities & base classes
```
