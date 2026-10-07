"""Observe public pipeline calls in a fresh process without replacing science code.

Used only by parity tests. The CLI mode runs the real argparse/module entry point;
the parameter mode stops at the public run() boundary before expensive computation.
"""

import importlib
import inspect
import json
import runpy
import sys
from pathlib import Path


class ParametersCaptured(Exception):
    pass


def save_miniscope(pipeline, output):
    import numpy as np

    dm = pipeline.miniscope_data_manager
    values = {
        "temporal_projection": dm.projections.time,
        "frame_rate": dm.fr,
        "time_stamps": dm.time_stamps,
        "frame_numbers": dm.frame_numbers,
        "PSD_spect": dm.PSD_spect,
        "t_spect": dm.t_spect,
        "freqs_spect": dm.freqs_spect,
        "p_spect": dm.p_spect,
        "miniscope_phases": dm.miniscope_phases,
    }
    values.update(
        {
            f"projection_{name}": getattr(dm.projections, name)
            for name in ["max", "std", "min", "mean", "median", "range"]
        }
    )
    if dm.filter_object is not None:
        values.update(
            unfiltered_temporal_projection=dm.filter_object.data,
            filtered_temporal_projection=dm.filter_object.filtered_data,
        )
    estimates = dm.CNMFE_obj.estimates
    values.update({name: getattr(estimates, name, None) for name in ["C", "S", "F_dff", "YrA", "b", "f"]})
    if estimates.A is not None:
        values["A_dense"] = estimates.A.toarray()
    np.savez(output, **{key: value for key, value in values.items() if value is not None})
    diagnostics = {}
    for name in ["neurons_sn", "g", "bl", "c1"]:
        value = getattr(estimates, name, None)
        if value is not None:
            diagnostics[name] = np.asarray(value.tolist() if isinstance(value, np.ndarray) else value, dtype=float)
    np.savez(Path(output).with_suffix(".diagnostics.npz"), **diagnostics)
    Path(output).with_suffix(".events.json").write_text(
        json.dumps({str(key): np.asarray(value).tolist() for key, value in (dm.ca_events_idx or {}).items()})
    )


def main():
    mode, kind, project, output = sys.argv[1:5]
    module = f"aceneurotools.pipelines.{kind}"
    observed = {}

    def observe(frame, event, result):
        if frame.f_code.co_name != "run" or frame.f_globals.get("__name__") != "__main__":
            return
        if event == "call":
            count = frame.f_code.co_argcount + frame.f_code.co_kwonlyargcount
            observed.update({key: frame.f_locals[key] for key in frame.f_code.co_varnames[:count] if key != "self"})
            if mode == "parameters":
                sys.setprofile(None)
                Path(output).write_text(json.dumps(observed, default=str))
                raise ParametersCaptured()
        elif event == "return" and mode == "cli":
            sys.setprofile(None)
            pipeline = frame.f_locals["self"]
            if kind == "ephys" and hasattr(pipeline, "ephys_data_manager"):
                import numpy as np

                channel = pipeline.ephys_data_manager.get_channel(observed["channel_name"])
                values = {
                    "signal": channel.signal,
                    "time": channel.time_vector,
                    "sampling_rate": channel.sampling_rate,
                    "signal_filtered": channel.signal_filtered,
                    "phases": channel.phases,
                }
                np.savez(output, **{key: value for key, value in values.items() if value is not None})
            elif kind == "miniscope" and hasattr(pipeline, "postprocessing_result"):
                save_miniscope(pipeline, output)

    if mode in {"parameters", "cli"}:
        # Import dependencies before observing the entry point; profiling their
        # import-time Python calls would dominate this otherwise small check.
        importlib.import_module(module)
        sys.argv = [module, "--line-num", "1", "--project-path", project, "--data-path", project, "--headless"]
        sys.setprofile(observe)
        try:
            runpy.run_module(module, run_name="__main__")
        except ParametersCaptured:
            pass
        finally:
            sys.setprofile(None)
        if not observed:
            raise RuntimeError("The real CLI did not reach the public pipeline run() boundary.")
        return

    # Direct Python/API path: independent from every gui.* module.
    import numpy as np

    options = json.loads(Path(project, "api-options.json").read_text())
    options.update(line_num=1, project_path=project, data_path=project, headless=True)
    if kind == "ephys":
        from aceneurotools.pipelines.ephys import EphysPipeline

        pipeline = EphysPipeline()
        pipeline.run(**options)
        channel = pipeline.ephys_data_manager.get_channel(options["channel_name"])
        values = {
            "signal": channel.signal,
            "time": channel.time_vector,
            "sampling_rate": channel.sampling_rate,
            "signal_filtered": channel.signal_filtered,
            "phases": channel.phases,
        }
    elif kind == "compute":
        from aceneurotools.miniscope import ucla_data_manager  # noqa: F401
        from aceneurotools.pipelines.compute import ComputePipeline

        result = ComputePipeline().run(
            project_path=project,
            data_path=project,
            lab_config=None,
            calcium_signal_dir=Path(output).parent / "calcium_signals",
            line_nums=[1],
            headless=True,
        )
        if 1 not in result:
            raise RuntimeError("Direct compute skipped the experiment.")
        with np.load(result[1], allow_pickle=False) as archive:
            values = dict(archive)
    elif kind == "preprocess":
        from aceneurotools.miniscope import ucla_data_manager  # noqa: F401
        from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
        from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor

        manager = MiniscopeDataManager.create(
            1, project_path=project, data_path=project, filenames=options.pop("filenames", [])
        )
        coords = options.pop("crop_coords", None)
        options.pop("line_num")
        options.pop("project_path")
        options.pop("data_path")
        pre = MiniscopePreprocessor(manager)
        pre.preprocess_calcium_movie(
            coords_dict=dict(zip(["x0", "y0", "x1", "y1"], coords)) if coords else None, **options
        )
        values = {
            "movie": manager.movie,
            "frame_rate": manager.fr,
            "time_stamps": manager.time_stamps,
            "frame_numbers": manager.frame_numbers,
        }
        if manager.projections is not None:
            values.update(
                {
                    f"projection_{name}": getattr(manager.projections, name)
                    for name in ["max", "std", "min", "mean", "median", "range", "time"]
                }
            )
    elif kind == "miniscope":
        from aceneurotools.miniscope import ucla_data_manager  # noqa: F401
        from aceneurotools.pipelines.miniscope import MiniscopePipeline

        pipeline = MiniscopePipeline()
        if mode == "configs":
            from aceneurotools.miniscope.pipeline_results import PostprocessConfig, PreprocessConfig, ProcessConfig

            common = {key: options[key] for key in ["line_num", "project_path", "data_path", "filenames", "headless"]}
            configs = {
                name: cls(**{key: value for key, value in options.items() if key in inspect.signature(cls).parameters})
                for name, cls in [
                    ("preprocess", PreprocessConfig),
                    ("process", ProcessConfig),
                    ("postprocess", PostprocessConfig),
                ]
            }
            pipeline.run_with_configs(**common, **configs)
        else:
            pipeline.run(**options)
        save_miniscope(pipeline, output)
        return
    else:
        raise ValueError(kind)
    np.savez(output, **{key: value for key, value in values.items() if value is not None})


if __name__ == "__main__":
    main()
