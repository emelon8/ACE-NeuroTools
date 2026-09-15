# Single-AVI Smoke Test — Setup Checklist

Use this to set up `aceneurotools` on a new machine and reach the goal:

> Download one `.avi` from Box, run CNMF-E to produce `estimates.hdf5`, and
> open the GUI to pick neurons.

Everything below is meant to be done **once** per machine. Once it works, the
day-to-day workflow is just step 8 (edit the four constants and run).

The companion script is [`single_avi_smoke_test.py`](single_avi_smoke_test.py)
in this same folder.

---

## 1. Install micromamba

Follow the [official micromamba installation instructions](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html)
for your operating system. On Windows, open the terminal configured by the
installer; on macOS or Linux, open a new terminal after installation.

Verify:

```bash
micromamba --version
```

You should see a version number. If the command is not found, finish the
installer's shell setup before continuing.

---

## 2. Clone the repo

Pick a folder you're happy keeping code in (e.g. `~/code/`):

```bash
cd ~/code
git clone https://github.com/emelon8/experiment_analysis.git
cd experiment_analysis
```

From here, all paths in this doc are **relative to** that
`experiment_analysis/` folder unless they start with `/`.

---

## 3. Create the conda environment

The committed lock covers Linux and Windows. Use it on those systems:

```bash
micromamba create -n aceneurotools -f conda-lock.yml
```

On macOS, use the human-maintained environment file instead; this checkout
does not include a macOS lock:

```bash
micromamba create -f environment.yml
```

This pulls in CaImAn and everything else and takes ~10–20 minutes. Then:

```bash
micromamba activate aceneurotools
pip install --no-deps -e .
```

The `-e .` registers `aceneurotools` so `python -m aceneurotools.pipelines.miniscope`
and `from aceneurotools... import ...` both work from any directory.

Verify:

```bash
python -c "import caiman, aceneurotools; print('caiman + aceneurotools OK')"
```

If that prints `caiman + aceneurotools OK`, the environment is good. If it fails
on a CaImAn import, check that `aceneurotools` is active. If it still fails,
remove the `aceneurotools` environment with `micromamba env remove -n aceneurotools`
and re-run step 3.

---

## 4. Get your Box credentials

Open <https://byu.app.box.com/developers/console>.

You have two options. **Pick one.**

### Option A — quick, expires every hour (good for first-time testing)

1. Open (or create) any Box custom app you have access to.
2. Click **Configuration**.
3. Scroll to **Developer Token** and click **Generate Developer Token**.
4. Copy the token. **It only lasts 1 hour.**

### Option B — permanent, what we use day-to-day

1. **First person on the team only:** click **Create Platform App** →
   **Server Authentication (Client Credentials Grant)**. Up to 15 teammates
   can share one app.
2. Open that app → **Configuration**:
   - Under **Application Scopes**, check **Write all files and folders
     stored in Box**.
   - Save changes.
3. Open **Authorization** → **Submit for Authorization**, and ask whoever
   manages the BYU Box enterprise to approve it. Until this is approved
   nothing else in this guide will authenticate, so don't skip it.
4. Back on the **Configuration** tab, copy:
   - **Client ID**
   - **Client Secret**
   - **User ID** (top right of the Box web UI → click your avatar → Account
     Settings → the long number beside "Account Details")

Keep these somewhere safe (a password manager — **not** in git).

---

## 5. Fill in `box_credentials.py`

From the repo root:

```bash
# Linux / macOS
cp src/aceneurotools/shared/BLANK_box_credentials.py src/aceneurotools/shared/box_credentials.py

# Windows (PowerShell)
Copy-Item src/aceneurotools/shared/BLANK_box_credentials.py src/aceneurotools/shared/box_credentials.py
```

Open `src/aceneurotools/shared/box_credentials.py` in your editor and paste in
the values from step 4:

- If you used **Option A** (developer token): replace
  `PUT_YOUR_BOX_DEVELOPER_TOKEN_HERE` with your token in the `dev_token` field.
  The credentials file then selects developer-token authentication. You do
  not need to edit `file_downloader.py`.

- If you used **Option B** (CCG): leave `dev_token` at its placeholder and fill
  in `client_id`, `client_secret`, and `user_id`.

`box_credentials.py` is in `.gitignore`, so it will not be committed. Don't
share this file.

Verify the file at least imports:

```bash
python -c "from aceneurotools.shared.box_credentials import auth; print('credentials loaded:', auth)"
```

Then verify it actually authenticates with Box:

```bash
python -c "from aceneurotools.shared.file_downloader import make_auth; print(make_auth())"
```

You want to see `Successfully connected to Box client` and a `<BoxClient ...>`
object. If you get `None` or an exception, the credentials or the
enterprise-approval step (4-Option-B-3) are wrong; fix that **before** moving
on.

---

## 6. Create your `project_path` (the CSV folder)

Pick a folder somewhere local — it does **not** need to live inside the repo.
Example: `~/lab/correlation_project/`.

Copy the two templates into it and rename them:

```bash
mkdir -p ~/lab/correlation_project
cp src/aceneurotools/shared/metadata_templates/experiments_template.csv          ~/lab/correlation_project/experiments.csv
cp src/aceneurotools/shared/metadata_templates/analysis_parameters_template.csv  ~/lab/correlation_project/analysis_parameters.csv
```

You should now have:

```text
~/lab/correlation_project/
├── experiments.csv
└── analysis_parameters.csv
```

Open `experiments.csv` in a spreadsheet editor (Excel, LibreOffice, Google
Sheets) and either:

