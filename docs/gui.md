# Experiment workbench

Launch `ace-gui` after activating the ACE environment. The default address uses
port 8765. The browser opens with a random launch token; reopen that printed
launch address if you need another tab. Every API request, including health,
previews and downloads, requires the launch token. A new launch generates a new
token. Keep the server running while using the application. Use Ctrl+C to close
it. The server listens only on 127.0.0.1.

Open a folder containing `experiments.csv` and optionally
`analysis_parameters.csv`. CSV files remain authoritative (ADR 0002). Settings
and defaults use the same shared code as the command-line pipelines (ADR 0001).
Unknown columns, existing quoting, line endings and multiline notes survive
edits. Original files are backed up under `.ace-gui-backups/`; rollback restores
a copy and preserves that backup.

Download Box recordings first, then choose their local data folder. The GUI
supports metadata/settings edits, embedded crop previews, reviewed analysis
runs, retained results and neuron curation. The Box setup wizard and cluster job
script generation are separate follow-ups. Neither service is included here.

Runs copy reviewed inputs under `.ace-runs/`. Multimodal runs keep calcium data
under `recording/` and electrophysiology under `recording-ephys/`; crop validation
always reads the calcium recording. Stopping sends terminate, waits for exit,
and force-kills if necessary. A failed stop keeps the run active. Partial
outputs remain available after stopping.

CSV snapshots and run manifests describe settings at launch. They are not an
EVC revision history. EVC is parked until an application consumer is integrated.
