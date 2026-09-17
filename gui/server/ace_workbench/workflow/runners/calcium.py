"""Explicit timing checks and an isolated adapter to the existing CNMF-E stage."""

from __future__ import annotations

import csv
from pathlib import Path

from ..common import atomic_json
from .base import Runner


def acquisition_times(root: Path, candidate: dict):
    import numpy as np

    metadata = candidate["metadata"]
    if candidate["format"] == "ucla-miniscope":
        values, frame_numbers = [], []
        with (root / metadata["timestamps"]).open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            next(reader)
            for row in reader:
                if len(row) < 2:
                    raise ValueError("Malformed frame timestamp row.")
                frame_numbers.append(int(row[0]))
                values.append(float(row[1]) / 1000)
        if len(frame_numbers) > 1 and not np.all(np.diff(frame_numbers) == 1):
            raise ValueError(
                "Frame numbers contain gaps, duplicates or reversals. Resolve dropped frames before extraction."
            )
        times = np.asarray(values)
    else:
        path = root / metadata["clock_file"]
        if path.stat().st_size % 8:
            raise ValueError("Clock file contains an incomplete 64-bit sample.")
        ticks = np.fromfile(path, dtype="<u8")
        # Check integers before floating conversion, and subtract in integer space.
        if len(ticks) < 2 or np.any(ticks[1:] <= ticks[:-1]):
            raise ValueError("Acquisition clock is empty, repeated, wrapped or reversed.")
        times = (ticks - ticks[0]).astype(float) / metadata["clock_hz"]
    if len(times) < 3 or not np.all(np.isfinite(times)) or np.any(np.diff(times) <= 0):
        raise ValueError("At least three finite, increasing acquisition timestamps are required.")
    intervals = np.diff(times)
    median = float(np.median(intervals))
    if np.any(np.abs(intervals - median) > max(0.002, median * 0.1)):
        raise ValueError(
            "Timing contains gaps or excessive jitter. CNMF-E requires reviewed uniform sampling; no interpolation is applied."
        )
    return times, 1 / median


class CalciumRunner(Runner):
    def check(self, root: Path, configuration: dict) -> dict:
        import caiman  # noqa: F401 -- exercise the selected runtime's actual imports
        import cv2

        times, measured_rate = acquisition_times(root, configuration["candidate"])
        declared = configuration["effective"]["frame_rate"]
        if declared and abs(measured_rate - declared) / declared > 0.03:
            raise ValueError(f"Frame-rate metadata ({declared:g} Hz) conflicts with timestamps ({measured_rate:g} Hz).")
        total, dimensions = 0, None
        for name in configuration["candidate"]["metadata"]["movies"]:
            capture = cv2.VideoCapture(str(root / name))
            try:
                ok, frame = capture.read()
                count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
                if not ok or count < 1:
                    raise ValueError(f"Movie is unreadable or empty: {name}")
                shape = frame.shape[:2]
                if dimensions and dimensions != shape:
                    raise ValueError("Movie segments have inconsistent frame dimensions.")
                dimensions = shape
                total += count
            finally:
                capture.release()
        if total != len(times):
            raise ValueError(
                f"Movie frame count ({total}) differs from acquisition timestamps ({len(times)}); truncation is not allowed."
            )
        if total < 20:
            raise ValueError(
                "CNMF-E needs at least 20 frames; this is a technical minimum, not assurance of a scientifically adequate recording."
            )
        if min(dimensions) <= max(configuration["effective"]["gSiz"]):
            raise ValueError("Neuron spatial scale is too large for the movie dimensions.")
        raw = total * dimensions[0] * dimensions[1] * 4
        return {
            "frames": total,
            "dimensions": list(dimensions),
            "frame_rate": declared or measured_rate,
            "timestamp_rate": measured_rate,
            "estimated_memory_bytes": raw * 6,
            "estimated_output_bytes": raw * 5,
            "warnings": [
                "Resource estimates are lower bounds; CNMF-E can require substantially more memory and disk.",
                "Extraction thresholds need recording-specific review; components are uncurated. Deconvolution is disabled (p=0); no spike estimates are requested.",
                "All segments are concatenated in the displayed natural filename order; no crop, detrend or ΔF/F normalization is applied.",
            ],
        }

    def run(self, root: Path, configuration: dict, output: Path) -> None:
        import caiman as cm
        import numpy as np

        from aceneurotools.miniscope.miniscope_processor import MiniscopeProcessor
        from aceneurotools.shared.plotting import set_backend

        set_backend(headless=True)
        metadata = configuration["candidate"]["metadata"]
        settings = configuration["effective"]
        times, measured_rate = acquisition_times(root, configuration["candidate"])
        rate = settings["frame_rate"] or measured_rate
        print("Loading the approved movie segments", flush=True)
        movie = cm.load_movie_chain([str(root / name) for name in metadata["movies"]], fr=rate)
        if movie.shape[0] != len(times) or not np.all(np.isfinite(movie)):
            raise ValueError("Decoded movie does not match the approved timing or contains nonfinite pixels.")
        # A TIFF avoids the lossy numeric conversion of the legacy AVI preprocessing writer.
        movie_path = output / "input-movie.tif"
        movie.save(str(movie_path))
        excluded = {"frame_rate", "motion_correct", "crop", "detrend", "df_over_f", "workers", "curation"}

        class RecordingAdapter:
            def __init__(self):
                self.movie, self.fr = movie, rate
                self.metadata = {"calcium imaging directory": str(output)}
                self.analysis_params = {k: v for k, v in settings.items() if k not in excluded}
                self.preprocessed_movie_filepath = str(movie_path)
                self.estimates_filepath = None

            def get_miniscope_directory(self):
                return output

        class HeadlessProcessor(MiniscopeProcessor):
            def cleanup_tkinter(self):
                # The legacy implementation switches to Qt even when plot_params=False.
                set_backend(headless=True)

        processor = HeadlessProcessor(RecordingAdapter())
        print("Extracting calcium components with CNMF-E", flush=True)
        dm = processor.process_calcium_movie(
            parallel=False,
            n_processes=1,
            apply_motion_correction=settings["motion_correct"],
            inspect_motion_correction=False,
            plot_params=False,
            run_CNMFE=True,
            save_estimates=True,
            save_CNMFE_estimates_filename="estimates.hdf5",
            save_CNMFE_params=True,
        )
        estimates = dm.CNMFE_obj.estimates
        traces = estimates.C
        if traces is None or traces.shape[1] != len(times) or not np.all(np.isfinite(traces)):
            raise ValueError("CNMF-E did not produce finite component traces aligned to all input frames.")
        with (output / "component-traces.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["time_s", *[f"component_{i}" for i in range(traces.shape[0])]])
            for index, time in enumerate(times):
                writer.writerow([float(time), *traces[:, index].tolist()])
        atomic_json(
            output / "quality-review.json",
            {
                "status": "uncurated",
                "components": int(traces.shape[0]),
                "frame_rate": rate,
                "trace_unit": "CaImAn component amplitude; not ΔF/F",
                "required_review": "Inspect spatial footprints, residuals, motion and traces before interpretation. No automated cell acceptance or event inference was performed.",
            },
        )
