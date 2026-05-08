# API Reference

This section contains the automatically generated documentation for the ACE-NeuroTools codebase. It is extracted directly from the Python docstrings using `mkdocstrings`.

ACE-NeuroTools is organized into several key modules:

- **[Pipelines](pipelines.md)**: High-level entry points for standard workflows.
- **[Miniscope](miniscope.md)**: Tools for calcium imaging data extraction and processing.
- **[Ephys](ephys.md)**: Multi-channel electrophysiology data management and signal processing.
- **[Multimodal](multimodal.md)**: Cross-modal alignment and the multimodal pipeline API.
- **[Shared](shared.md)**: Core utilities for configuration, paths, and data managers.

## Package Structure

```text
aceneurotools/
├── ephys/        # Electrophysiology pipeline & managers
├── miniscope/    # Calcium imaging pipeline & processing
├── multimodal/   # Cross-modal alignment & analysis
├── pipelines/    # High-level CLI & API entry points
└── shared/       # Common utilities & base classes
```
