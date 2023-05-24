# -*- coding: utf-8 -*-
"""
Created on Mon May 22 17:32:15 2023

@author: Eric
"""

import miniscope

    
obj = miniscope.UCLAMiniscope(35)

obj.findMovieFilePaths()

h = []

for k in range(obj.movieFilePaths):
    obj.importCaMovies(k)
    h.append(len(obj.movie))