# Terms used in this guide

These definitions are for reading the workflow instructions. The [API reference](api/index.md) gives technical details for programmers.

| Term | Plain-language meaning |
| --- | --- |
| **Miniscope** | A small camera used to record activity in a group of cells. ACE-NeuroTools reads its video and timing files. |
| **Calcium imaging** | A way to measure cell activity from changes in brightness in a fluorescent video. The video is an indirect measure of activity. |
| **Electrophysiology (ephys)** | A recording of electrical signals. A **channel** is one named signal stream, often stored in a separate file. |
| **EEG / LFP** | Types of electrical signals that describe activity from groups of cells rather than a single identified cell. |
| **CNMF-E** | A method used by CaImAn to find candidate cell signals in a miniscope video. Review the result before treating every candidate as a confirmed cell. |
| **Motion correction** | Adjusting video frames to reduce apparent movement of the scene during recording. |
| **Artifact** | A part of a recording caused by equipment or interference rather than the biological signal being studied. |
| **Filter** | A processing step that keeps a selected frequency range of an electrical signal and reduces other frequencies. Frequencies are measured in hertz (Hz). |
| **TTL pulse / sync pulse** | A brief electrical marker recorded by equipment. Matching markers can place video frames and ephys samples on a common time line. |
| **Headless** | Running without pop-up windows or interactive plots. Add `--headless` for a batch or remote-computer run. |
| **`line number` / `--line-num`** | The experiment ID in the `line number` column of `experiments.csv`. It is not the physical row number in a spreadsheet. |
| **`project_path` / `--project-path`** | The folder containing `experiments.csv` and optional configuration files. |
| **`data_path` / `--data-path`** | The root folder containing raw recording files. Relative recording paths in `experiments.csv` are looked up underneath it. |
| **`analysis_parameters.csv`** | An optional spreadsheet for processing choices. Module commands can read a row matching the selected experiment ID. |
