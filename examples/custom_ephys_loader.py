"""Worked example: a Python ephys loader for a recording format ACE does not read.

The format here is a simple NumPy export, chosen so the example runs anywhere:

    <ephys directory>/
    ├── timestamps.npy      sample times in seconds, one per sample
    ├── sync.npy            imaging frame pulse times in seconds (optional)
    └── channels/
        ├── LFP1.npy        one 1-D signal per channel, same length as timestamps
        └── EEG1.npy

Replace the file reading with whatever your system needs; keep the four methods.
See docs/guides/loader_definitions.md, "Analyse recordings now: a Python loader".

Use it from a Python script or notebook. Importing this module registers the
loader; it must be imported before the pipeline runs, in the same process:

    import custom_ephys_loader  # noqa: F401  (registers NumpyExportDataManager)
    from aceneurotools.pipelines.ephys import EphysPipeline

    EphysPipeline().run(line_num=1, project_path="/path/to/project",
                        data_path="/path/to/data", channel_name="LFP1", headless=True)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from aceneurotools.ephys.channel import Channel
from aceneurotools.ephys.ephys_data_manager import EphysDataManager


class NumpyExportDataManager(EphysDataManager):
    """Reads recordings exported as one .npy file per channel."""

    @classmethod
    def can_handle(cls, directory: str | Path) -> bool:
        """Recognise the folder from file names only; never read data here.

        Be specific: loaders are tried in registration order and the first
        match is used, so a test that also matches another system's folders
        would take those recordings over.
        """
        folder = Path(directory)
        return (folder / "timestamps.npy").is_file() and (folder / "channels").is_dir()

    def import_ephys_block(self, ephys_directory: str | Path) -> None:
        """Find the files. Reading can wait until channels are requested."""
        self.folder = Path(ephys_directory)
        self.ephys_block = self.folder  # anything not None marks the import as done

    def process_ephys_block_to_channels(
        self, channels: list[str] | None = None, remove_artifacts: bool = False
    ) -> None:
        """Create one Channel per requested channel (all channels when none are requested)."""
        times = np.load(self.folder / "timestamps.npy")
        sampling_rate = float(1.0 / np.median(np.diff(times)))
        for path in sorted((self.folder / "channels").glob("*.npy")):
            if channels and path.stem not in channels:
                continue
            signal = np.load(path)
            if signal.shape != times.shape:
                raise ValueError(f"{path.name} has {signal.size} samples but timestamps.npy has {times.size}")
            events = {"labels": [], "timestamps": []}
            self.channels[path.stem] = Channel(path.stem, signal, sampling_rate, times, events)

    def get_sync_timestamps(self, channel_name: str | None = None) -> np.ndarray:
        """Imaging frame pulse times, in the same time base as ``timestamps.npy``."""
        sync = self.folder / "sync.npy"
        return np.load(sync) if sync.is_file() else np.array([])
