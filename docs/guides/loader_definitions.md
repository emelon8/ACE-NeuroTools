# Ephys loader definitions

Most of what an ephys loader does is configuration. It decides:

- how to recognise a recording folder
- which reader opens the folder
- where sample times come from
- how channels are named
- how the recording is synchronised with imaging

A **loader definition** writes these choices down as a JSON file, so you can
describe your acquisition system without writing a Python subclass of
`EphysDataManager`.

```text
<project>/
├── experiments.csv
├── analysis_parameters.csv
└── loaders/
    └── my-rig.json        ← one definition per file; "name" must be "my-rig"
```

!!! info "What works today, and what is proposed"
    **Available now:** the `ace-loader/1` format, validation, folder
    detection, file lookup by name, a JSON Schema, and the
    `ace-neuro loaders` commands. None of these read signal data.

    **Proposed in ADR 0008 (not implemented):** loading channels from a
    definition inside the ephys pipelines. The ephys data managers are core
    code, so a maintainer must approve that change. Until it is merged,
    `EphysDataManager.create()` uses only the built-in Python loaders, and
    project definitions have no effect on analyses. The proposal also covers:

    - **Choosing a loader.** If several loaders match a folder and
      `experiments.csv` does not name one, loading stops with an error that
      lists the matches. A new `ephys loader` column in `experiments.csv`
      selects one explicitly. The column does not exist yet.
    - **Name clashes with built-in loaders.** Whether project definitions may
      reuse built-in loader names such as `neuralynx` is still to be decided.

## Commands

```sh
# List the built-in loaders and the definitions in <project>/loaders
ace-neuro loaders list --project-path /path/to/project

# Check definition files; prints "file: path: message" per problem, exits 1 on any
ace-neuro loaders validate /path/to/project/loaders/my-rig.json

# Which built-in loaders and project definitions recognise a recording folder?
ace-neuro loaders detect /path/to/recording --project-path /path/to/project
```

`--project-path` defaults to the current directory. `detect` exits with 1 when
nothing matches. When several built-in loaders match, it shows which one
`EphysDataManager.create()` uses today: the first in registration order.

## Portability rules

Definitions are copied into run plans and may run on other computers, so they
must not contain machine paths:

- **Patterns are relative globs under the recording folder.** Use `/` as the
  separator. A pattern cannot be absolute or start with `~` or a drive letter
  (`C:`). It cannot contain backslashes, empty segments, `.` or `..`
  segments. `**` must be a whole segment, as in `sub/**/*.ncs`.
- **Reader arguments are JSON scalars** (string, number, `true`/`false`,
  `null`). A string argument cannot look like a machine path.
- **The recording path is never written in a definition.** The loader passes
  it to the reader.
- **Strict JSON.** Unknown keys, duplicate keys and `NaN`/`Infinity` are
  errors, so typos do not go unnoticed. A different `schema` version, such as
  `ace-loader/2`, is reported as unsupported.

## Format reference (`ace-loader/1`)

### Top level

| Key | Required | Meaning |
|-----|----------|---------|
| `schema` | yes | Always `"ace-loader/1"`. |
| `name` | yes | Kebab-case identifier (`my-rig`), at most 64 characters. Must equal the file name without `.json`. |
| `label` | yes | Human-readable name shown in lists. |
| `description` | no | Free text. |
| `modality` | yes | `"ephys"`. Calcium imaging is not covered by this version. |
| `detect` | yes | How to recognise a recording folder. |
| `reader` | yes | What opens the recording. |
| `time` | yes | Where sample times come from. |
| `channels` | yes | Channel names and default selection. |
| `sync` | yes | How to synchronise with other recordings. |

### `detect`

A folder matches when every `all_of` pattern finds at least one entry, at least
one `any_of` pattern finds one (if `any_of` is given), and no `none_of` pattern
finds anything. At least one of `all_of` and `any_of` must be non-empty.
Entries can be files or folders, which is the same test the built-in
`can_handle` methods use. Detection never opens a file.

