# -*- coding: utf-8 -*-
"""
Created on Fri Aug 14 11:25:19 2020

@author: Eric

Before submitting a job to run this code on the cluster, you must activate your conda environment, since the environment is installed in my user directory!
"""

import os
os.chdir('/PHShome/em609/data_analysis_code/experiment_analysis') # for running on ERISTwo
os.system('python scratch.py')