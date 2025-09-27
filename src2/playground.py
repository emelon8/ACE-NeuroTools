#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun 29 14:44:53 2025

@author: nathan
"""
import caiman as cm
mov = cm.load('/Users/nathan/Desktop/K99/miniscope_data/dexmedetomidine/R230706A/2023_09_04/15_06_16/Miniscope/0.avi')
time = mov.mean(axis=(1,2))