```json
"detect": {"all_of": ["*.rhd"], "none_of": ["*.nev"]}
```

### `reader.files`

`files` is an ordered list of rules that find the files the reader needs, by
name only. Each rule names a **role** that other sections refer to.

| Key | Default | Meaning |
|-----|---------|---------|
| `role` | — | Name for this file (`ac`, `clock`, `events`), lowercase with `_`. |
| `pattern` | — | Relative glob. May contain `{variable}` placeholders captured by an *earlier* rule. Captured values are inserted literally, so glob characters in them are escaped. |
| `exclude_names` | `[]` | Globs matched case-sensitively against the file name, for example `"*miniscope*"`. |
| `exclude_dirs` | `[]` | Folder names. A file inside such a folder (below the recording folder) is skipped. |
| `pick` | `"only"` | How to choose among several matches. See below. |
| `required` | `true` | When `false`, a missing file is allowed. |
| `capture` | — | `{"variable", "split", "part"}`: store `stem.split(split)[part]` of the chosen file as `{variable}`. |

Only regular files are matched. `pick` values:

- `only`: exactly one match is expected. Several matches are an error.
- `first_listed`: the first match in the operating system's directory listing
  order. This order is not sorted and can differ between computers. It exists
  to reproduce loaders that already work this way.
- `oldest_modified`: the earliest modification time. Ties keep listing order.
- `first_sorted`: the first match by relative path.

### `reader` with `backend: "neo"`

| Key | Required | Meaning |
|-----|----------|---------|
| `io` | yes | A class name from `neo.io.iolist`, for example `NeuralynxIO`, `IntanIO`, `OpenEphysBinaryIO`. Names are checked against neo's own list and are never imported from arbitrary strings. `PickleIO` and `NeurosharectypesIO` are refused because they can run arbitrary code. |
| `path_argument` | yes | The reader's path parameter, usually `dirname` or `filename`. Checked against the class signature. |
| `path_from` | yes | What to pass as the path argument: `{"source": "recording_folder"}`, `{"source": "file", "file": "<role>"}` or `{"source": "file_parent", "file": "<role>"}`. |
| `files` | no | File rules, as above. |
| `args` | no | Other constructor arguments, as JSON scalars. Names are checked against the class signature. A `mode` argument must be read-only (`r` or `ro`). |
| `read_block` | no | Arguments to `read_block()`, as JSON scalars, for example `{"signal_group_mode": "split-all"}`. |

A neo reader takes its times and channel names from neo, so it needs
`time.source: "reader"` and `channels.source: "reader"`.

### `reader` with `backend: "raw_binary"`

This backend reads an interleaved, sample-major binary file (all channels for
sample 0, then all channels for sample 1, and so on) with
`neo.rawio.RawBinarySignalRawIO`.

| Key | Default | Meaning |
|-----|---------|---------|
| `files` | — | File rules. Must contain the signal file. |
| `signal_file` | — | Role of the signal file. |
| `dtype` | — | Sample type on disk: `int8` … `uint64`, `float32`, `float64`. |
| `channel_count` | — | Number of interleaved channels. |
| `gain` | `1.0` | Scale factor, not zero. |
| `offset` | `0.0` | Added after scaling: `value = raw.astype(output_dtype) * gain + offset`. |
| `byte_offset` | `0` | Header bytes to skip. |
| `output_dtype` | `"float32"` | `float32` or `float64`. |

### `time`

| `source` | Keys | Meaning |
|----------|------|---------|
| `reader` | — | Times come from the neo reader. Only for `neo`. |
| `clock_file` | `clock_file` (role), `clock_dtype`, `ticks_per_second`, `effective_rate` | The clock file holds one tick count per sample. Seconds are `ticks / ticks_per_second`, computed in float64. `ticks_per_second` is a number, or `{"csv_file": "<role>", "column": N, "header_rows": 0}` to read it from a CSV file (0-based column). `effective_rate` is `{"method": "median_interval", "first_samples": N}`, which sets the channel sampling rate to `1 / median(diff(times[:N]))`. |
| `sample_index` | `sampling_rate_hz` | Times are `arange(n) / sampling_rate_hz`. |

