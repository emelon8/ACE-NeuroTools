---
status: accepted
---

# Share application capabilities between GUI and CLI

Preserve command-line access while providing a GUI for interactive use. Both
interfaces should use common application operations so that settings, validation,
execution, and scientific behavior do not diverge. This decision establishes the
shared application boundary; it does not prescribe a framework, API transport,
subprocess protocol, or migration schedule.

The CLI and GUI now import `pipeline_defaults()` from
`aceneurotools.shared.pipeline_defaults`. Each call returns an independent copy.
GUI option discovery uses the same module's `pipeline_keys()` and never reads or
parses pipeline source text. CSV settings, including canonical `crop_coords` and
legacy crop tuples, are interpreted in `shared.config_utils`; there is no
GUI-only coordinate injection. GUI headless execution uses the shared headless
policy. Direct Python callers can still pass explicit run arguments.
