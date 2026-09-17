# Recording setup and execution

Authorized by Eli on 2026-09-17: implement a modular, object-oriented workflow
from dropped recordings through minimal, precise setup questions to local runs.
This branch implements that direction; it does not close the team's broader
Comenius decision issues.

## Contract

1. Drop files or a recording folder, or use the accessible file/folder picker.
   Browser imports stream copies to the local project; originals are untouched.
2. Inspect recording candidates using metadata and companion files. Display
   evidence and missing information. Never infer subject, treatment, or modality
   from a generic movie/raw-file extension.
3. Confirm a new or existing experiment, a recording, and the intended operation.
   Ask scientific questions only when required by that operation. Known values
   remain visible with their source; missing values are never fabricated.
4. Create an EVC experiment (or attach a new recording without replacing existing
   parameters). Raw files live under ignored `artifacts/`; small configuration,
   input hashes, answers and detection evidence are versioned.
5. Preflight the saved configuration and exact input bytes. Show parameters,
   checks, runtime, output location and limits. Changed inputs/settings invalidate
   the plan. A separate Run action approves this particular plan.
6. Execute one local worker, with visible stage/log output and cancellation.
   Each run has a unique directory. Successful results receive EVC manifests;
   failure, cancellation and interruption remain durable outcomes.

## Module boundaries

`gui/src/workflow/` owns browser file enumeration, upload transport, workflow
state and the Lumino panel. `gui/server/ace_workbench/workflow/` owns typed
contracts, bounded upload storage, detector strategies, conditional questions,
pipeline strategies, experiment setup, preflight and worker lifecycle.

The HTTP router is an adapter. Scientific code is imported only in a separate
worker; the GUI service remains usable without CaImAn. Existing EVC operations
remain the history implementation. Legacy scientific readers receive isolated
per-run metadata, rather than edits to a lab's original CSV registries.

## Scientific boundaries

Detection identifies a recording format, not experimental meaning. Multiple
recordings require selection; pairing/alignment is never assumed. CNMF-E needs
researcher-supplied indicator decay and spatial scale and review of extraction
thresholds. Extracted components are uncurated estimates. Ephys export preserves
signal units and acquisition timestamps. Generic trace CSV analysis requires
explicit time and signal units. Integrity inventory is labeled as an inspection,
not scientific processing. Unsupported/incomplete formats remain explainable.
