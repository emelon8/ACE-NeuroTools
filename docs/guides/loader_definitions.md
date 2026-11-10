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
    - **Name clashes with built-in loaders.** For now, project definitions
      cannot use built-in loader names such as `neuralynx` or `rhs2116`.
      `ace-neuro loaders` and the workbench both refuse them. The proposal may
      relax this once a loader can be chosen explicitly.

    **To analyse recordings from a new system today**, write a
    [Python loader](#analyse-recordings-now-a-python-loader). You can write
    the definition as well, so it is ready when ADR 0008 is accepted.

## Add a recording system ACE doesn't read

ACE reads Neuralynx and RHS2116/ONIX recordings out of the box. For anything
else, follow these steps.

### Choose a route

| Your situation | What to do |
|----------------|------------|
| `ace-neuro loaders detect` names a built-in loader for your folder ([step 1](#step-1-check-whether-ace-already-reads-it)) | Nothing. ACE already reads it. |
| [neo](https://neo.readthedocs.io/en/latest/iolist.html) can open your format, or each recording is one interleaved binary file | Write a **loader definition** (steps 2 to 6). Today it is checked and recognised; analyses use it once ADR 0008 is accepted. To analyse recordings now, also write a Python loader. |
| Anything else: several files per channel, custom headers, compression, a format neo cannot read | Write a [Python loader](#analyse-recordings-now-a-python-loader). |

### Step 1: Check whether ACE already reads it

Point `detect` at one recording folder (the folder you would put in the
`ephys directory` column of `experiments.csv`):

```sh
ace-neuro loaders detect /path/to/recordings/rat01-day1 --project-path /path/to/my-project
```

If a built-in loader is listed under "Built-in loaders whose can_handle()
matches", ACE can already read the folder and you can stop here. If both
lists say `(none)`, continue.

### Step 2: Look at your recording folder

Before writing anything, answer four questions about one recording folder:

1. **Which file names only this system produces?** An extension such as
   `.rhd` or `.dat`, or a fixed name such as `settings.xml`. These become
   the `detect` patterns. Pick names that other systems' folders do not
   contain, or exclude those with `none_of`.
2. **Which file holds the signals, and what opens it?** Look up your format
   in [neo's list of readers](https://neo.readthedocs.io/en/latest/iolist.html).
   If neo has a reader, use the `neo` backend. If the signals are one
   interleaved binary file (all channels for sample 0, then all channels
   for sample 1, and so on), use `raw_binary`; you need its sample type,
   channel count, scale (microvolts per bit) and sampling rate.
3. **What are the channel names?** Analyses ask for channels by name: the
   `LFP and EEG CSCs` column of `experiments.csv` must list names exactly as
   the loader produces them. For a neo reader, print them:

    ```python
    import neo

    reader = neo.io.IntanIO(filename="/path/to/recordings/rat01-day1/session.rhd")
    block = reader.read_block(lazy=True, signal_group_mode="split-all")
    print([signal.name for signal in block.segments[0].analogsignals])
    print([(event.name, sorted(set(event.labels))) for event in block.segments[0].events])
    ```

    Use your own reader class and its `filename` or `dirname` argument.
    `signal_group_mode="split-all"` gives each channel its own name; without
    it, many readers group channels and ACE cannot find them by name. For
    `raw_binary`, you choose the names with a template such as `CH{index}`.

4. **How is the recording synchronised with imaging?**
    - TTL pulses recorded as **events** with a fixed label (as Neuralynx
      does): `event_labels`. Copy the label exactly from the output above.
    - TTL pulses recorded on a **digital or analog input channel**:
      `digital_threshold` on that channel.
    - Ephys and imaging share one **hardware clock** (as ONIX does), so no
      pulses are needed: `shared_clock`.
    - Ephys only, no imaging: `shared_clock` (there are no pulses to find).

### Step 3: Start from an example

Copy the example closest to your system into your project's `loaders`
folder. The file name, without `.json`, must equal its `"name"`:

```sh
mkdir -p /path/to/my-project/loaders
cp examples/loaders/intan-rhd.json /path/to/my-project/loaders/my-rig.json
# then change "name": "intan-rhd" to "name": "my-rig"
```

The examples are in the repository's `examples/loaders/` folder. Tests check
that both are valid and behave as described here.

**A system neo can read** (`examples/loaders/intan-rhd.json`):

```json
--8<-- "examples/loaders/intan-rhd.json"
```

- `detect`: a folder is this system's if it contains an `.rhd` file.
- `reader`: neo's `IntanIO` opens one file, so `path_argument` is `filename`
  and `path_from` passes the file found by the `recording` rule.
  `"pick": "only"` makes a folder with two `.rhd` files an error instead of a
  guess.
- `read_block`: `split-all` gives each channel its own name (step 2).
- `time` and `channels` come from the reader. `"default": "none"` loads
  only the channels an analysis asks for.
- `sync`: imaging frame pulses arrive on a digital input. Replace
  `DIGITAL-IN-01` with the name printed in step 2.

**One interleaved binary file** (`examples/loaders/flat-binary-16ch.json`):

```json
--8<-- "examples/loaders/flat-binary-16ch.json"
```

- `detect`: a `.dat` file, but not in folders that also hold Neuralynx
  (`.nev`) or Intan (`.rhd`) files, so this definition does not claim their
  recordings.
- `reader`: 16 channels of `int16`, no header (`byte_offset: 0`), scaled by
  0.195 to microvolts. Use the values from your system's manual.
- `time`: no clock file, so times are the sample number divided by
  `sampling_rate_hz`.
- `channels`: named `CH0` to `CH15`; with `select_by_index`, `3` or `"3"`
  also requests `CH3`.
- `sync`: `shared_clock`, because this rig drives the camera from the
  acquisition clock. Use `digital_threshold` with a channel name such as
  `"CH15"` if a channel records the frame TTL.

### Step 4: Edit it for your system

Change each section using your answers from step 2. The
[format reference](#format-reference-ace-loader1) lists every key. The most
common changes:

- `detect`: your system's file patterns.
- `reader.io` and `path_argument`: your neo reader and whether it takes a
  `filename` or a `dirname`. For `dirname` readers, use
  `"path_from": {"source": "recording_folder"}`, or `file_parent` when the
  files sit in a subfolder.
- `reader.files`: one rule per file the reader needs. Use `capture` when a
  file name shares a part with other files (see the
  [RHS2116 example](#rhs2116)).
- `sync`: your strategy and its channel or labels.
- `label` and `description`: what a colleague needs to know, such as which
  input carries the frame TTL.

Patterns are relative to the recording folder and must not contain machine
paths, because definitions travel with the project to other computers
([portability rules](#portability-rules)).

### Step 5: Validate it

```sh
ace-neuro loaders validate /path/to/my-project/loaders/my-rig.json
```

Every problem is printed as `file: location: message`, where the location is
the key inside the JSON. For example, a definition with three mistakes:

```text
my-project/loaders/my-rig.json: detect.all_of[0]: must be relative to the recording folder, not start with a drive letter
my-project/loaders/my-rig.json: reader.io: 'IntanRHDIO' is not a neo IO in neo.io.iolist; did you mean 'IntanIO'?
my-project/loaders/my-rig.json: sync.edge: must be one of: rising, falling, both (got 'up')
1 of 1 file(s) invalid
```

Fix them and run it again until it prints `ok`:

```text
my-project/loaders/my-rig.json: ok (my-rig, neo)
```

Common messages:

| Message | Fix |
|---------|-----|
| `name: 'x' must match the file name ('y.json')` | Rename the file or change `name`. |
| `unknown key ...; did you mean '...'?` | A typo in a key name. Use the suggestion. |
| `reader.io: '...' is not a neo IO ...` | Use the reader name exactly as neo spells it, or the suggestion. |
| `must be relative to the recording folder ...` | Remove drive letters, leading `/` or `~` from patterns. |
| `reader.args.x: cannot be set in a definition ...` | Remove the argument. Choose files with `files` and `path_from` instead. |
| `reader.args.mode: is required ...` | Add `"mode": "ro"` (or the value the message names) to `args`. |
| `placeholder '{x}' is not captured by an earlier file rule` | Add a `capture` to an earlier rule, or move that rule up. |
| `must be a whole number written without a decimal point` | Write `32`, not `32.0`. |

### Step 6: Check that it recognises your recordings

Run `detect` on a few recording folders, including one from another system
if you have one:

```text
$ ace-neuro loaders detect recordings/rat01-day1 --project-path my-project
Recording folder: recordings/rat01-day1

Built-in loaders whose can_handle() matches:
  (none)

Project definitions that match (my-project):
  my-rig  [neo]  matched: *.rhd (1)
```

- Your definition should be listed for your system's folders and for no
  other folders. If it also matches another system's folders, tighten
  `detect` with `all_of` or `none_of`.
- If a built-in loader also matches, today's analyses use the built-in
  loader.
- `ace-neuro loaders list --project-path my-project` shows every definition
  in the project and reports invalid files.

Share the definition with colleagues by keeping it in the project's `loaders`
folder; it contains no paths from your computer.

### Step 7: Use it in analyses

When ADR 0008 is accepted, you will put the definition's name in a new
`ephys loader` column of `experiments.csv`, or leave the column empty and let
ACE detect it. Until then, analyses cannot read signals through a
definition. To analyse recordings now, write a Python loader.

## Analyse recordings now: a Python loader

A Python loader is a subclass of `EphysDataManager`. It works with today's
pipelines for any format you can read in Python. This example reads a simple
NumPy export, with one `.npy` file per channel; it is in the repository as
`examples/custom_ephys_loader.py`, and tests run it through the real ephys
loader:

```python
--8<-- "examples/custom_ephys_loader.py"
```

Write your own by copying the file and changing the four methods:

| Method | What it must do |
|--------|-----------------|
| `can_handle(directory)` | Return `True` for your system's recording folders, using file names only. |
| `import_ephys_block(ephys_directory)` | Find or open the recording. Set `self.ephys_block` to anything other than `None`. |
| `process_ephys_block_to_channels(channels, remove_artifacts)` | Add a `Channel(name, signal, sampling_rate, time_vector, events)` to `self.channels` for each requested name, or for every channel when `channels` is empty. Times are in seconds, one per sample. |
| `get_sync_timestamps(channel_name)` | Return imaging frame pulse times in the same time base as the channels, or an empty array when there are none. |

To use it, import your module in the same Python script or notebook before
running an analysis:

```python
import custom_ephys_loader  # registers NumpyExportDataManager

from aceneurotools.pipelines.ephys import EphysPipeline

EphysPipeline().run(
    line_num=1,
    project_path="/path/to/my-project",
    data_path="/path/to/data",
    channel_name="LFP1",
    headless=True,
)
```

Things to know:

- **Only Python scripts and notebooks use it.** `ace-neuro` commands and the
  workbench run analyses in a fresh Python process that does not import your
  module, so they keep using the built-in loaders.
- **The first loader that recognises a folder wins.** Built-in loaders are
  tried first, then yours, in import order. Make `can_handle` specific.
- **`experiments.csv` needs its usual columns.** Ephys loading checks the
  `calcium imaging directory` column even for ephys-only rows, so keep the
  column, empty if needed, as in the template.
- **Channel names must match** the names listed in `LFP and EEG CSCs`.
- **For combined calcium and ephys analyses**, `get_sync_timestamps` must
  follow the [multimodal alignment contract](adapting_to_your_lab.md#step-3-multimodal-alignment-contract).


## Commands

```sh
# List the built-in loaders and the definitions in <project>/loaders
ace-neuro loaders list --project-path /path/to/project

# Check definition files; prints "file: path: message" per problem, exits 1 on any
ace-neuro loaders validate /path/to/project/loaders/my-rig.json

# Which built-in loaders and project definitions recognise a recording folder?
ace-neuro loaders detect /path/to/recording --project-path /path/to/project
```

`--project-path` defaults to the current directory. Exit codes:

- `list` exits with 1 when any file in `loaders/` has a problem, or the folder
  cannot be read. Problems are printed to stderr.
- `validate` exits with 1 when any file is invalid or cannot be read.
- `detect` exits with 1 when no built-in loader or project definition
  matches, or when the recording folder is missing or cannot be read. It warns,
  but continues, when the project folder does not exist.

`detect` skips invalid project definitions and lists them on stderr. When several built-in loaders match, it shows which one
`EphysDataManager.create()` uses today: the first in registration order.

## Portability rules

Definitions are meant to travel with a project to other computers, for
example to a cluster once analyses can use them (ADR 0008), so they must not
contain machine paths:

- **Patterns are relative globs under the recording folder.** Use `/` as the
  separator. A pattern cannot be absolute or start with `~` or a drive letter
  (`C:`). It cannot contain backslashes, empty segments, `.` or `..`
  segments, or control characters such as tabs or newlines. `**` must be a
  whole segment, as in `sub/**/*.ncs`.
- **Symbolic links are followed.** A link inside the recording folder (for
  example to raw files kept on another drive) is matched like any other file,
  even if it points outside the folder.
- **Reader arguments are JSON scalars** (string, number, `true`/`false`,
  `null`). A string argument cannot look like a machine path.
- **The recording path is never written in a definition.** The loader passes
  it to the reader. Reader arguments that name files, folders or caches (any
  name containing `file`, `dir`, `path`, `folder`, `cache`, `dll`, `url` or
  `override`, such as `exclude_filename`, `use_cache` or `nsx_override`) cannot
  be set, in `args` or in `read_block`.
- **Strict JSON.** Unknown keys, duplicate keys and `NaN`/`Infinity` are
  errors, so typos do not go unnoticed. Whole numbers are written without a
  decimal point (`32`, not `32.0`). A UTF-8 byte-order mark at the start of
  the file is allowed. A different `schema` version, such as `ace-loader/2`,
  is reported as unsupported.

## Format reference (`ace-loader/1`)

### Top level

| Key | Required | Meaning |
|-----|----------|---------|
| `schema` | yes | Always `"ace-loader/1"`. |
| `name` | yes | Kebab-case identifier (`my-rig`), at most 64 characters. Must equal the file name without `.json`. Cannot be a Windows device name (`con`, `prn`, `aux`, `nul`, `com0`–`com9`, `lpt0`–`lpt9`) or a built-in loader name (`neuralynx`, `rhs2116`). |
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
| `required` | `true` | When `false`, a missing file is allowed. Because the file may be absent, no other section may name its role or use a `{variable}` it captures, except another optional rule. An optional rule whose `{variable}` was not captured is skipped. |
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
| `io` | yes | The name `neo.io` exports a class from `neo.io.iolist` under, for example `NeuralynxIO`, `IntanIO`, `OpenEphysBinaryIO`. Names are checked against neo's own list and are never imported from arbitrary strings. `PickleIO` and `NeurosharectypesIO` are refused because they can run arbitrary code. |
| `path_argument` | yes | The reader's path parameter, usually `dirname` or `filename`. Checked against the class signature. |
| `path_from` | yes | What to pass as the path argument: `{"source": "recording_folder"}`, `{"source": "file", "file": "<role>"}` or `{"source": "file_parent", "file": "<role>"}`. |
| `files` | no | File rules, as above. |
| `args` | no | Other constructor arguments, as JSON scalars. Names are checked against the class signature; for readers such as `BlackrockIO` that pass `**kwargs` on, against the underlying rawio class. Readers must open files read-only: for a reader with a `mode` argument, `mode` must be read-only (`r` or `ro`; `ro` for `NixIO`, `r` for `NWBIO`), and it must be written out when the reader's default could write (`NixIO` defaults to `rw`). For NIX files, `NixIOFr` is neo's read-only reader. |
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
| `clock_file` | `clock_file` (role), `clock_dtype`, `ticks_per_second`, `effective_rate` | The clock file holds one tick count per sample. Seconds are `ticks / ticks_per_second`, computed in float64. `ticks_per_second` is a number, or `{"csv_file": "<role>", "column": N, "header_rows": 0}` to read it from a CSV file (0-based column of the first data row, read as an unsigned integer). `effective_rate` is `{"method": "median_interval", "first_samples": N}`, which sets the channel sampling rate to `1 / median(diff(times[:N]))`, or to `ticks_per_second` when the clock has fewer than two samples. The loaded length is the shorter of the signal and the clock; both are cut to it. |
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

These two definitions are in the repository at `tests/data/loaders/`. Their
names end in `-example` because built-in loader names are reserved; rename a
copy before adapting it for your project. Tests
check them against the built-in managers: detection gives the same result as
`can_handle`, the same files are found, the same sync events are selected,
and RHS2116 channels match bit for bit.

### Neuralynx

```json
--8<-- "tests/data/loaders/neuralynx-example.json"
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
--8<-- "tests/data/loaders/rhs2116-example.json"
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

- neo IO names and their arguments, including refused file, folder and cache
  arguments and the read-only `mode` rule
- references to roles and placeholders, including references to optional files
- which backend, time and channel settings can be combined
- machine paths inside reader arguments
- the file-name rule

Tests keep the schema and the validator in agreement.
