---
status: accepted
---

# Keep CSV settings authoritative until EVC has an application consumer

The experiment GUI and CLI currently read and write `experiments.csv` and
`analysis_parameters.csv`. CSVs are the source of truth. Both interfaces use
shared parameter parsing and pipeline defaults; GUI runs retain frozen copies
of the input CSVs. No GUI route reads or writes EVC configuration.

Canonical schema-validated JSON documents remain a proposed migration direction.
EVC is parked on a separate branch and is not part of this PR series. Before
adopting it, a separate PR must connect the GUI or analysis CLI to its read/write
API, migrate CSV settings without loss, define compatibility writeback, and
update this ADR to describe the implemented source of truth.
