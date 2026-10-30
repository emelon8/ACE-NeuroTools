# Import a cluster CNMF-E result

ACE can import a completed CaImAn CNMF-E extraction without rerunning the movie.
Place two files in one folder on the computer running the ACE workbench:

- The CaImAn estimates HDF5 file saved by the cluster job.
- `manifest.json`, using the format below.

```json
{
  "format": "ace-cluster-result-v1",
  "experiment": "96",
  "estimates": "estimates.hdf5",
  "sha256": "64 lowercase hexadecimal characters for estimates.hdf5",
  "component_ids": [0, 1, 2],
  "frame_rate": 10.0,
  "parameters": {"run_CNMFE": true, "gSig": [3, 3]},
  "software": {"ace": "installed version", "caiman": "installed version"}
}
```

Replace the example values with those from the completed job. `experiment` must
match an existing ACE project experiment number. `component_ids` must list the
original zero-based ID for **each row** of the saved trace matrix, in the same
order. Use `0` through `N-1` for an unfiltered extraction with `N` components.
Record the effective extraction parameters and software versions, rather than
defaults you intended to use. Compute the checksum after transfer with
`sha256sum estimates.hdf5` on Linux, or an equivalent SHA-256 tool. The frame
rate must match the rate in the HDF5 file.

In **Results**, choose **Import cluster extraction**, select the bundle folder,
and choose **Import result**. ACE checks the checksum, footprints, traces,
component IDs, and frame rate. It copies the estimates and manifest into a new
run folder under `<project>/.ace-runs/`. The original bundle stays intact. The
imported run appears in Results, where **Review extracted neurons** opens the
existing curation workflow. Original component IDs are retained in curation
exports.

To detect events directly from the imported estimates, choose a derivative and
height in Results and select **Detect events from estimates**. Each calculation
creates a new `postprocessing/<timestamp>/` folder in the imported run. The same
operation is available without the GUI:

```sh
python -m aceneurotools.pipelines.postprocess_estimates \
  --bundle /path/to/copied-bundle \
  --output /path/to/new-event-result \
  --derivative first --event-height 5
```

This command reads saved component traces and writes `calcium-events.json` with
original component IDs and source provenance. It does not need the movie. Movie
projection filtering, phase and spectrogram analysis, and multimodal alignment
still require their respective source data; importing estimates alone does not
recreate those products.
