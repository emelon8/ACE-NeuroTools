# -*- coding: utf-8 -*-
"""
Created on Mon Dec 11 19:56:26 2023

@author: ericm

This script creates and saves dF/F movies for specified files.
"""

import miniscope

expNums = [90]#, 93, 95, 97, 103, 107, 108]

for k in expNums:
    obj = miniscope.UCLAMiniscope(k)
    
    CaMovies = ['0.avi','1.avi','2.avi','3.avi','4.avi']
    
    obj.importCaMovies(CaMovies)
    
    obj.preprocessCaMovies(crop=True)
    
    newMovie = (obj.movie + 0.000001).computeDFF(method='delta_f_over_f')
    
    newMovie[0].save(obj.experiment['calcium imaging directory'] + '/Miniscope/0to4.tif',compress=9)