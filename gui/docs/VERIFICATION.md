# Workbench verification — 2026-09-16

Local environment: macOS arm64; Node 25.8.1; isolated Python 3.10.20;
Chromium 153 through Playwright 1.63.0. CI separately exercises Ubuntu,
Node 24, Python 3.10/3.12 and Chromium. Dependency versions are locked.

| Check | Measured result |
| --- | --- |
| Existing scientific fast suite, before changes | 277 passed, 1 skipped, 17.33 s |
| Existing scientific fast suite, after implementation | 277 passed, 1 skipped, 12.50 s |
| GUI API/service tests | 20 passed |
| Parameter type unit tests | 9 passed |
| Chromium workflows | 9 passed, 6.6 s for the full local run |
| Automated accessibility | No WCAG 2 A/AA or WCAG 2.1 AA violations detected on the parameter form/shell |
| TypeScript + Vite production build | Passed; local JSON/editor workers emitted |
| GUI Python Ruff lint/format | Passed |
| `npm audit` including development dependencies | 0 known vulnerabilities |
| Python locked dependencies, `pip-audit --no-deps --disable-pip` | No known vulnerabilities found |
| Production launcher | Passed: real launcher, static app/notices, two clean EVC demos, unauthenticated API rejection, graceful shutdown |
| Existing scientific source/test diff | Empty against `2fd7cac` |
| Git identity | GitHub confirms author and committer `elijah-keldsen`; no AI attribution trailers added |

The EVC property tests are the baseline suite's one skipped test module because
Hypothesis is absent from the existing CaImAn environment. The slow full CNMF-E
pipeline was not run. No real acquired dataset was processed. Automated
accessibility checks do not substitute for researcher/screen-reader usability
sessions. Native Windows/macOS installers and Firefox/Safari are not validated.

The latest complete published code-validation run available while writing this
report was [GitHub Actions run 35186484812](https://github.com/emelon8/experiment_analysis/actions/runs/35186484812),
with all three jobs successful. Every later GUI push triggers the same workflow;
inspect the branch's Actions page for its newest result.

## Exercised browser journeys

- Real Lumino shell, local Monaco workers, token removal from visible URL.
- Typed parameter edit → save → inspect key differences → record → reload.
- Revision comparison in Monaco, safe restore, forward-only history, comments.
- Real manifest integrity verification and numeric CSV trace preview.
- Blocking recording with unsaved buffers; canceling experiment switch preserves them.
- Command palette and experiment switching.
- Compact 1024×768 desktop, invalid arrays and visible validation feedback.
- Monaco find and keyboard save through the focused editor.

API tests additionally cover stale-file rejection, concurrent review rejection,
safety-snapshot recovery, strict schema validation, duplicate/nonfinite JSON,
immutable CSV provenance, traversal/symlink rejection, origin/host/token checks,
manifest tamper/missing detection, artifact confinement, oversized documents,
malformed manifest reporting and preserving edits when reopening the demo.

## Visual evidence

Screenshots were captured from the running application with real synthetic EVC
fixtures and inspected, not generated mockups:

- [Desktop JSON editor, 1440×960](screenshots/workbench-desktop.png)
- [Verified synthetic result traces](screenshots/workbench-results.png)
- [Parameter form, 1024×768](screenshots/workbench-compact.png)

The compact screenshot deliberately includes an operation-log entry from its
invalid-input test. The result plot uses values read from the manifest-listed
CSV, with canonical viridis color samples. Preview data are synthetic and labeled
as such. No acquired recording was copied into the repository.

## Non-blocking observations

Vite reports a large Monaco bundle (about 3.43 MB uncompressed main JS, 0.89 MB
compressed; JSON feature chunk about 0.70 MB). This is a local desktop app and
loads successfully; further bundle optimization is not claimed. The Python
test adapter emits upstream Starlette/httpx and AnyIO deprecation notices; all
assertions pass. The original scientific tree still has 298 advisory Ruff
findings, separately documented in the audit.
