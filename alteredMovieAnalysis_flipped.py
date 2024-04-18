#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 27 11:46:44 2023
explanation script for movie values changing when resaved
@author: Rachael
"""

import caiman as cm
import numpy as np
import matplotlib.pyplot as plt

movie = cm.load('../../experimental_data/miniscope_data/sleep/R230706A/2023_08_15/14_38_44/Miniscope/0.avi')
movie.save('0_resaved.avi')
resaved = cm.load('../../experimental_data/miniscope_data/sleep/R230706A/2023_08_15/14_38_44/Miniscope/0_resaved.avi')

y1 = movie[0][:,280]
y2 = resaved[0][:,280]

plt.figure(num =1)
plt.plot(np.arange(len(y1)),y1, color = 'r')
plt.plot(np.arange(len(y2)),y2, color = 'b')
plt.ylim(-10, 300)
plt.xlabel('row number')
plt.ylabel('movie value from column in middle of lens')