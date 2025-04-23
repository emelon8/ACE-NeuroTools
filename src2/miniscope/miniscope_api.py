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
from src2.miniscope.movie_io import MovieIO


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
        self.data_manager = MiniscopeDataManager(line_num, auto_import_data=True)
        miniscope_dir_path = self.data_manager.metadata['calcium imaging directory']
        self.preprocessor = MiniscopePreprocessor(self.data_manager.movie)

        coords: str
        crop_type: str
        if square:
            coords = self.data_manager.analysis_params['crop']
            crop_type = 'square'
        else:
            coords = self.data_manager.analysis_params['crop_square']
            crop_type = 'crop'
        
        # unpack coords
        coords_dict = { 'x0': coords[0], 'y0': coords[1], 'x1': coords[2], 'y1': coords[3] }
        
        file_path, coords = self.preprocessor.preprocess_movie(coords_dict, miniscope_dir_path, crop=False)
        updateCSVCell( data=coords, columnTitle=crop_type, lineNum=line_num, csvFile=ANALYSIS_PARAMS)
        
        movie = MovieIO.load_movie(miniscope_dir_path, file_path)
        print(movie)


        # file_path = MovieIO.save_movie(self.dm.movie, miniscope_dir_path, "unpreprocessed_movie")

        # projections = self.p.computeProjections()
        # print(f'Projections: {projections}')


    # def nathans_function(self, line_num):
    #     self.dm = MiniscopeDataManager(line_num, auto_import_data=True, avi_range= [5])
    #     miniscope_dir_path = self.dm.metadata['calcium imaging directory']
    #     file_path = MovieIO.save_movie(self.dm.movie, miniscope_dir_path, "unpreprocessed_movie")
    #     processor()


if __name__ == "__main__":      
    # run the API
    api = MiniscopeAPI()
    api.run(
        line_num=97,
        crop=True
    )
        
    
    
    
    
    
    
    
    
    
    
    
    