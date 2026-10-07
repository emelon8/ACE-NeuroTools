"""
UCLA V4 Miniscope Data Manager
"""

import os
from pathlib import Path
from typing import Any

import numpy as np

from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
from aceneurotools.shared.path_finder import PathFinder


class OnixMiniscopeDataManager(MiniscopeDataManager):
    """
    Handles UCLA V4 Miniscope data formats (start-time_*_miniscope.csv, ucla-miniscope-v4-clock_*.raw).
    """

    suffix: str  # recording suffix parsed from start-time_<suffix>_miniscope.csv

    @classmethod
    def can_handle(cls, directory: str | Path) -> bool:
        """Returns True if V4 miniscope format files are found."""
        dir_path = Path(directory)
        if not dir_path.exists():
            return False
        return len(list(dir_path.rglob("start-time_*_miniscope.csv"))) > 0

    def _get_miniscope_metadata(self) -> dict[str, Any]:
        """
        Reads start-time_*_miniscope.csv to extract recording parameters.
        """
        print("Reading UCLA V4 miniscope metadata...")

        metadata: dict[str, Any] = {}
        if self.metadata is None or "calcium imaging directory" not in self.metadata:
            print("Warning: Metadata or calcium imaging directory missing. Proceeding with empty metadata.")
            return metadata

        csv_files = PathFinder.find(str(self.metadata["calcium imaging directory"]), suffix=".csv", prefix="start-time")
        # Filter for miniscope specifically
        miniscope_files: list[Any] = []
        if isinstance(csv_files, list):
            miniscope_files = [f for f in csv_files if "miniscope" in str(f)]
        elif csv_files is not None:
            miniscope_files = [csv_files] if "miniscope" in str(csv_files) else []

        if not miniscope_files:
            print("Warning: Could not find start-time_..._miniscope.csv. Proceeding with empty metadata.")
            return metadata

        start_time_path = str(miniscope_files[0])
        self.suffix = os.path.basename(start_time_path).split("_")[1]  # e.g. start-time_0_miniscope.csv -> 0

        dt: Any = {
            "names": ("time", "acq_clk_hz", "block_read_sz", "block_write_sz"),
            "formats": ("datetime64[us]", "u4", "u4", "u4"),
        }
        try:
            meta_arr = np.genfromtxt(start_time_path, delimiter=",", dtype=dt, skip_header=0)
            metadata["recordingStartTime"] = str(meta_arr["time"])
            metadata["AcquisitionClockHz"] = float(meta_arr["acq_clk_hz"])
        except Exception as e:
            print(f"Failed to parse ucla miniscope start-time csv: {e}")

        return metadata

    def _get_timestamps(self) -> tuple[np.ndarray, list[int]]:
        """
        Reads ucla-miniscope-v4-clock_*.raw to generate timestamp array.
        Also calculates `self.metadata['frameRate']` based on dt.
        """
        if self.metadata is None or "calcium imaging directory" not in self.metadata:
            raise ValueError("Metadata or calcium imaging directory missing. Cannot load timestamps.")

        clock_files = PathFinder.find(
            str(self.metadata["calcium imaging directory"]), suffix=".raw", prefix="ucla-miniscope-v4-clock"
        )
        if not clock_files:
            raise FileNotFoundError("Could not find ucla-miniscope-v4-clock_*.raw file.")

        if isinstance(clock_files, list):
            clock_path = str(clock_files[0])
        else:
            clock_path = str(clock_files)

        print(f"Loading UCLA V4 Miniscope hardware clock from {clock_path}...")

        # Clock is 64-bit uint
        clock_data = np.fromfile(clock_path, dtype=np.uint64)

        acq_freq = self.metadata.get("AcquisitionClockHz", 250000000.0)  # default fallback

        # Convert clock ticks to seconds
        time_stamps = clock_data / acq_freq
        frame_numbers = list(range(len(time_stamps)))

        # Estimate framerate dynamically
        if self.metadata is not None:
            if len(time_stamps) > 1:
                dt_avg = np.mean(np.diff(time_stamps))
                if dt_avg > 0:
                    self.metadata["frameRate"] = 1.0 / dt_avg
                    print(f"Estimated framerate: {self.metadata['frameRate']} fps")
                else:
                    self.metadata["frameRate"] = 30.0  # fallback
            else:
                self.metadata["frameRate"] = 30.0

        return time_stamps, frame_numbers

    def _get_miniscope_events(self) -> dict[str, list[str] | np.ndarray]:
        """
        Import events, e.g. from port-status_*_miniscope.csv if necessary.
        """
        # Right now testing has port-status_0_miniscope.csv
        # Let's extract any basic triggers as events, placeholder.
        events: dict[str, Any] = {"timestamps": [], "labels": []}
        return events

    def sync_timestamps(
        self, ephys_dm: Any | None = None, channel_name: str | None = None, **kwargs: Any
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        Since ONIX hardware inherently synchronizes using a unified hardware clock,
        we do not need to do TTL alignment. We simply return the already-aligned hardware timestamps.
        """
        print("ONIX timestamps are natively synchronized via hardware clock. Returning native timestamps.")

        # low_confidence_periods is empty for native syncing
        low_confidence_periods = np.empty((0, 2))

        # We already extracted time_stamps in load_attributes()
        if hasattr(self, "time_stamps") and self.time_stamps is not None:
            tCaIm = self.time_stamps
        else:
            tCaIm, _ = self._get_timestamps()

        return tCaIm, low_confidence_periods
