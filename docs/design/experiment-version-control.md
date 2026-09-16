# Experiment Version Control (EVC) — architecture

**Status:** working draft, 15 September 2026. Owner: Elijah Keldsen (human decision owner
for experiment version control). Prototype implementation: `src/aceneurotools/evc/`.
This document is Eli's proposal informing Comenius decisions
[D07 — History and recovery semantics (#93)](https://github.com/emelon8/experiment_analysis/issues/93)
and [D08 — Reproducibility contract (#94)](https://github.com/emelon8/experiment_analysis/issues/94),
and implements the core of feature
[F07 — Compare experiment revisions and restore settings without losing history (#76)](https://github.com/emelon8/experiment_analysis/issues/76).

## 1. Vision

ACE-NeuroTools should behave **like git for experiments**: every change to an
experiment's parameters and result manifests is recorded in a git-like format, so a
researcher can *access* any past state, *restore* it, *comment* on it, and *push* it to a
shared lab store. From the team meeting: "literally just like a version control idea —
for your experiments," motivated by the unrecoverable-CSV-edit problem and by
reproducibility.

## 2. Reference material (open source, verified)

The design mimics git's own architecture, verified against:

| Source | What we take from it |
| --- | --- |
| Pro Git, §10.2 ["Git Objects"](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects) (Chacon & Straub, CC BY-NC-SA 3.0) | Content-addressable storage; the `<type> <size>\0<body>` header hashed with the body; blob/tree/commit object types; commit field order (`tree`, `parent`*, `author`, `committer`, blank line, message); loose-object layout `objects/<2 hex>/<rest>`; zlib compression. |
| Pro Git, §10.3 ["Git References"](https://git-scm.com/book/en/v2/Git-Internals-Git-References) | Refs as files containing an object id under `refs/heads/...`; `HEAD` as a symbolic ref (`ref: refs/heads/main`); safe updates via `update-ref` semantics rather than ad-hoc writes. |
| Pro Git, §10.4 (Reflog) / `git reflog` | The append-only journal of ref movements that makes "recover what I just lost" possible even for dangling commits. |
| git `gitformat-hash-function-transition` documentation | Git itself is migrating SHA-1 → SHA-256; a new system should start on SHA-256. |
| `git notes` design | Annotations stored as a parallel history (a notes ref whose tree maps target-oid → note blob) so commenting never rewrites the commented object. |
| Git LFS pointer-file specification (github.com/git-lfs) | The pattern for large binary artifacts: version a small pointer (hash, size, location), not the artifact bytes. Planned for result payloads (§7). |
| Pro Git, §10.1 ("Plumbing and Porcelain") | The two-layer command architecture: a small set of plumbing primitives, with user-facing porcelain composed from them. |

## 3. Concept mapping

| Git concept | EVC concept |
| --- | --- |
| Working tree | The experiment directory's live parameter/config files + small result manifests |
| Blob | One file's content (e.g. `params.json`, `stats_config.json`, a manifest) |
| Tree | A full snapshot of the experiment's versioned files |
| Commit | An **experiment revision**: tree + parent(s) + author + timestamp + message |
| Branch (`refs/heads/main`) | The experiment's revision line (one per experiment; branching is possible later by design, not exposed in v1) |
| HEAD | `.evc/HEAD` symbolic ref — the current line |
| Reflog | `.evc/journal.log` — append-only recovery journal |
| `git notes` | `refs/notes/comments` — post-hoc comments on revisions |
| Remote / push | Shared lab store (directory remote now; Box/SSH/HTTP later) |
| Index/staging | **Omitted** in v1 — snapshots are whole-directory; staging is GUI-era polish |

Each **experiment owns its repository** (`<experiment>/.evc/`), which matches the
Comenius hierarchy (results and history nest inside the experiment, "all in one place").
A project-level view aggregates per-experiment histories; it does not merge them.

## 4. Axioms (invariants every command preserves)

1. **Immutability.** Objects are content-addressed (SHA-256 of `type size\0body`);
   a revision, once recorded, cannot be altered — only added to. Reads verify the
   hash and refuse corrupt objects.
2. **Nothing is ever lost.** Every ref movement is journaled. `restore` of a dirty
   working state first records a *safety snapshot* commit reachable from the journal
   (git's dangling-commit + reflog recovery model). There is no destructive command:
   no force-push, no rewrite, no delete.
3. **History only moves forward.** `restore` copies an old tree into the working
   state; branch refs never rewind. Keeping a restored state = `record`ing a new
   revision whose content equals the old one (revert-style, auditable).
4. **Annotation ≠ mutation.** `comment` attaches text via the notes ref; the
   commented revision's id is unchanged.
5. **Publication is append-only.** `push` is fast-forward-only; a rejected push
   means histories diverged and a human reconciles (D18 territory).
6. **Ref updates are compare-and-set.** Concurrent writers get a `RefConflictError`
   instead of silently clobbering each other (git `update-ref` semantics).

## 5. Module architecture (object-oriented, one responsibility each)

```
aceneurotools/evc/
├── errors.py       EVCError hierarchy (typed failures, no bare excepts)
├── objects.py      Immutable value objects: Blob, Tree, TreeEntry, Commit
│                     — serialization + SHA-256 identity (object_id)
├── store.py        ObjectStore ABC → FileObjectStore (zlib loose objects,
│                     atomic writes, integrity-checked reads, prefix resolve)
├── refs.py         RefStore: refs/, symbolic HEAD, compare-and-set updates,
│                     append-only journal (reflog)
├── repository.py   ExperimentRepository — the PLUMBING facade: hash/read
│                     objects, resolve revisions, history walks, layout+config
├── worktree.py     WorkingTree: directory ⇄ tree snapshot/materialize
├── diff.py         Tree diff + JSON key-level parameter diff (ParamChange)
├── remote.py       Remote ABC → LocalDirectoryRemote; fast-forward push_ref
├── porcelain.py    ExperimentVersionControl — the axiomatic USER commands
└── __main__.py     CLI (python -m aceneurotools.evc) over the same porcelain
```

Extension seams (edit-friendly by design): a new storage backend subclasses
`ObjectStore`; a new transport subclasses `Remote`; what gets versioned is the
`WorkingTree`'s concern; new inspection commands compose existing plumbing. The GUI
calls `ExperimentVersionControl` directly — CLI/GUI parity per ADR 0001.

## 6. The axiomatic command set

| Axiom | Command | Semantics |
| --- | --- | --- |
| record  | `record(message, author)` | Snapshot working state → new revision on the experiment's line. Refuses empty messages and no-op snapshots. |
| access  | `status()` | Clean/dirty vs HEAD with per-file, per-parameter changes. |
| access  | `history(limit)` | Revision line, newest first. |
| access  | `show(rev)` | One revision: metadata + file list. `rev` = `HEAD`, branch name, full or ≥4-char unique id prefix. |
| access  | `diff(a, b)` | Added/removed/modified files; JSON files get dotted-key `old → new` parameter changes. |
| access  | `recover()` | The journal, newest first — includes safety snapshots no ref points at; any listed id can be restored. |
| restore | `restore(rev)` | Working state := revision's tree. Dirty state auto-preserved first (axiom 2); refs untouched (axiom 3). |
| comment | `comment(rev, text)` / `comments(rev)` | Append/read annotations on a revision via the notes history (axiom 4). |
| push    | `push(remote)` | Send missing objects, fast-forward the remote ref; comments ref included by default (axiom 5). |

## 7. Deliberate deviations from git (each documented in code)

1. **SHA-256, not SHA-1** — following git's own transition plan; no legacy interop
   burden since this is a new store.
2. **Text tree serialization** (`<mode> <type> <oid>\t<name>` lines, sorted) instead of
   git's binary tree entries — human-debuggable, deterministic, and sufficient; we do
   not need byte-compatibility with git tooling.
3. **No index/staging area** in v1 — experiments snapshot whole-directory. Selective
   staging can be added behind `record(paths=...)` without format changes.
4. **No packfiles/gc** in v1 — parameter files are small; loose objects with zlib are
   fine at this scale. Packing is an `ObjectStore` implementation detail if ever needed.
5. **Merge is out of scope for v1** — the commit format already supports multiple
   parents, so merge/branch UX is a future porcelain feature, not a format change
   (relevant to D18, concurrent edits).
6. **Large result artifacts** (movies, `estimates.hdf5`) will be versioned as
   **LFS-style pointer manifests** — JSON blobs holding `{sha256, size, uri}` — never
   as raw blobs. v1 versions whatever files are in the experiment directory; the
   pointer convention + helper is the next increment, coordinated with F06 provenance.

## 8. Open questions routed to Comenius decisions

- **D07:** Is journal-based recovery + forward-only restore the accepted semantics?
  (This prototype proposes yes; snapshots-and-restore, no branch UX in v1.)
- **D08:** What belongs in a revision for the reproducibility contract — parameters
  only, or also environment (package versions, config provenance)? The tree format is
  agnostic; adding a generated `environment.json` to snapshots is a one-line policy.
- **D18:** Concurrent edits — v1's answer is compare-and-set refs + fast-forward-only
  push (divergence surfaces as a rejected push for humans to reconcile).
- **D06:** Which directory is "the experiment directory" that EVC tracks — depends on
  the data-layout decision; `WorkingTree` takes any root.

## 9. Verification

- `tests/test_evc_objects.py` — object model: round-trips, hash stability, ordering
  invariance, validation failures.
- `tests/test_evc_repository.py` — store integrity (corruption detected), idempotent
  writes, prefix resolution, refs CAS, journal.
- `tests/test_evc_porcelain.py` — full user journeys: record/history/show/diff,
  dirty-restore safety snapshot + recover, comments, push (new remote, fast-forward,
  up-to-date, diverged rejection), CLI smoke test.

All EVC code is pure standard library (hashlib, zlib, json, pathlib) — no new
dependencies, importable without caiman.
