# Keeping backend changes safe

Every pull request runs the integrity checks automatically. Look for **Quality
gate** in the pull request checks: all mandatory jobs must pass. A red check
means the proposed change needs attention before it can be merged. Open the
failed job to see the failing test and its explanation. Avoid deleting the test,
adding a skip, or reducing a coverage threshold just to get a green check.

The checks also run on pushes to `main` and `proj-comenius`, manually from the
Actions page, for merge queues, and weekly on the repository's default branch.
Release tags use the same reusable workflow as pull requests. They retain the
existing publication approval requirements.

## What is protected

| Contract | Evidence |
| --- | --- |
| CSV identity and cell values survive parsing | Leading zeroes, large IDs, literal notes, UTF-8 BOM, CRLF, quoted commas and newlines, optional blank settings, historical empty spacer columns |
| A bad CSV change cannot silently destroy the existing file | Invalid columns, missing experiments, duplicate IDs, schema mismatches, simulated disk errors, atomic replacement and staging cleanup |
| Settings identify the intended experiment and time windows | Invalid JSON roots, non-finite values, booleans used as numbers, fractional subject IDs, duplicate window keys, aggregated validation errors, JSON round trips |
| Numerical operations match independent answers | Pairwise correlogram counting, brute-force timestamp matching, padded event windows, per-sample SEM, filter amplitude, known signal delay and coherence |
| Spectral power has the right magnitude and units | Independent DPSS periodograms, amplitude-squared scaling, DC/Nyquist energy, eigenvalue normalization, serial/parallel equivalence, one-window and one-frequency results |
| Phase summaries respect the chosen neurons | Analytic Hilbert phases, circular wraparound, histogram mass, equal-neuron averaging, empty units, invalid event indices and headless selection |
| Coherence and population comparisons retain their scientific meaning | Independent averaged cross-spectra, known signal gains, paired Wilcoxon results, explicit undefined ratios, saved subject identities |
| Scatter statistics count acquired samples | Closed-form correlation, slope and Fisher intervals, paired effect sizes/tests, subject-pair exclusion, missing-data masks and constant signals |
| Statistics loaders keep signal fields aligned | Actual TTL sample indexing across signals, clocks, filtered signals and phases; paired clock checks, staged updates, frame-rate validation, closed numeric archives and stage-specific errors |
| Randomized analysis is reproducible | Seeded surrogates, interval/count invariants, permutation ties, corrected p-values and rejection of non-finite statistics |
| History and result provenance remain inspectable | Corrupt compressed objects, invalid object paths, simultaneous writes, one-winner reference updates, interrupted writes, artifact hashes, invalid manifests, dirty-state recovery |
| Real pipeline inputs produce expected outputs | Lossless synthetic multi-file movies through the API and real CLI, explicit cropping, synthetic RHS2116 clocks, filtering and phases, unchanged input files |
| Installed distributions contain backend resources | Schemas, metadata templates, typed marker, no bundled lab data, and installed wheel and source-distribution checks outside the source checkout |
| Releases publish the checked package | Release jobs download the exact artifact from the shared verification workflow; they do not rebuild it |
| The public history API remains usable by existing tools | Stable exported names, standard-library-only import, frozen return types and recoverable dirty work |
| The CI checks themselves fail correctly | Executed tests of the skip guard and quality gate; coverage tests reject missing modules, invalid floors and reports without branches |

These contracts are tested independently of the GUI. Existing GUI tests still
run in a separate job to detect accidental compatibility regressions; no new
browser tests were added.

## Run the backend checks locally

Start with the scientific environment from the [installation guide](getting_started.md).
The pinned conda environment contains the compiled neuroscience CaImAn package.
The package called `caiman` on PyPI is unrelated and must not be substituted.

When regenerating the lock, retain the Qt-enabled OpenCV build: CaImAn's AVI
reader calls `destroyAllWindows` even during headless processing, and that call
fails in headless OpenCV builds. The environment also explicitly includes
`cython`, `moviepy`, `numpydoc`, and `yapf`, which CaImAn declares in its Python
metadata but its conda recipe omits. The lock regression checks cover both
supported platforms; the backend job additionally runs `pip check` against the
installed environment.

From the repository root:

```bash
python -m pip install --no-deps -e .
python -m pip install -r ci/requirements-test.txt
python scripts/run_backend_checks.py
```

This command executes the backend suite, requires every selected test to run,
generates reports, and checks branch-coverage floors. It returns a nonzero exit
status on failure. It does not install dependencies, change Git history, or use
real lab recordings. For a broader generated-case search:

```bash
python scripts/run_backend_checks.py --extended
```

Ordinary CI uses a deterministic Hypothesis profile with 100 examples per
property. Weekly runs use 500 examples and fresh generation. A Hypothesis
failure includes a minimized input and reproduction information. Add that input
as a permanent regression case when fixing the underlying problem.

