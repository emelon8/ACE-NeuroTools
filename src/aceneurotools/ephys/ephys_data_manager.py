import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypeVar, cast

import numpy as np
from scipy.signal import hilbert  # type: ignore

from aceneurotools.ephys.channel import Channel

T = TypeVar("T", bound="EphysDataManager")


class EphysDataManager(ABC):
    """
    Abstract base class for ephys data managers.
    Manages the import of raw ephys data and processes it into channels.
    Stores the processed channels in self.channels, where the key is the channel name and the value is a Channel object.
    """

    _registry: list[type["EphysDataManager"]] = []
    logger: logging.Logger
    channels: dict[str, Channel]
    ephys_block: Any

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls not in cls._registry:
            cls._registry.append(cls)

    @classmethod
    def create(cls: type[T], ephys_directory: str | Path, **kwargs: Any) -> T:
        """Factory method to create the appropriate subclasses for the directory."""
        if ephys_directory is None:
            raise ValueError("ephys_directory must be provided to create() factory.")

        for subclass in cls._registry:
            if subclass.can_handle(ephys_directory):
                return cast(T, subclass(ephys_directory=ephys_directory, **kwargs))

        raise ValueError(f"No EphysDataManager subclass found that can handle directory: {ephys_directory}")

    @classmethod
    @abstractmethod
    def can_handle(cls, directory: str | Path) -> bool:
        """Return True if this class can handle the format in the given directory."""
        pass

    def __init__(
        self,
        ephys_directory: str | Path | None = None,
        auto_import_ephys_block: bool = True,
        auto_process_block: bool = True,
        auto_compute_phases: bool = True,
        level: str | int = "CRITICAL",
        channels: list[str] | None = None,
        remove_artifacts: bool = False,
    ) -> None:
        """Initialize the EphysDataManager and optionally load data.

        Args:
            ephys_directory: Path to directory containing ephys data.
            auto_import_ephys_block: If True, automatically import raw ephys data.
            auto_process_block: If True, automatically process block into channels.
            auto_compute_phases: If True, automatically compute phase for all channels.
            level: Logging level string.
            channels: Channel names to process (optional).
            remove_artifacts: If True, apply artifact removal during processing.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(level)

        self.channels = {}  # Processed channels
        self.ephys_block = None  # Raw data storage

        if auto_import_ephys_block:
            assert ephys_directory is not None
            self.import_ephys_block(ephys_directory)

        if auto_process_block:
            self.process_ephys_block_to_channels(channels=channels, remove_artifacts=remove_artifacts)

        if auto_compute_phases:
            self.compute_phases_all_channels()

    @abstractmethod
    def import_ephys_block(self, ephys_directory: str | Path) -> None:
        """Load raw ephys data from disk."""
        pass

    @abstractmethod
    def process_ephys_block_to_channels(
        self, channels: list[str] | None = None, remove_artifacts: bool = False
    ) -> None:
        """Process raw ephys data into Channel objects."""
        pass

    @abstractmethod
    def get_sync_timestamps(self, channel_name: str | None = None) -> np.ndarray:
        """
        Extract raw hardware sync timestamps from an ephys channel.
        To be overridden by subclasses.
        """
        pass

    def compute_phases_all_channels(self) -> None:
        """Compute instantaneous phase for all loaded channels."""
        for key, value in self.channels.items():
            self.channels[key] = self.compute_phase(value)

    def compute_phase(self, channel: Channel) -> Channel:
        """Compute instantaneous phase using Hilbert transform.

        Args:
            channel: Channel object with signal data.

        Returns:
            Channel object with phases attribute populated.
        """
        print(f"Computing phase for {channel.name}")
        analytic_signal = hilbert(channel.signal)
        channel.phases = np.angle(analytic_signal)
        return channel

    def filter_ephys(
        self,
        channel_name: str,
        n: int = 2,
        cut: float | list[float] | np.ndarray = [0.5, 4],
        ftype: str = "butter",
        btype: str = "bandpass",
        replace_signal: bool = True,
    ) -> np.ndarray:
        """Apply a frequency filter to a channel's signal.

        Supports FIR and Butterworth filter types with configurable
        cutoff frequencies and band types.

        Args:
            channel_name: Name of the channel to filter.
            n: Filter order (Butterworth) or number of taps (FIR).
            cut: Cutoff frequency or [low, high] for bandpass.
            ftype: Filter type ('butter', 'butterworth', or 'fir').
            btype: Band type ('low', 'high', 'band', 'bandpass').
            replace_signal: If True, overwrite signal; else store in signal_filtered.

        Returns:
            Filtered signal as 1D numpy array.

        Raises:
            ValueError: If channel is not found in loaded channels.
        """
        # self.logger.info('Filtering ' + channel_name + ' with a(n) ' + ftype + ' filter ...')
        try:
            channel: Channel = self.channels[channel_name]
        except KeyError:
            raise ValueError("Channel not found in data_manager. Please import the data first.")

        print(f"Filtering the ephys signal: {channel_name}")

        filtered_data = self._filter_data(
            channel.signal, n=n, cut=cut, ftype=ftype, btype=btype, fs=channel.sampling_rate
        )

        if replace_signal:
            self.channels[channel_name].signal = filtered_data
        else:
            self.channels[channel_name].signal_filtered = filtered_data

        return filtered_data

    def get_channels(self) -> dict[str, Channel]:
        """Return dictionary of all processed channels."""
        return self.channels

    def get_channel(self, channel_name: str) -> Channel:
        """Return a single channel by name.

        Args:
            channel_name: Name of the channel to retrieve.
        """
        return self.channels[channel_name]

    @staticmethod
    def _filter_data(
        data: np.ndarray,
        n: int,
        cut: float | list[float] | np.ndarray,
        ftype: str,
        btype: str,
        fs: float,
        bodePlot: bool = False,
    ) -> np.ndarray:
        """Apply FIR or Butterworth filter to signal data.

        Thin wrapper around :func:`aceneurotools.shared.signal_processing.filter_signal`,
        which is the single canonical implementation.  All bug fixes and
        improvements should be made there.

        Args:
            data: 1D numpy array of signal values.
            n: Filter order (Butterworth) or number of taps (FIR).
            cut: Cutoff frequency or [low, high] for bandpass.
            ftype: Filter type ('fir', 'butter', or 'butterworth').
            btype: Band type ('low', 'high', 'band', 'bandpass', etc.).
            fs: Sampling frequency in Hz.
            bodePlot: If True, plot Bode diagram of filter response.

        Returns:
            Filtered signal as 1D numpy array.
        """
        from aceneurotools.shared.signal_processing import filter_signal

        return filter_signal(data, n=n, cut=cut, ftype=ftype, btype=btype, fs=fs, bode_plot=bodePlot)
