# Experiment-Analysis

Code for the Melonakos Lab of Neuroscience at Brigham Young University

## Description

This project facilitates the analysis of several input streams of data from experiments on rats.

### Classes

The foundation of the project lies on the following classes
* DataManager - (base class) - Represents a specific experiment with metadata loaded from a corresponding line_num in "experiments.csv" and "analysis_params.csv".  
* EphysDataManager(DataManager) - uses the metadata in DataManager, a file path for example, to load in ephys data.  Uses BlockProcessor.
* BlockProcessor - takes a Neo block object and converts it to desired Channel objects
* Channel - (data object) - Has attributes: name: string, signal: np.array, sampling_rate: int, time_vector: np.array, signal_filtered: np.array
* 

experiment - (base class) - Refers to "experiments.csv" and "analysis_params.csv" to get file paths and metadata about an experiment, indexed by a line number.
* ULCAMiniscope - Processes input stream from the miniscope, enabled by calcium flourescence.
* NeuralynxEphys - Processes input stream from the EEG.
* miniscopeEphys - Processes simultaneous miniscope and EEG data.

  
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
* You'll need to download files from box (they're massive, so only download those you need) into some directory on your computer,then change all file paths in experiments.csv to match the one on your local computer.  We recommend maintaining as similar a project structure as possible (e.g. change Box/Brown/K99/miniscope_data/test/R220606/2022_07_21/14_40_42 to /Users/lukerichards/Desktop/K99/miniscope_data/test/R220606/2022_07_21/14_40_42	via a find and replace command)

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
