#!/bin/bash
# To run this script, type 'sbatch submit_job.slurm' in the terminal.
# Then look in the output folder for the logs that matches the job ID number

#SBATCH --job-name=data_analysis # This is the name of the job
#SBATCH --partition=normal #short
#SBATCH --ntasks=1
#SBATCH --mem-per-cpu=150G #8G
#SBATCH --time=5-0:0:0 #3:0:0
#SBATCH --output=output/%j.out # This is the name of the file where print statements are sent
#SBATCH --error=output/%j.err # This is the name of the file where error messages are sent
#SBATCH --mail-user=emelonakos@mgh.harvard.edu
#SBATCH --mail-type=end

# Some important variables to check (Can be removed later)
echo '---PROCESS RESOURCE LIMITS---'
ulimit -a
echo '---SHARED LIBRARY PATH---'
echo $LD_LIBRARY_PATH
echo '---APPLICATION SEARCH PATH:---'
echo $PATH
echo '---SLURM Parameters:---'
printenv | grep '^SLURM'
echo '---LOADED MODULES:---'
module list
echo '---SHELL:---'
echo $SHELL
echo '---HOSTNAME:---'
hostname
echo '---GROUP MEMBERSHIP (files are created in the first group listed):---'
groups
echo '---DEFAULT FILE PERMISSIONS (UMASK):---'
umask
echo '---CURRENT WORKING DIRECTORY:---'
pwd
echo '---DISK SPACE QUOTA---'
df .
echo '---TEMPORARY SCRATCH FOLDER ($TMPDIR):---'
echo $TMPDIR

# Add your job command here
# Before submitting a job to run this code on the cluster, you must activate your conda environment, since the environment is installed in my user directory!
# I.e., This command should be run before submitting the script: conda activate miniscope_EEG

# python --version # This can help confirm that the previous command has been run, because otherwise the command below will start Python 2.

python ~/data_analysis_code/experiment_analysis/process_entire_miniscope_recording.py $SLURM_JOBID
