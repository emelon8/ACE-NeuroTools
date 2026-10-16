---
status: accepted
---

# Share application capabilities between GUI and CLI

The September 15 Comenius meeting agreed to preserve CLI access and pursue feature parity while making the GUI the primary human workflow. Both interfaces should use common application operations so that settings, validation, execution, and scientific behavior do not diverge. This accepts an architectural direction, not a particular framework, API transport, subprocess protocol, or migration schedule; those choices remain open in the decision register.

The CLI and GUI now import `pipeline_defaults()` from
`aceneurotools.shared.pipeline_defaults`. Each call returns an independent copy.
GUI option discovery uses the same module's `pipeline_keys()` and never reads or
parses pipeline source text. CSV settings, including canonical `crop_coords` and
legacy crop tuples, are interpreted in `shared.config_utils`; there is no
GUI-only coordinate injection. GUI headless execution uses the shared headless
policy. Direct Python callers can still pass explicit run arguments.
