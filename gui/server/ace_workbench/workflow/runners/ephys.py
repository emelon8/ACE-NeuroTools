"""Export actual acquisition samples; avoid legacy implicit gap interpolation."""

from __future__ import annotations

import csv
from pathlib import Path

from ..common import atomic_json
from .base import Runner


class EphysRunner(Runner):
    def check(self, root: Path, configuration: dict) -> dict:
        import neo  # noqa: F401
        import numpy as np

        candidate = configuration["candidate"]
        metadata = candidate["metadata"]
        if candidate["format"] == "rhs2116":
            clock = root / metadata["streams"]["clock"]
            ticks = np.memmap(clock, dtype="<u8", mode="r")
            previous = None
            for start in range(0, len(ticks), 1000000):
                values = ticks[start : start + 1000000]
                if (previous is not None and values[0] <= previous) or np.any(values[1:] <= values[:-1]):
                    raise ValueError("RHS clock contains duplicate, reversed or wrapped timestamps.")
                previous = values[-1]
            samples = len(ticks)
        else:
            from neo.io import NeuralynxIO

            reader = NeuralynxIO(dirname=str(root / candidate["directory"]))
            names = list(reader.header["signal_channels"]["name"])
            if configuration["effective"]["channel"] not in names:
                raise ValueError("Selected channel filename does not match a channel in the Neuralynx header.")
            samples = sum(
                reader.get_signal_size(block_index=0, seg_index=i, stream_index=0)
                for i in range(reader.segment_count(0))
            )
        return {
            "estimated_output_bytes": int(samples) * 80,
            "estimated_memory_bytes": int(samples) * 32 * 8,
            "warnings": [
                "Export preserves acquisition timing and gaps. No filtering, interpolation, artifact removal, or anatomical assignment is performed."
            ],
        }

    def run(self, root: Path, configuration: dict, output: Path) -> None:
        import numpy as np

        candidate, settings = configuration["candidate"], configuration["effective"]
        name = settings["channel"]
        directory = root / candidate["directory"]
        print(f"Loading calibrated channel {name}", flush=True)
        if candidate["format"] == "rhs2116":
            from aceneurotools.ephys.rhs2116_data_manager import RHS2116DataManager

            manager = RHS2116DataManager(directory, channels=[name], auto_compute_phases=False, remove_artifacts=False)
            channel = manager.channels[name]
            segments = [(channel.time_vector, channel.signal)]
            unit = "uV"
        else:
            from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager

            manager = NeuralynxDataManager(directory, auto_process_block=False, auto_compute_phases=False)
            # Legacy BlockProcessor interpolates gaps. Export original Neo segments instead.
            segments = []
            for segment in manager.ephys_block.segments:
                signal = next((s for s in segment.analogsignals if s.name == name), None)
                if signal is None:
                    raise ValueError(f"Channel {name} is missing from a recording segment.")
                segments.append((signal.times.rescale("s").magnitude, signal.rescale("uV").magnitude.reshape(-1)))
            unit = "uV"
        count, previous = 0, None
        with (output / "channel.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["time_s", name])
            for times, values in segments:
                if (
                    len(times) != len(values)
                    or not np.all(np.isfinite(times))
                    or not np.all(np.isfinite(values))
                    or np.any(np.diff(times) <= 0)
                ):
                    raise ValueError("Reader produced invalid sample timing or nonfinite channel values.")
                if len(times) and previous is not None and times[0] <= previous:
                    raise ValueError("Acquisition segments overlap or run backwards.")
                writer.writerows(zip(times, values))
                count += len(times)
                if len(times):
                    previous = times[-1]
        if count < 2:
            raise ValueError("No usable signal samples were exported.")
        atomic_json(
            output / "channel-metadata.json",
            {
                "channel": name,
                "samples": count,
                "signal_unit": unit,
                "time_unit": "seconds",
                "filter": "none",
                "interpolation": "none",
                "source_format": candidate["format"],
            },
        )
