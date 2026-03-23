#!/bin/bash
# To run this script, type 'sbatch submit_job.slurm' in the terminal.
# Then look in the output folder for the logs that matches the job ID number

#SBATCH --job-name=data_analysis # This is the name of the job
#SBATCH --partition=m12
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=output/%j.out # This is the name of the file where print statements are sent
#SBATCH --error=output/%j.err # This is the name of the file where error messages are sent
#SBATCH --mail-user=jaa120@student.byu.edu
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
module load miniforge3
conda activate caiman_env

echo '---PYTHON BEING USED---'
which python
python --version


# Add your job command here
# Before submitting a job to run this code on the cluster, you must activate your conda environment, since the environment is installed in my user directory!
# I.e., This command should be run before submitting the script: conda activate miniscope_EEG

# python --version # This can help confirm that the previous command has been run, because otherwise the command below will start Python 2.

cd ~/emelon_analysis/experiment_analysis
python -m src2.miniscope.miniscope_pipeline --line-num 96 --headless # $SLURM_JOBID


