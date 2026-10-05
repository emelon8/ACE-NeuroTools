# Experiment GUI: source findings

Observed during project loading and CSV editing, October 3, 2026.
No code in `src` was modified. These issues require explicit permission before
any source fix. The bundled files load 118 experiments and 114 parameter records;
all 118 metadata records can be inspected by the existing reader.

The bundled CSVs also have five metadata rows with no settings record (`114`,
`115`, `116`, `117`, and `Example`) and one settings row whose `line number` is
descriptive text rather than a matching experiment. These are displayed as file
content issues; the viewer preserves them and reports the unmatched records.

## Missing parameter row does not use the documented fallback

[`ExperimentDataManager.import_analysis_parameters`](../../src/aceneurotools/shared/experiment_data_manager.py#L118)
documents an empty settings dictionary when an experiment number is absent.
However, its call to
[`CSVWorker.csv_row_to_dict`](../../src/aceneurotools/shared/csv_worker.py#L41)
raises `ValueError` for an absent number. The manager only checks for a `None`
return, so that exception bypasses the fallback.

Reproduction: load a metadata record whose `line number` does not occur in an
otherwise valid `analysis_parameters.csv`. Calling `import_analysis_parameters`
raises instead of assigning `{}`. The bundled CSVs have unmatched experiment
numbers, so a future GUI run adapter must account for this before enabling runs.
The viewer shows missing settings explicitly and does not invoke this manager.

## Zero-padded experiment numbers cannot match the existing reader

Reproduction with a small fixture:

```csv
line number,id
001,R1
```

`CSVWorker.csv_row_to_dict(path, "001")` raises “not found”: pandas infers the
column as an integer, and string conversion yields `"1"` rather than `"001"`.
This is covered by the GUI test. The viewer retains the raw `001` identity and
shows the reader error alongside the intact record. The bundled project did
not encounter this error.

## Boundary decisions

The existing reader loads one selected experiment and converts its types. The
GUI adds whole-table enumeration/validation, labeled editors, and a local browser
adapter, then reuses that reader for the optional interpreted view. Raw fields are kept
as text so exact IDs, `NA`, dates, blanks, and additional columns remain visible.

Settings are matched by exact `line number`. Missing files/rows are distinct from
invalid files. The GUI never silently repairs a malformed file or substitutes
defaults. Explicit saves reuse `update_csv_cell` and `append_row_csv` on a temporary
CSV, validate it, back up the original, and atomically replace the selected file.
Unknown columns and other records are retained. Box links are constructed only
from numeric folder IDs, without claiming authentication or recording availability.
Execution and scientific defaults remain outside this slice.

## The parameter template example has a missing cell

[`analysis_parameters_template.csv`](../../src/aceneurotools/shared/metadata_templates/analysis_parameters_template.csv)
has 53 headers and 52 fields in its example row. Loading that example through the
existing strict CSV reader raises a malformed-CSV error. This was encountered in
the new missing-file tests; the template was not changed.

For a missing settings file, the GUI reads only the template header and appends
the user's explicitly saved row with blank unspecified values. This reuses the
schema without importing its broken example or inventing defaults.