The number of samples loaded is the smaller of the signal length and the clock
length.

### `channels`

| Key | Meaning |
|-----|---------|
| `source` | `reader` (neo names channels) or `template`. |
| `template` | Required for `template`. Must contain `{index}` (0-based), for example `"AMP_{index}"`. |
| `select_by_index` | `template` only. When `true`, a channel can also be requested by its index (`3` or `"3"`). |
| `default` | Which channels to load when the caller requests none: `all` or `none`. |

### `sync`

| `strategy` | Keys | Meaning |
|------------|------|---------|
| `event_labels` | `labels` | Sync times are the timestamps of reader events whose label exactly equals one of `labels`. Only for `neo`, because raw binary files have no events. |
| `digital_threshold` | `channel`, `threshold`, `edge` (`rising` by default, or `falling` or `both`) | Sync times are threshold crossings on a channel. |
| `shared_clock` | — | No sync pulses. The recording shares a hardware clock with the imaging system, and `get_sync_timestamps()` returns an empty array. |

## Examples: the built-in loaders

These two definitions are in the repository at `tests/data/loaders/`. Tests
check them against the built-in managers: detection gives the same result as
`can_handle`, the same files are found, the same sync events are selected,
and RHS2116 channels match bit for bit.

### Neuralynx

```json
--8<-- "tests/data/loaders/neuralynx.json"
```

- `detect` matches `NeuralynxDataManager.can_handle`: any `*.nev` file directly in
  the folder.
- The `events` rule reproduces the manager's file search. The manager searches
  the folder and its subfolders, skipping `saved_movies` folders, for files that
  start with `Events` and end in `.nev`, and it uses the oldest one. The reader
  receives the folder that contains that file.
- `channels.default: "none"`: the built-in manager loads only the channels
  you ask for.

### RHS2116

```json
--8<-- "tests/data/loaders/rhs2116.json"
```

- `detect` matches `RHS2116DataManager.can_handle`: any `*.raw` file. This is
  broad, because miniscope recordings that store `.raw` files also match. A
  new definition should use a stricter test, for example
  `"all_of": ["start-time_*.csv", "rhs2116pair-ac_*.raw"]`.
- The suffix after the last `_` of the `start-time_*.csv` name (ignoring
  files that contain `miniscope`) selects the `rhs2116pair-{clock,ac,dc}`
  files. All three must exist, although only `ac` and `clock` are read.
- `offset` is `-(32768 × 0.195)`, written out as `-6389.76`. That is the same
  float64 value the manager computes.
- `ticks_per_second` is column 1 of the start-time CSV (the acquisition clock
  rate).

### Known differences from the built-in code

Neither difference affects the shipped examples on normal recordings:

- `PathFinder`, which the Neuralynx manager uses, skips any file whose
  *absolute* path contains a `saved_movies` folder, including folders *above*
  the recording folder. `exclude_dirs` only looks below the recording folder.
- On Windows, `pathlib` globbing ignores case. `PathFinder`'s `Events`/`.nev`
  check does not.

## Python API

```python
from aceneurotools.shared.loader_definitions import (
    load_definition, load_project_definitions, definition_matches,
    matching_files, resolve_files, validate_definition, definition_json_schema,
)

definition = load_definition("loaders/my-rig.json")          # raises DefinitionError
problems = validate_definition({"schema": "ace-loader/1"})   # never raises
definitions, bad_files = load_project_definitions("/path/to/project")
definition_matches(definition, "/path/to/recording")         # filenames only
resolve_files(definition, "/path/to/recording").files        # {"role": Path}
schema = definition_json_schema()                             # draft 2020-12
```

`definition_json_schema()` describes the structure, for editors and form
builders. Some rules depend on context, so only `validate_definition` checks
them:

- neo IO names and their arguments
- references to roles and placeholders
- which backend, time and channel settings can be combined
- machine paths inside reader arguments
- the file-name rule

Tests keep the schema and the validator in agreement.