Integration tests use small synthetic files and run in ordinary CI; the `slow`
marker is reserved for expensive, separately validated real-recording work.
`--backend-only` excludes `test_gui_*.py` and `test_crop_gui.py` before collection.
Missing Hypothesis is a collection error. `--fail-on-skip` rejects both skipped
and expected-failure tests, including collection skips for absent dependencies.

## Read the audit trail

Each locked backend job uploads a `backend-<operating-system>-<attempt>` artifact,
even when tests fail. The artifacts are kept for 30 days and include:

- `junit.xml`: which tests ran, their durations, and failures;
- `coverage.json` and `coverage.xml`: line and branch measurements;
- `coverage-html/index.html`: browsable source with uncovered branches;
- `environment.json`: Git commit, whether the checkout was dirty, Python and
  platform, installed dependency versions, test profile, run/attempt identifiers,
  and SHA-256 hashes of configuration, lock files, and source/test/workflow files.
  Source hashes also identify uncommitted local changes.

The local runner writes the same reports under ignored `reports/`. Environment
evidence records package versions, not credentials or a dump of environment
variables. Test logs and artifacts use synthetic inputs. Save the artifacts
alongside a review or release record if evidence is needed beyond 30 days.

Linux and Windows run the complete backend suite in the locked scientific
environment. Separate Python 3.11 and 3.12 jobs automatically discover all core
tests against current pip dependencies, without CaImAn or Box access. New tests
are included without editing a workflow file. Tests needing CaImAn use the
`requires_caiman` marker and import it inside the test; files that require it
at import time belong in `tests/compiled_stack/`. The portable jobs exclude that
directory before importing test modules and deselect the marked cases. The locked
jobs execute all of them. Each environment report makes dependency drift visible.

The versioned `ci/coverage-policy.json` includes an overall
floor and stricter floors for key modules. It measures lines **and** branches.
An absent module fails the check. Raise floors as coverage improves; changes
that lower them should explain which protected behavior is being removed.
The overall floor reflects the inherited untested code; it is not a claim of
complete backend coverage.

## Compatibility and scientific corrections

The tests retain valid existing config/CSV formats, CLI commands and public
pipeline names. These corrections intentionally change problematic cases:

- Raw CSV cells remain strings so leading zeroes and literal notes survive.
  Custom scripts needing parsed values should use `convert_data_types`.
  Missing required rows fail explicitly; absent optional analysis rows use
  defaults, and crop-coordinate persistence returns `False` if its row is absent.
  Malformed CSV errors still propagate.
- Padded peri-event SEM uses the actual contributing sample count at each time.
- Eigenvalue-weighted spectra divide by the sum of eigenvalues. The default
  uniform weighting is unchanged. Nonpositive power becomes undefined in dB.
- Headless mean-density phase analysis respects selected neurons and excludes
  empty neurons from the circular average.
- Downsampling keeps timestamps, filtered signals and phase arrays at the same
  samples as the signal. Paired channels must share a clock.
- Scatter analysis excludes long missing-data gaps from normalization and
  regression. Constant signals have undefined correlation and regression.
  Population coherence ratios with a zero baseline remain undefined.

These are scientific result changes for affected inputs. Review representative
recordings before comparing affected results to historical analyses. Passing
synthetic tests does not establish that every external custom script is compatible.

## One repository setting the workflow cannot supply

A repository administrator should require **Quality gate** for `main` and
`proj-comenius` in branch rules, require pull requests, and restrict bypasses and
direct pushes. Select the actual emitted check from a completed Actions run
because reusable-workflow display prefixes may vary. Without a required check,
GitHub runs CI but can still permit a failing change to be merged. The workflow
always evaluates this gate and treats failed, cancelled, and skipped mandatory
jobs as failures. See GitHub's [required status check documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging).

## Limits and scientific review

Synthetic tests establish reproducible behavior, not biological validity on all
recording systems. Full real-data CNMF-E validation, interrupted power-loss
recovery across multiple files, live Box behavior, and hardware/driver changes
still need representative local validation. The pinned Windows environment must
also be exercised on a hosted runner; a Linux local run cannot establish its
success.

Type checking remains advisory because of the existing type backlog. All other
jobs in Quality gate are blocking. The current electrophysiology phase contract
uses the acquired signal even when a filtered signal is also stored; the
integration test documents that behavior rather than silently changing it.

The optional coherogram plot requires an `xrscipy` version exposing
`signal.spectral.coherogram`; versions without that API warn and omit that plot.
Welch coherence statistics still run through SciPy. The unavailable plotting path
is not claimed as an independently validated accelerated implementation.

Remaining gaps include full multimodal orchestration, video denoising and head
orientation, execution of real-data tutorials, minimum dependency versions, and
legacy Box download/retry behavior. Existing probes under `review/` are exploratory
evidence outside the passing CI suite; they do not become protected regressions
until their behavior is confirmed and the corresponding fix/test lands. The
weekly job starts only after this workflow reaches the default branch.

Changes to algorithms, units, time alignment, masks or defaults should explain
their scientific effect, name the regression test, and record representative
recording checks in the pull request. New data formats should supply small
synthetic fixtures with known answers before they are relied on in the lab.
