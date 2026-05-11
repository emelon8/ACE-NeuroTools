"""ACE-Neuro ephys subpackage.

Public API
----------
EphysDataManager     — Abstract base + factory for loading raw ephys recordings.
Channel              — Plain data container (signal, sampling_rate, events, phases).
NeuralynxDataManager — Neuralynx .ncs / .nev reader (via Neo).
RHS2116DataManager   — Intan RHS2116 binary reader (via Neo).
BlockProcessor       — Converts a Neo Block into Channel objects.
ChannelWorker        — Per-channel analysis: plot, spectrogram, phase histogram.
Visualizer           — Standalone matplotlib plotting for Channel + Spectrogram.
Spectrogram          — Data container for PSD matrix + time/frequency vectors.

Note: NeuralynxIO, NeuralynxRawIO, etc. (Neo internals) are *not* re-exported;
import them directly from aceneurotools.ephys.neuralynx_data_manager if needed.
"""

from aceneurotools.ephys.block_processor import BlockProcessor
from aceneurotools.ephys.channel import Channel
from aceneurotools.ephys.channel_worker import ChannelWorker
from aceneurotools.ephys.ephys_data_manager import EphysDataManager
from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager
from aceneurotools.ephys.rhs2116_data_manager import RHS2116DataManager
from aceneurotools.ephys.spectrogram import Spectrogram
from aceneurotools.ephys.visualizer import Visualizer

__all__ = [
    "EphysDataManager",
    "Channel",
    "NeuralynxDataManager",
    "RHS2116DataManager",
    "BlockProcessor",
    "ChannelWorker",
    "Visualizer",
    "Spectrogram",
]
