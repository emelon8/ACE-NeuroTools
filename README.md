# Experiment-Analysis

Code for the Melonakos Lab of Neuroscience at Brigham Young University

## Description

This project facilitates the analysis of several input streams of data from experiments on rats.

### Classes

The foundation of the project lies on the following classes:

*   **ExperimentDataManager** - (Base class) Manages the import and storage of metadata and analysis parameters. Loads metadata from `experiments.csv` and parameters from `analysis_params.csv`.
*   **EphysDataManager** - (Inherits from `ExperimentDataManager`) Manages the import and processing of raw electrophysiology (Neuralynx) data. Uses `BlockProcessor` to convert raw data into `Channel` objects.
*   **MiniscopeDataManager** - (Inherits from `ExperimentDataManager`) Manages raw Miniscope data import, storage, and metadata (timestamps, frame numbers). Prepares data for processing.
*   **MiniscopeProcessor** - Handles the processing pipeline for Miniscope data, including motion correction, parameter optimization, and CNMFE (calcium trace extraction).
*   **BlockProcessor** - Takes a Neo block object (raw ephys data) and processes it into individual `Channel` objects, handling artifact removal and organization.
*   **Channel** - (Data object) Represents a single ephys channel. Attributes include: `name` (string), `signal` (np.array), `sampling_rate` (int), `time_vector` (np.array), and `signal_filtered` (np.array).

  
![uml](https://github.com/user-attachments/assets/4b97fc47-240f-49c4-859e-65b2736f2d24)


### Scripts
A plethora of scripts for various miniprojects can be found under src.scripts

## Getting Started

### Dependencies

#### If you are on mac, do not install CaImAn through anaconda.  The default solver, libmamba, creates complex dependency errors with the liblapack package.  Instead, we highly encourage the use of miniforge3

You can install the .yml file found in the package, but that comes with many unneeded packages.  Or you can install the following through miniforge3 or your preferred package manager:

* CaImAn
* FreeSimpleGui
* Neo


### Installing

* Copy Repo:
```
    git clone https://github.com/emelon8/experiment_analysis.git
```
* Navigate to repo location on local machine
* Activate virtual environment
* Download project as editable package:
```
    pip install -e .
```

### Data importing setup

* EEG, Calcium imaging, and other channel data is stored in the lab Box account
* The experiment class reads experiments.csv to find the file paths for such data.
* **Manual Download:** You'll need to download files from box (they're massive, so only download those you need) into some directory on your computer,then change all file paths in experiments.csv to match the one on your local computer.  We recommend maintaining as similar a project structure as possible (e.g. change Box/Brown/K99/miniscope_data/test/R220606/2022_07_21/14_40_42 to /Users/lukerichards/Desktop/K99/miniscope_data/test/R220606/2022_07_21/14_40_42	via a find and replace command)
* **Automated Download:** Alternatively, you can use the `src2/shared/file_downloader.py` script to automate downloads for specific experiments.
    *   **Setup:** Copy `src2/shared/BLANK_box_credentials.py` to `src2/shared/box_credentials.py` and follow the instructions within to configure your Box authentication. Be sure not to publish your box_credentials.py file anywhere. 
    *   **Usage:** Open `src2/shared/file_downloader.py` and modify the `verify_file_by_line` call in the `__main__` block to specify the target experiment (line number) and data type. Then run the script to download the required files to the paths defined in your `experiments.csv`.

## Help

Good luck :)

## Authors

Eric Melonakos
Luke Richards

## Version History

* 0.1
    * Initial Release

## License

No license you can steal our code :)

## Old Comments

An analysis job is run by the following command in the command line: "python [path to scratch.py] [optional jobID]", e.g., "python Dropbox/Documents/Brown_Lab/data_analysis_code/experiment_analysis test_larger_gSig"

When running the code on the ERISTwo cluster at MGH, first load your conda environment before submitting the SLURM script. The command within the SLURM script that runs your code is "python ~/data_analysis_code/experiment_analysis/<filename of script> $SLURM_JOBID"
