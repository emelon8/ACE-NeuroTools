# Presentation readiness audit

Audited on 2026-10-05 in the `experiment_analysis` checkout, branch
`docs-accessibility-audit`, for the canonical
[ACE-NeuroTools repository](https://github.com/emelon8/ACE-NeuroTools).
GitHub `main` matched local `main` at
`02ffaad1f1316f121711d4a0aada5f2836b4dc32` when checked. The current branch
includes earlier documentation improvements and existing uncommitted
miniscope/guide edits. This audit covers the working tree, not a published release.

## Repairs completed

- Updated clone commands, package metadata, citation metadata, and public
  documentation links to the canonical repository name.
- Reworked the README around inputs, workflows, results, and alpha status.
  Added a workflow diagram and a contributor guide with reproducible checks.
- Removed unresolved personal-information placeholders and repository speculation
  from the author page while preserving the listed authors and contributor credit.
- Replaced advertised hosted documentation links with repository sources. The
  Read the Docs URL returned HTTP 404; hosting instructions now describe the
  remaining setup and verification.
- Cleared the Ruff lint backlog (321 findings at baseline) and standardized
  formatting across Python files and notebooks. CI lint and formatting now fail
  the job when checks fail instead of being advisory.
- Added the missing type-only `StudyMetadata` import, removed unused locals,
  and cleaned equivalent type/None checks and string formatting.
- Corrected the jitter-bound test to check the actual returned values. Made
  the Box template test tolerate formatter changes to quote style.
- Expanded the local Markdown checker to cover all root Markdown documents.
- Preserved the pre-existing staged changes and miniscope implementation.
  Baseline patches were saved in `/tmp/ace-audit-baseline/` for comparison.

Most source changes are formatting. This pass does not redesign processing
algorithms or establish new scientific claims.

## Verification

| Check | Result |
| --- | --- |
| Fast pytest selection (`-m "not slow"`) | 183 passed, before and after cleanup |
| `ruff check .` | Passed |
| `ruff format --check .` | Passed |
| Local Markdown targets and anchors | Passed |
| Notebook sync and `mkdocs build --strict` | Passed |
| Wheel and source distribution build | Passed, using the existing environment with `--no-isolation` |
| `twine check` and distribution-content checks | Passed |
| Wheel package import without the scientific dependencies | Passed |
| Git whitespace check | Passed |

The documentation build emits notebook HTML conversion warnings about unclosed
`div` elements in existing notebook content. It completes successfully, but
notebook rendering should be visually reviewed before hosted publication.
Linux checks used `/home/reedpen/.conda/envs/caiman`. Fresh environment creation,
Windows execution, macOS support, Box authentication, numerical validation on
real recordings, and a full CNMF-E run were not tested in this pass. A clean
lint result does not establish complete type checking or scientific validation.

## Before presenting

1. Merge or publish the reviewed changes to the branch visitors will see.
   Nothing in this audit was committed or pushed.
2. Use the canonical GitHub repository as the poster link or QR destination.
   A hosted documentation link needs a configured, verified deployment first.
3. Validate one representative recording with the exact options used for the
   poster results. Retain the software commit, input provenance, configuration,
   and expected output checks.
4. Confirm poster/paper author order separately from software metadata. Add a
   paper citation or release DOI only once it exists and has been verified.

GitHub's repository description was empty when checked. A suitable description
for a maintainer to add is: “Python pipelines for miniscope calcium imaging,
electrophysiology, and multimodal timestamp alignment.”
