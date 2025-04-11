#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
from src2.shared.paths import ANALYSIS_PARAMS
from src2.shared.misc_functions import updateCSVCell
from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.miniscope_preprocessor import MiniscopePreprocessor
from src2.ephys.visualizer import Visualizer
from typing import List


class MiniscopeAPI:
    """Main workflow class."""

    def __init__(self):
        pass
    
    def run(
            self, 
            line_num,
            crop = False,
            square = False
            ):
        
        # Create instance of EphysDataManager, process the block into channels
        self.dm = MiniscopeDataManager(line_num, auto_import_data=True)
        self.p = MiniscopePreprocessor(self.dm.movie)

        coords: str
        crop_type: str
        if square:
            coords = self.dm.analysis_params['crop']
            crop_type = 'square'
        else:
            coords = self.dm.analysis_params['crop_square']
            crop_type = 'crop'
        
        # unpack coords
        coords_dict = {
            'x0': coords[0],
            'y0': coords[1],
            'x1': coords[2],
            'y1': coords[3]
            }
        
        movie, processing_steps, coords = self.p.preprocess_movie(coords_dict, crop=crop)
        updateCSVCell( data=coords, columnTitle=crop_type, lineNum=line_num, csvFile=ANALYSIS_PARAMS)




        projections = self.p.computeProjections()
        print(f'Projections: {projections}')


if __name__ == "__main__":      
    # run the API
    api = MiniscopeAPI()
    api.run(
        line_num=97,
        crop=True
    )
        
    
    
    
    
    
    
    
    
    
    
    
    