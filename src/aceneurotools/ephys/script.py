from aceneurotools.ephys.channel_worker import ChannelWorker
from aceneurotools.ephys.neuralynx_data_manager import NeuralynxDataManager
from aceneurotools.shared.experiment_data_manager import ExperimentDataManager
import logging




logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---- Configuration ----
# Set these to your project and data directories:
project_path = "/home/reed/lab/examples/ephys_project"
# data_path = "/path/to/your/raw_data"  # Uncomment if data lives elsewhere

line_num = 97
logging_level = "INFO"
remove_artifacts = False
filter_type = None  # if desired, enter the type, eg "butter"
filter_range = [0.5, 4]
plot_channel = True
plot_spectrogram = True
channel_name = 'PFCLFPvsCBEEG'

experiment_data_manager = ExperimentDataManager(line_num, project_path=project_path, logging_level=logging_level)
ephys_directory = experiment_data_manager.get_ephys_directory()
ephys_data_manager = NeuralynxDataManager(ephys_directory, auto_import_ephys_block=True, auto_process_block=False)
ephys_data_manager.process_ephys_block_to_channels(remove_artifacts=remove_artifacts, channels=[channel_name])
channel = ephys_data_manager.get_channel(channel_name)
channel_worker = ChannelWorker(channel)
channel_worker.plot_spectrogram(plot_events=True)   