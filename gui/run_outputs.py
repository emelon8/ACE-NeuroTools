"""Explicit, pickle-free export contracts for GUI analysis results."""

from pathlib import Path

import numpy as np

from gui.runs import atomic_json


class OutputInventory:
    def __init__(self, root, kind, parameters):
        self.root = Path(root)
        self.kind = kind
        self.parameters = parameters
        self.outputs = []
        self.archives = {}
        self.diagnostics = {}

    def missing(self, name, flag=None, reason=None):
        disabled = flag is not None and not self.parameters.get(flag, False)
        self.outputs.append(
            {
                "name": name,
                "status": "not_computed",
                "reason": reason or (f"{flag} disabled" if disabled else "Not available from the pipeline result"),
            }
        )

    def array(self, name, value, file="postprocessing.npz", flag=None):
        if value is None:
            self.missing(name, flag)
            return
        try:
            array = np.asarray(value)
            if array.dtype.kind == "O":
                # CaImAn diagnostics can wrap numeric scalars or vectors in an
                # object array. Infer their numeric shape/dtype without pickle.
                array = np.asarray(array.tolist())
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name}: could not serialize the computed numeric output.") from exc
        if array.dtype.kind not in "biufc":
            raise ValueError(f"{name}: expected a numeric array, received {array.dtype}. Output was not exported.")
        self.archives.setdefault(file, {})[name] = array
        self.outputs.append(
            {
                "name": name,
                "status": "exported",
                "file": file,
                "key": name,
                "shape": list(array.shape),
                "dtype": str(array.dtype),
            }
        )

    def artifact(self, name, path, flag=None):
        if path is None:
            self.missing(name, flag)
            return
        path = Path(path).resolve()
        if not path.is_relative_to(self.root.resolve()) or not path.is_file():
            raise ValueError(f"{name}: the declared output file is missing or outside this run: {path}")
        self.outputs.append({"name": name, "status": "exported", "file": str(path.relative_to(self.root.resolve()))})

    def events(self, name, values, filename, metadata=None, flag=None):
        if values is None:
            self.missing(name, flag)
            return
        if not isinstance(values, dict):
            raise ValueError(f"{name}: expected an event dictionary.")
        data = {str(key): np.asarray(value).tolist() for key, value in values.items()}
        atomic_json(self.root / filename, {**(metadata or {}), name: data} if metadata is not None else data)
        self.outputs.append(
            {
                "name": name,
                "status": "exported",
                "file": filename,
                "key": name if metadata is not None else None,
                "groups": len(values),
            }
        )

    def finish(self):
        for name, values in self.archives.items():
            np.savez_compressed(self.root / name, **values)
        atomic_json(
            self.root / "diagnostics.json",
            {
                "kind": self.kind,
                "parameters": self.parameters,
                **self.diagnostics,
                "availability": [item for item in self.outputs if item["status"] != "exported"],
            },
        )
        self.artifact("diagnostics", self.root / "diagnostics.json")
        for name, path in [("effective_parameters", "effective-parameters.json"), ("run_log", "run.log")]:
            if (self.root / path).is_file():
                self.artifact(name, self.root / path)
            else:
                self.missing(name)
        atomic_json(
            self.root / "output-inventory.json",
            {
                "schema_version": 1,
                "kind": self.kind,
                "parameters": self.parameters,
                "outputs": self.outputs,
            },
        )


