# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

Run this script from your LSF script in order to kick off a job.

Before submitting a job to run this code on the cluster, you must activate your conda environment, since the environment is installed in my user directory!
"""

import sys
jobID = ''
if len(sys.argv) > 1:
    jobID = sys.argv[1]

import os
os.chdir('/PHShome/em609/data_analysis_code/experiment_analysis') # for running on ERISTwo
os.system('python ~/data_analysis_code/experiment_analysis/scratch.py ' + jobID)