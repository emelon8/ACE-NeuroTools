# Experiment-Analysis
The directories listed in experiments.csv and analysis_parameters.csv assume you have a directory structure where the code is stored in (and run from, i.e., it's the working directory) "some_base_directory/data_analysis_code/experiment_analysis/", and the data is stored in "some_base_directory/experimental_data/miniscope_data/..." and "some_base_directory/experimental_data/Neuralynx_data/...".

An analysis job is run by the following command in the command line: "python [path to scratch.py] [optional jobID]", e.g., "python Dropbox/Documents/Brown_Lab/data_analysis_code/experiment_analysis test_larger_gSig"

When running the code on the ERISTwo cluster at MGH, first load your conda environment before submitting the SLURM script. The command within the SLURM script that runs your code is "python ~/data_analysis_code/experiment_analysis/<filename of script> $SLURM_JOBID"
