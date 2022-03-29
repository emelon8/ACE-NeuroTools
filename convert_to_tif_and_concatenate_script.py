# -*- coding: utf-8 -*-
"""
Created on Fri Nov  6 16:07:33 2020

@author: Eric

For use in converting select .avi files to .tif files for preliminary analyses using Mesmerize.
"""

import miniscope

obj = miniscope.miniscope('D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R211022/2021_11_02/10_58_59/Miniscope/metaData.json', lineNum=8)

obj.convertCaMovies()