- **Reuse an existing row.** Copy the row that corresponds to the recording
  you want to test from `data/experiments_correlation_project.csv` in this
  repo. Make sure it has values in **`Box Calcium Folder ID`** and
  **`calcium imaging directory`**. Note the **`line number`** — you'll use
  it as `LINE_NUM` in step 8.

- **Add a new row.** The two fields that *must* be filled in for the smoke
  test:

  | Column                       | Where to get it                                                                                                            |
  | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
  | `line number`                | Any unique integer — pick `1` if the file is otherwise empty.                                                              |
  | `Box Calcium Folder ID`      | Open the Miniscope folder for that recording in Box's web UI; the long number at the end of the URL is the folder ID.     |
  | `calcium imaging directory`  | Relative path under `data_path` where you want the AVI to land, e.g. `K99/miniscope_data/sleep/R220817B/2022_11_25/14_04_09`. |

Then open `analysis_parameters.csv` and either copy the row from
`data/analysis_parameters_correlation_project.csv` for the same line number,
or just leave the example row from the template. The pipeline only needs
sensible values in `crop_coords`, `gSig`, `gSiz`, `min_corr`, `min_pnr`, and
`decay_time` to actually finish CNMF-E; the template values work for UCLA
miniscope data.

> Tip: keep the `line number` identical in both CSVs. The pipeline matches
> rows across the two files by that number.

---

## 7. Create your `data_path` (the raw data folder)

Pick a directory with **plenty of free space** (a single 10-minute miniscope
session is several GB). Example: `~/lab/raw_data/`.

```bash
mkdir -p ~/lab/raw_data
```

You don't have to put anything in it; the smoke-test script will let Box
populate the right subfolders.

> If your `experiments.csv` row says
> `calcium imaging directory = K99/miniscope_data/sleep/R220817B/2022_11_25/14_04_09`,
> the AVI will end up at
> `~/lab/raw_data/K99/miniscope_data/sleep/R220817B/2022_11_25/14_04_09/Miniscope/0.avi`.

---

## 8. Run the smoke test

Open `examples/single_avi_smoke_test.py` and edit the four constants near
the top:

```python
PROJECT_PATH = Path("/home/<you>/lab/correlation_project")
DATA_PATH    = Path("/home/<you>/lab/raw_data")
LINE_NUM     = 96             # the row you set up in step 6
AVI_FILENAME = "0.avi"        # start with the first AVI of the session
```

On Windows, use forward slashes or raw strings:

```python
PROJECT_PATH = Path(r"C:\Users\you\lab\correlation_project")
```

Then, with the env active:

```bash
micromamba activate aceneurotools
python examples/single_avi_smoke_test.py
```

What you should see, in order:

1. `Step 0/3: checking paths and credentials...` — confirms the CSVs are
   where you said and `box_credentials.py` imports.
2. `Step 1/3: downloading AVI from Box...` — if the AVI is already on disk
   it skips immediately; otherwise it pulls it.
3. `Step 2/3: running MiniscopePipeline...` — CaImAn does motion correction
   (skipped in this script) and CNMF-E. This is the slow step (minutes to
   tens-of-minutes for one AVI). Then a **FreeSimpleGUI window opens** showing
   the detected neurons over a max projection. Click the listbox entries
   for any components you want to reject, then **Submit**.
4. `Step 3/3: locating estimates.hdf5` — prints the full path of the saved
   `estimates.hdf5`.

If any step fails, the script prints `[smoke-test] FAILED at: <stage>` plus
a hint targeted at that specific stage. Take the stage name to whoever set
this up and they'll know where to look.

---

## 9. After it works once

You're now set up. From this point:

- Re-running the same line number is just `python examples/single_avi_smoke_test.py`
  again (it'll skip the download if the AVI is already on disk).
- To process a different recording: edit `LINE_NUM` (and add the row in
  `experiments.csv` / `analysis_parameters.csv` if it's not there).
- To process the *whole* recording (all AVIs) instead of just `0.avi`: stop
  using this smoke-test script and use the real entry point —
  `python -m aceneurotools.pipelines.miniscope --line-num <N> --project-path
  /your/project --data-path /your/raw_data`. See
  [`docs/guides/miniscope.md`](../docs/guides/miniscope.md) for the full
  parameter list.

---

## Quick troubleshooting reference

| Symptom                                                              | Most likely cause                                                                                  |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `ModuleNotFoundError: aceneurotools.shared.box_credentials`              | Skipped step 5 — the file is still named `BLANK_box_credentials.py`.                              |
| `make_auth()` returns `None` or prints an exception                  | Step 4-Option-B-3 (enterprise approval) wasn't done, or client_id/secret/user_id is wrong.        |
| Dev token suddenly stops working ~1 hour in                          | That's expected — generate a fresh dev token (step 4-Option-A-3), or switch to CCG (Option B).    |
| `The miniscope path or ID do not exist in the CSV file` in the logs  | The `experiments.csv` row is missing `Box Calcium Folder ID` or `calcium imaging directory`.       |
| `0.avi did not land at ...`                                          | Box folder ID points at the wrong folder, or that folder doesn't actually contain `0.avi`.        |
| GUI step crashes with `ModuleNotFoundError: FreeSimpleGUI`           | Check that the `aceneurotools` environment is active; its `environment.yml` installs FreeSimpleGUI. If the environment is incomplete, recreate it. |
| `import caiman` fails                                                | The environment wasn't activated (`micromamba activate aceneurotools`) or setup did not finish — recreate it.   |
| CNMF-E finishes with 0 neurons                                       | `gSig` / `min_corr` / `min_pnr` in `analysis_parameters.csv` are wrong for this recording.         |
