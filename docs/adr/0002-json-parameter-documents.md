---
status: accepted
---

# Store experiment parameters as schema-validated canonical JSON documents

Decision D05 (2026-09-16, owner Elijah Keldsen) makes small canonical JSON documents — one per concern, validated by versioned JSON Schema files and tracked by experiment version control — the authoritative saved experiment configuration. The GUI edits them through schema-driven forms and agents through a machine-readable CLI, so all frontends resolve the same effective settings (extends ADR 0001). Existing CSVs are imported non-destructively (the first extract becomes the experiment's root revision) and written back for compatibility while CSV-reading pipelines migrate; unknown lab-specific columns are preserved verbatim in an explicit passthrough section rather than silently dropped. This accepts the storage format and migration direction, not a GUI framework, schema library, or migration schedule; those remain open in the decision register (D02, D03, D06).
