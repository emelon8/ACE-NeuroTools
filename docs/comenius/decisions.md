# Decision register

**All entries below are open. Recommendations are proposals, not accepted decisions.**

Start with D01–D06 and D20–D21. Other choices become gates before their affected features. We can interview one decision at a time; this register makes the full discussion visible to collaborators.

For each decision, record: chosen option, rationale, named human owner, date, affected issues, and any follow-up. Nobody has been assigned a role by this document. Silence does not accept a recommendation.

Each decision now has its own GitHub issue for comments, ownership, and the final decision record.

## Decision map

| ID | Decision | Resolve | Suggested human participants |
| --- | --- | --- | --- |
| [D01](#d01) | First milestone and audience | First | Product lead + participating researchers |
| [D02](#d02) | Experiment, subject, session, and run | First | Researchers + application maintainer |
| [D03](#d03) | GUI platform and application boundary | First | UX owner + application maintainer |
| [D04](#d04) | Supported computers and installation | First | Release maintainer + lab users |
| [D05](#d05) | Configuration authority and CSV migration | First | Application maintainer + existing CLI users |
| [D06](#d06) | Data layout and ownership | First | Data steward + application maintainer |
| [D07](#d07) | History and recovery semantics | Before auditability work | Researchers + data steward |
| [D08](#d08) | Reproducibility contract | Before run contract | Scientific reviewer + application maintainer |
| [D09](#d09) | Human approval and automation | Before run contract | Researchers + application maintainer |
| [D10](#d10) | Detection scope and unsupported data | Before import | Data owners + reader maintainers |
| [D11](#d11) | Pipeline selection and suggestions | Before workflow selection | Researchers + UX owner |
| [D12](#d12) | Execution, resources, and interruption | Before execution | Compute maintainer + lab users |
| [D13](#d13) | Scientific quality review and curation | Before curation integration | Scientific reviewer + PR #68 collaborator |
| [D14](#d14) | Multimodal alignment and scope | Before multimodal work | Modality specialists + scientific reviewer |
| [D15](#d15) | Analysis, comparison, and export | Before analysis workspace | Researchers + analysis maintainers |
| [D16](#d16) | Module contracts and trust | Before extension API | Extension maintainer + community reviewers |
| [D17](#d17) | Contribution ownership and governance | Early | Project maintainers + community representatives |
| [D18](#d18) | Experiment sharing and concurrent edits | Before sharing/history contract | Researchers + data steward |
| [D19](#d19) | Integrations and external data movement | Before integrations | Data steward + integration maintainer |
| [D20](#d20) | Human usability and accessibility | First | UX owner + participating researchers |
| [D21](#d21) | Branch strategy and compatibility promises | First | Project maintainers + existing contributors |
| [D22](#d22) | Poster, documentation, and release evidence | Early | Poster authors + scientific reviewer |

<a id="d01"></a>
## D01 — First milestone and audience

**Discuss and decide:** [D01 on GitHub](https://github.com/emelon8/experiment_analysis/issues/87)

**Question:** What must a researcher actually demonstrate at the first milestone, and what does October 7 mean?

**Options:** One complete miniscope path; full paired multimodal path; poster checkpoint with a separate implementation release.

**Recommendation:** Start with one complete miniscope path and a representative real recording, then add paired modalities. Confirm October 7, 2026 explicitly before using it as a date commitment.

**Trade-offs and follow-up:** A full multimodal milestone broadens dataset, synchronization, UI, and validation work before staffing is known.

**Affected work:** F01–F17. **Suggested participants:** Product lead + participating researchers. **Status:** open.

<a id="d02"></a>
## D02 — Experiment, subject, session, and run

**Discuss and decide:** [D02 on GitHub](https://github.com/emelon8/experiment_analysis/issues/88)

**Question:** If one animal is recorded on three days and the team tries two parameter sets, how many experiments should appear?

**Options:** One experiment per session; one experiment per scientific protocol with multiple sessions; user-defined collections with explicit session/subject identity.

**Recommendation:** Use project → experiment → recording sessions, with subjects referenced independently and analysis runs recorded separately; first validate this model against two real lab examples.

**Trade-offs and follow-up:** Do not migrate every CSV line into a subject or an experiment until this is resolved. A rerun should not ambiguously create a new scientific experiment.

**Affected work:** F01–F07, F11–F13. **Suggested participants:** Researchers + application maintainer. **Status:** open.

<a id="d03"></a>
## D03 — GUI platform and application boundary

**Discuss and decide:** [D03 on GitHub](https://github.com/emelon8/experiment_analysis/issues/89)

**Question:** Where does the GUI run, and which application operations do both interfaces call?

**Options:** Native Python desktop; browser UI with a local Python service; hosted browser service.

**Recommendation:** Evaluate native desktop and a local browser UI on file picking, long-running jobs, existing curation windows, accessibility, packaging, and maintenance. Keep shared Python application operations in either case.

**Trade-offs and follow-up:** The Docker-app reference specifies usability, not a toolkit. A hosted service introduces separate data movement, identity, and operations decisions.

**Affected work:** F01–F17. **Suggested participants:** UX owner + application maintainer. **Status:** open.

<a id="d04"></a>
## D04 — Supported computers and installation

**Discuss and decide:** [D04 on GitHub](https://github.com/emelon8/experiment_analysis/issues/90)

**Question:** Which operating systems and installation experience must work for the first real users?

**Options:** Support the lab’s current platforms first; cross-platform installer from day one; managed environment/launcher first.

**Recommendation:** Inventory the actual lab machines, then nominate a tested platform matrix and one install path. Onboarding should diagnose missing dependencies and offer an explicit repair path.

**Trade-offs and follow-up:** CaImAn and GUI dependencies must be validated on the selected machines. Do not infer tested support from package metadata or a Docker analogy.

**Affected work:** F01, F09, F12, F14, F16–F17. **Suggested participants:** Release maintainer + lab users. **Status:** open.

<a id="d05"></a>
## D05 — Configuration authority and CSV migration

**Discuss and decide:** [D05 on GitHub](https://github.com/emelon8/experiment_analysis/issues/91)

**Question:** What is the authoritative saved experiment configuration, and what happens to existing CSV/JSON workflows?

**Options:** CSV remains authoritative; versioned manifest with CSV import/export; database with explicit export/migration.

**Recommendation:** Define a versioned, inspectable configuration contract, with explicit defaults/override precedence and non-destructive CSV/JSON import. Decide export coverage rather than promising lossless round-trip of unknown fields.

**Trade-offs and follow-up:** Reject conflicting identifiers and report unsupported fields. GUI and CLI must resolve the same effective settings. Migration should preserve the originals and a mapping to prior IDs.

**Affected work:** F01, F03–F08, F11–F16. **Suggested participants:** Application maintainer + existing CLI users. **Status:** open.

<a id="d06"></a>
## D06 — Data layout and ownership

**Discuss and decide:** [D06 on GitHub](https://github.com/emelon8/experiment_analysis/issues/92)

**Question:** Does “all in one place” mean copying recordings, linking them, or offering both?

**Options:** Copy into a managed project; reference external/NAS data; explicit copy-or-reference choice.

**Recommendation:** Organize manifests and per-run results under the experiment; allow explicit references to large raw recordings, with optional import by copy. Make missing/moved-data repair visible.

**Trade-offs and follow-up:** Raw data can be very large. Define duplicate detection, rename/relocation behavior, writable output roots, and whether two projects may refer to one input. The physical layout follows D02.

**Affected work:** F01–F07, F10–F13, F16. **Suggested participants:** Data steward + application maintainer. **Status:** open.

<a id="d07"></a>
## D07 — History and recovery semantics

**Discuss and decide:** [D07 on GitHub](https://github.com/emelon8/experiment_analysis/issues/93)

**Question:** What does version control mean in the first release?

**Options:** Saved snapshots with compare/restore; named variants/branches; full branching, merging, and shared editing.

**Recommendation:** Start with visible saved revisions and immutable run snapshots; restoring old settings creates a new revision. Keep past runs and curation decisions associated with their original inputs.

**Trade-offs and follow-up:** Decide autosave versus named checkpoints, author attribution, notes, retention, deletion, and what constitutes a new revision. Full merging is a separate promise.

**Affected work:** F03, F06–F07, F10. **Suggested participants:** Researchers + data steward. **Status:** open.

<a id="d08"></a>
## D08 — Reproducibility contract

**Discuss and decide:** [D08 on GitHub](https://github.com/emelon8/experiment_analysis/issues/94)

**Question:** What evidence must travel with a result, and what level of repeatability can we claim?

**Options:** Configuration only; inputs/configuration/software/environment plus review history; byte-identical outputs across machines.

**Recommendation:** Record effective settings, input identities/checksums, software and module versions, relevant environment/hardware, seeds when applicable, human choices, status, logs, and output identities. Distinguish a traceable rerun from byte-identical reproduction.

**Trade-offs and follow-up:** Choose hashing depth/cost for large datasets, external dependency capture, and numerical comparison tolerances. A settings file alone cannot establish full reproducibility.

**Affected work:** F04–F07, F10–F14, F16. **Suggested participants:** Scientific reviewer + application maintainer. **Status:** open.

<a id="d09"></a>
## D09 — Human approval and automation

**Discuss and decide:** [D09 on GitHub](https://github.com/emelon8/experiment_analysis/issues/95)

**Question:** Which actions require review, and how is deliberate headless use represented?

**Options:** Approve only run launch; approval at scientific checkpoints; fully manual setup with optional explicit automation policies.

**Recommendation:** Always review the final run plan; require explicit scientific review where choices affect interpretation. Headless execution consumes a frozen approved plan or a clearly recorded non-interactive policy.

**Trade-offs and follow-up:** If inputs/settings change after preflight, invalidate that approval. Decide which warnings can be acknowledged, what automation may choose, and how CLI users provide equivalent consent.

**Affected work:** F02–F05, F08–F10, F12–F16. **Suggested participants:** Researchers + application maintainer. **Status:** open.

<a id="d10"></a>
## D10 — Detection scope and unsupported data

**Discuss and decide:** [D10 on GitHub](https://github.com/emelon8/experiment_analysis/issues/96)

**Question:** Which file formats are supported first, and how should the user resolve ambiguous detection?

**Options:** Only existing known formats; a prioritized additional-format list; general extension-driven probing.

**Recommendation:** Begin with nominated existing UCLA/ONIX miniscope and Neuralynx/RHS2116 paths as applicable to real datasets; show evidence, missing companion files, and a manual override. Treat these as candidates until tested.

**Trade-offs and follow-up:** Format detection, metadata inference, and experiment association are separate. Never treat a generic video extension or the first matching plugin as sufficient evidence for a scientific interpretation.

**Affected work:** F02, F08–F09, F11–F12, F14. **Suggested participants:** Data owners + reader maintainers. **Status:** open.

<a id="d11"></a>
## D11 — Pipeline selection and suggestions

**Discuss and decide:** [D11 on GitHub](https://github.com/emelon8/experiment_analysis/issues/97)

**Question:** How much freedom should users have when composing processing and analysis?

**Options:** Curated templates with editable settings; a module list with compatibility checks; arbitrary node/graph editor.

**Recommendation:** Start with named templates and a compatible module list. Suggestions explain their evidence and remain editable; record accepted suggestions in the configuration.

**Trade-offs and follow-up:** Decide whether recommendations are deterministic rules or a later assisted service. A graph editor needs validation of ordering, branching, and intermediate data contracts.

**Affected work:** F03, F08, F13–F14. **Suggested participants:** Researchers + UX owner. **Status:** open.

<a id="d12"></a>
## D12 — Execution, resources, and interruption

**Discuss and decide:** [D12 on GitHub](https://github.com/emelon8/experiment_analysis/issues/98)

**Question:** Where do expensive runs execute, and what does stopping or recovering one mean?

**Options:** One local job; a local queue; remote/HPC/Slurm workers or a hosted service.

**Recommendation:** Start with one local worker process, responsive UI, stage progress, cancellation, and retained failure records. Record an interrupted run on restart; make retry a new linked run.

**Trade-offs and follow-up:** Automatic resumption requires reliable checkpoints and compatible intermediate artifacts; do not promise it by calling a retry “resume.” Set CPU/memory/disk policies and concurrency behavior.

**Affected work:** F04–F06, F09–F13, F16. **Suggested participants:** Compute maintainer + lab users. **Status:** open.

<a id="d13"></a>
## D13 — Scientific quality review and curation

**Discuss and decide:** [D13 on GitHub](https://github.com/emelon8/experiment_analysis/issues/99)

**Question:** Which outputs must a researcher inspect before downstream analysis?

**Options:** Optional review; prescribed crop/motion/component review; configurable review policies per pipeline.

**Recommendation:** Reuse existing crop/component tools, record decisions and reasons, and preserve original estimates. Define quality gates with researchers, including headless behavior.

**Trade-offs and follow-up:** PR #68 already implements component selection and describes overwriting estimates. Comenius must adapt result ownership and lineage without duplicating the selector.

**Affected work:** F05–F06, F10, F12–F13. **Suggested participants:** Scientific reviewer + PR #68 collaborator. **Status:** open.

<a id="d14"></a>
## D14 — Multimodal alignment and scope

**Discuss and decide:** [D14 on GitHub](https://github.com/emelon8/experiment_analysis/issues/100)

**Question:** What modalities are paired first, and what evidence makes their alignment acceptable?

**Options:** Existing calcium/ephys pair; arbitrary modalities; manual alignment only.

**Recommendation:** First support one nominated calcium/ephys pair with visible synchronization markers, drift/gap diagnostics, excluded/uncertain periods, and a recorded approval/correction.

**Trade-offs and follow-up:** Define ground-truth fixtures, acceptable timing errors, units/time bases, missing pulses, non-overlap, and uncertainty propagation into analyses. Do not invent scientific thresholds in software.

**Affected work:** F11–F13. **Suggested participants:** Modality specialists + scientific reviewer. **Status:** open.

<a id="d15"></a>
## D15 — Analysis, comparison, and export

**Discuss and decide:** [D15 on GitHub](https://github.com/emelon8/experiment_analysis/issues/101)

**Question:** Which questions and deliverables should post-processing analysis support first?

**Options:** Browse files only; curated existing analyses with reviewable parameters; a general analysis marketplace.

**Recommendation:** Expose a small agreed set of existing analyses and their input requirements, units, exclusions, and provenance; export figures/tables with a run manifest. Keep processing and analysis selections separate.

**Trade-offs and follow-up:** Decide population versus single-session scope, condition/time-window handling, figure formats, statistical review, and whether comparing two run outputs is required in the first milestone.

**Affected work:** F06, F08, F13–F14, F17. **Suggested participants:** Researchers + analysis maintainers. **Status:** open.

<a id="d16"></a>
## D16 — Module contracts and trust

**Discuss and decide:** [D16 on GitHub](https://github.com/emelon8/experiment_analysis/issues/102)

**Question:** What can a community extension contribute, and how is it enabled?

**Options:** In-repository modules; installed Python package extensions; remotely discovered marketplace.

**Recommendation:** Start with a documented versioned contract for one reader or analysis extension, explicit installation/enablement, compatibility checks, and a reference implementation. Keep core and extension behavior visible in the run record.

**Trade-offs and follow-up:** Define inputs/outputs, parameter schemas, preflight hooks, errors/progress, and provenance. Python extensions execute code; do not claim a sandbox without implementing one. Decide review/trust policy before third-party distribution.

**Affected work:** F08, F13–F16. **Suggested participants:** Extension maintainer + community reviewers. **Status:** open.

<a id="d17"></a>
## D17 — Contribution ownership and governance

**Discuss and decide:** [D17 on GitHub](https://github.com/emelon8/experiment_analysis/issues/103)

**Question:** Who can approve scientific changes, interface changes, and releases?

**Options:** Maintainer review; rotating modality owners; open submissions with documented approval roles.

**Recommendation:** Publish contribution roles and claiming rules; one accountable issue owner, named scientific reviewers, and explicit acceptance evidence. Record owners before implementation rather than assigning people from the transcript.

**Trade-offs and follow-up:** Define how proposals become accepted, how disagreements are resolved, and when a contributor may evolve a stable module contract. Confirm extension licensing and citation expectations with maintainers.

**Affected work:** F14–F15, all issue handoffs. **Suggested participants:** Project maintainers + community representatives. **Status:** open.

<a id="d18"></a>
## D18 — Experiment sharing and concurrent edits

**Discuss and decide:** [D18 on GitHub](https://github.com/emelon8/experiment_analysis/issues/104)

**Question:** How do two researchers exchange or edit an experiment without losing each other’s work?

**Options:** Export/import a portable bundle; shared-folder editing with conflict detection; synchronized multi-user service.

**Recommendation:** For an initial local workflow, support reviewed export/import and reject stale conflicting writes. Decide whether metadata and results or also recordings are shared.

**Trade-offs and follow-up:** GitHub issue collaboration is separate from collaboration inside the product. Live synchronization, access control, authorship identity, and merge policy need an explicit future scope decision.

**Affected work:** F01, F03, F06–F07, F16. **Suggested participants:** Researchers + data steward. **Status:** open.

<a id="d19"></a>
## D19 — Integrations and external data movement

**Discuss and decide:** [D19 on GitHub](https://github.com/emelon8/experiment_analysis/issues/105)

**Question:** Which optional services should onboarding offer, and what may they read or transfer?

**Options:** Local-only first; opt-in existing Box connector; additional storage/compute services.

**Recommendation:** Keep local operation usable; make existing Box setup opt-in with a connection check and an explicit preview of selected transfers. Record source/version details without storing credentials in experiment history.

**Trade-offs and follow-up:** Decide credential storage, offline behavior, failed transfers, provider version IDs, and whether usage/error telemetry exists. An integration suggestion is not consent to upload data.

**Affected work:** F02, F06, F09, F14, F16. **Suggested participants:** Data steward + integration maintainer. **Status:** open.

<a id="d20"></a>
## D20 — Human usability and accessibility

**Discuss and decide:** [D20 on GitHub](https://github.com/emelon8/experiment_analysis/issues/106)

**Question:** Who should be able to finish the workflow without developer help, and how will we know it works?

**Options:** Lab power users; first-time researchers; both with progressive disclosure.

**Recommendation:** Test the same representative task with a first-time researcher and an experienced user; support keyboard operation, clear units, readable contrast, actionable errors, and advanced options on demand.

**Trade-offs and follow-up:** Agree completion criteria and observe where users hesitate. Establish time/error-rate targets after a baseline rather than inventing performance claims.

**Affected work:** F01–F17. **Suggested participants:** UX owner + participating researchers. **Status:** open.

<a id="d21"></a>
## D21 — Branch strategy and compatibility promises

**Discuss and decide:** [D21 on GitHub](https://github.com/emelon8/experiment_analysis/issues/107)

**Question:** How does Comenius absorb existing work and reach the main project without diverging CLI behavior?

**Options:** Long-lived rewrite; incremental feature branches into proj-comenius; independently packaged GUI using a shared engine.

**Recommendation:** Use small owned PRs into proj-comenius and agree a route back to main. Preserve current public CLI/API workflows through adapters while introducing shared operations; document any deliberate deprecations.

**Trade-offs and follow-up:** Choose when to integrate PR #68 and pending packaging/docs work. Define a compatibility matrix and a release policy before changes to schema/CLI become depended upon.

**Affected work:** F01–F17. **Suggested participants:** Project maintainers + existing contributors. **Status:** open.

<a id="d22"></a>
## D22 — Poster, documentation, and release evidence

**Discuss and decide:** [D22 on GitHub](https://github.com/emelon8/experiment_analysis/issues/108)

**Question:** What can the team honestly show or claim at the poster checkpoint?

**Options:** Concept/storyboard; working first workflow; validated multimodal release.

**Recommendation:** Agree a dated demonstration script and state which steps are implemented. Provide a workflow diagram, screenshots tied to a tested version, terminology, and reproducibility example; schedule videos later.

**Trade-offs and follow-up:** Confirm October 7’s year and the practice deadline, dataset-sharing permission, demo hardware, and who signs off on scientific claims. A polished mockup is not evidence of a working pipeline.

**Affected work:** F09, F17. **Suggested participants:** Poster authors + scientific reviewer. **Status:** open.