def miniscope_outputs(report, dm):
    params = report.parameters
    obj = getattr(dm, "CNMFE_obj", None)
    estimates = getattr(obj, "estimates", None)
    C = getattr(estimates, "C", None)
    ids = np.arange(C.shape[0], dtype=int) if C is not None else None
    report.array("neuron_ids", ids)
    for name in ["C", "S", "F_dff", "YrA", "b", "f"]:
        report.array(name, getattr(estimates, name, None), flag="run_CNMFE")
    A = getattr(estimates, "A", None)
    if A is not None:
        from scipy.sparse import csc_matrix

        # Preserve footprints without allocating the potentially enormous dense matrix.
        A = csc_matrix(A)
        for name, value in {"A_data": A.data, "A_indices": A.indices, "A_indptr": A.indptr, "A_shape": A.shape}.items():
            report.array(name, value, "components.npz")
    else:
        report.missing("A", "run_CNMFE")
    for name in [
        "SNR_comp",
        "r_values",
        "cnn_preds",
        "idx_components",
        "idx_components_bad",
        "neurons_sn",
        "g",
        "bl",
        "c1",
    ]:
        report.array(name, getattr(estimates, name, None), "diagnostics.npz")
    metadata = {
        "neuron_ids": ids.tolist() if ids is not None else [],
        "fr": float(dm.fr),
        "experiment": params.get("line_num"),
        "trace_source": {"file": "postprocessing.npz", "key": "C"},
        "parameters": {key: params.get(key) for key in ["derivative_for_estimates", "event_height"]},
        "index_convention": "Zero-based peak indices in C (zeroth) or np.diff(C, n=1 or 2); no frame offset added.",
    }
    report.events(
        "ca_events_idx", getattr(dm, "ca_events_idx", None), "calcium-events.json", metadata, "find_calcium_events"
    )
    projections = getattr(dm, "projections", None)
    report.array("temporal_projection", getattr(projections, "time", None))
    for name in ["max", "std", "min", "mean", "median", "range"]:
        report.array(f"projection_{name}", getattr(projections, name, None))
    filtered = getattr(dm, "filter_object", None)
    report.array("unfiltered_temporal_projection", getattr(filtered, "data", getattr(projections, "time", None)))
    report.array("filtered_temporal_projection", getattr(filtered, "filtered_data", None), flag="filter_miniscope_data")
    report.array("frame_rate", dm.fr)
    for name in ["time_stamps", "frame_numbers"]:
        report.array(name, getattr(dm, name, None))
    for name in ["PSD_spect", "t_spect", "freqs_spect", "p_spect"]:
        report.array(name, getattr(dm, name, None), flag="compute_miniscope_spectrogram")
    report.array("miniscope_phases", getattr(dm, "miniscope_phases", None), flag="compute_miniscope_phase")
    for name, attribute, flag in [
        ("neuron_estimates", "estimates_filepath", "save_estimates"),
        ("caiman_parameters", "opts_caiman_filepath", "save_CNMFE_params"),
        ("preprocessed_movie", "preprocessed_movie_filepath", None),
        ("motion_corrected_movie", "motion_corrected_movie_filepath", "apply_motion_correction"),
    ]:
        report.artifact(name, getattr(dm, attribute, None), flag)
    report.missing("correlation_pnr_diagnostics", reason="Interactive plot diagnostics are not computed by the GUI run")
    report.missing(
        "motion_correction_shifts", reason="The core pipeline does not retain a motion-correction object or shifts"
    )
    report.diagnostics.update(
        neuron_count=len(ids) if ids is not None else None,
        inline_requested=params.get("inline"),
        projection_replaced=filtered is not None and projections.time is filtered.filtered_data,
        phase_and_spectrogram_input="unfiltered temporal projection (computed before filtering in the core pipeline)",
    )


def ephys_outputs(report, channel):
    for name, value in {
        "signal": channel.signal,
        "time": channel.time_vector,
        "sampling_rate": channel.sampling_rate,
        "signal_filtered": channel.signal_filtered,
        "phases": channel.phases,
    }.items():
        flag = "compute_phases" if name == "phases" else None
        report.array(name, value, "ephys.npz", flag)
    report.events("ephys_events", channel.events, "ephys-events.json")
    report.diagnostics["channel_name"] = channel.name


def multimodal_outputs(report, pipeline):
    """Preserve both sub-pipelines and every retained alignment result."""
    miniscope_outputs(report, pipeline.miniscope_pipeline.miniscope_data_manager)
    channel = pipeline.ephys_pipeline.ephys_data_manager.get_channel(report.parameters["channel_name"])
    ephys_outputs(report, channel)
    for name in [
        "t_ca_im",
        "low_confidence_periods",
        "ephys_idx_all_TTL_events",
        "ca_frame_num_of_ephys_idx",
        "phase_hist_ephys",
        "phase_bin_edges_ephys",
        "phase_hist_miniscope",
        "phase_bin_edges_miniscope",
    ]:
        report.array(name, getattr(pipeline, name, None), "alignment.npz")
    for name in ["ephys_idx_ca_events", "ca_events_phases_ephys", "ca_events_phases_miniscope"]:
        report.events(name, getattr(pipeline, name, None), f"{name}.json", flag="ca_events")
