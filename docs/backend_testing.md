# Scientific regression checks

This change corrects numerical results; historical outputs can change. The
backend PR contains numerical code, its tests, and this document. Module names
remain those on `main` (`aceneurotools.multimodal`) so reviewing an algorithm does
not require reviewing a package migration.

Run the complete existing and new regression suite in the CaImAn environment:

```sh
MPLBACKEND=Agg python -m pytest tests/ -m "not slow"
```

## Result contracts

| Result | Corrected behavior | Regression |
| --- | --- | --- |
| Peri-event SEM | Each padded time bin uses its own number of contributing events. Bins without acquired samples remain undefined. | `tests/test_backend_perievent_sem.py` |
| Multitaper PSD | Eigenvalue weights sum to one. Power and one-sided frequency scaling match independent SciPy periodograms. | `tests/test_backend_spectrogram.py` |
| Phase average | Average Cartesian unit vectors with equal neuron weights, then convert to an angle. Ignore empty neurons; no events means undefined density/phase. | `tests/test_backend_phase_analysis.py` |
| Spectral band power and plots | Convert only positive finite power to dB. Zero/negative/nonfinite bins are missing; means and color limits ignore them, and wholly missing bands stay undefined. | `tests/test_backend_spectral_db_contract.py` |
| TTL downsampling | Signal, timestamps, filtered signal and phase use identical sample indices. Validate both channel clocks and lengths before mutating either channel. | `tests/test_backend_downsampling.py` |
| Scatter gaps | Exclude the union of long EEG/calcium gaps and a margin on both sides before pooled z-scoring, regression and uncertainty. Extend masks before trimming endpoints. | `tests/test_backend_scatter_analysis.py` |
| Boundary NaNs | Extend short leading/trailing gaps with the nearest acquired value. An entirely missing signal has no valid samples. | `tests/test_backend_signal_integrity.py` |

The scatter margin is `int(edge_trim_seconds * frame_rate)` samples on each side
of a long gap (five seconds by default). It is a heuristic, not a bound on
filter error; low cutoffs may need longer margins. Setting the trim to zero
adds no margin. Short interpolated gaps remain valid. The endpoint-gap test
covers a gap contained entirely within the discarded endpoint samples whose
transient margin still reaches retained data.

## Representative recordings: deferred

The user deferred these checks on 2026-10-16. Synthetic regression success does
not establish biological validity. When recording checks resume, record the
following in the PR for each representative Box recording:

- Box file/folder ID, recording/animal ID, SHA-256 of local inputs, acquisition
  rate, selected channels, event provenance and analysis windows.
- Baseline and candidate commit IDs, environment versions and exact settings.
- Peri-event event counts and per-bin available counts, means and SEM deltas.
- Unity/eigen multitaper spectra against independent periodograms, frequency
  grid and integrated-power deltas; identify whether previous results used
  eigen weighting.
- Per-neuron event counts, population histogram and circular phase/vector
  deltas, including unequal event counts and the wrap at ±π.
- TTL indices and timestamps and lengths of every downsampled field; reject
  mismatched paired clocks without changing either channel.
- Scatter excluded counts including margins, pooled normalization mean/std,
  correlation/slope/CI deltas and plots around each gap. Include a gap-free
  recording as a control and choose margins appropriate to its filter.

The local full suite passed **340 tests** on 2026-10-16 using Python 3.10 in the
existing CaImAn environment. This is regression evidence only. Representative
Box recording checks have not been run and are deferred by request; do not
mark them complete based on the synthetic fixtures.

## Spectral dB follow-up

Band-power averages and spectrogram color limits no longer convert exact zeros
into a fabricated -300 dB floor. Non-positive and non-finite linear power bins
are treated as missing. This changes results for bands containing those bins;
positive finite power retains the existing 10*log10(power) convention. An
all-zero or fully missing band reports NaN. Seven focused tests cover scalar
and array conversion, mixed and all-missing bands, ordinary positive power,
and plot output. Representative recording checks remain deferred by request.

## Change-based continuous integration

Pull requests and pushes to `main` first run the lightweight selector in
`scripts/ci_plan.py`. Each workflow summary lists the jobs and test paths selected.
The workflows still report a result when expensive jobs are skipped; selection
failures or failures in any selected job fail the aggregate result.

| Changed files | Checks selected |
| --- | --- |
| Documentation, notebooks, documentation theme/configuration, or documentation scripts | Documentation build and local-link checks |
| Individual test files | Changed tests; GUI test changes also run the GUI group because tests share fixtures |
| GUI Python, JavaScript, or HTML | GUI tests and public naming contracts; installed-wheel checks; Python changes also rebuild API docs |
| GUI styles or static image/font assets | Installed-wheel checks |
| Calcium imaging or miniscope readers | Imaging regressions and downstream GUI/alignment/statistics integration checks, API docs, and installed-wheel checks |
| Electrical recording code | Electrical regressions and downstream GUI/alignment/statistics integration checks, API docs, and installed-wheel checks |
| Multimodal code | Multimodal regressions and downstream GUI/statistics integration checks, API docs, and installed-wheel checks |
| Shared utilities, pipeline orchestration, dependencies, package recipes, CI configuration, other scripts, or unclassified files | All jobs and the full non-slow test suite |

Native conda builds on Linux, Windows, and both Mac architectures run when package
configuration, dependencies, CI, or native launch entry points change. They also
run for the conservative full fallback. Other focused code changes use the Linux
installed-wheel check; release tags and manual workflow runs always run all jobs.
Merge-queue events and unavailable comparison history also fall back to full checks.

PR comparisons use the merge base of the target and PR head, so all commits in
the PR count. Push comparisons use the complete before/after range, not only the
last commit. Renames count as a removal and addition so both affected areas are
covered. Mixed changes combine their selected checks. New unclassified test files
are included in focused code runs until they are assigned to a group.

The selector uses conservative groups rather than claiming exact per-function
coverage. Keep its regression groups current when adding cross-component
coupling. Its dependency-free tests run before selection in both workflows:

```sh
python -m unittest tests.test_ci_plan
```

To request a full run regardless of changed files, select **Run workflow** for
**CI** or **Conda package** in GitHub Actions. Full runs retain the existing
`not slow` selection; they do not introduce a real-recording acceptance test.
