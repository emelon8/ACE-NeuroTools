#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Feb  2 11:20:05 2025
 
@author: lukerichards
"""
import csv
import json
import os
import caiman as cm
from caiman.base.movies import movie
import numpy as np
import matplotlib.pyplot as plt
from src2.shared.path_finder import PathFinder
from src2.shared.experiment_data_manager import ExperimentDataManager

class MiniscopeDataManager(ExperimentDataManager):
    """Manages raw Miniscope data import and storage. Processes data via Processor."""
    
    def __init__(self, line_num, auto_import_data=True):
        super().__init__(line_num)
        self.time_stamps: list = None
        self.frame_numbers: list = None
        self.path_finder = PathFinder()

        if (auto_import_data):
            self.load_attributes()
            

    def load_attributes(self):
        self.metadata.update(self._get_miniscope_metadata()) # add miniscope metadata to overall metadata
        self.time_stamps, self.frame_numbers = self._get_timestamps()  # import timestamps and frame numbers
        self.movie: movie = self._get_movies()  # import calcium imaging data




    def download_ca_movie(self, processing_step: str = '') -> None:
        """
        Saves the calcium movie currently stored in self.movie.
        
        For a single movie file (or a single-element list in self.movieFilePaths), the new filename is built 
        by concatenating self.jobID, the original filename, and the processing_step.
        
        For multiple movie files, the new filename is constructed using the numeric portions extracted from 
        the first and last filenames, separated by an underscore, with processing_step appended to the last portion.
        
        After saving, self.movieFilePaths is updated to the new filename.
        """
        try:

            # Generate the new filename based on the original filename(s) and the processing step.

            if not isinstance(self.movieFilePaths, list) or (isinstance(self.movieFilePaths, list) and len(self.movieFilePaths) == 1):
                # If it's a list with one element, take that element.
                movie_path = self.movieFilePaths[0] if isinstance(self.movieFilePaths, list) else self.movieFilePaths
                dir_path, full_filename = os.path.split(movie_path)
                name, ext = os.path.splitext(full_filename)
                new_filename = os.path.join(dir_path, f"{self.jobID}{name}{processing_step}{ext}")
            else:
                # For multiple movie files, use the first and last file names.
                dir_path, first_full_filename = os.path.split(self.movieFilePaths[0])
                first_name, ext = os.path.splitext(first_full_filename)
                _, last_full_filename = os.path.split(self.movieFilePaths[-1])
                last_name, _ = os.path.splitext(last_full_filename)

                # Extract numeric parts from the filenames.
                filenum_first = self._extract_numeric_suffix(first_name)
                filenum_last = self._extract_numeric_suffix(last_name) + processing_step

                new_filename = os.path.join(dir_path, f"{self.jobID}{filenum_first}_{filenum_last}{ext}")






            # Save the movie using the new filename.
            self.movie.save(new_filename, compress=0)
            #self.movieFilePaths = new_filename
            print(f"Movie saved as '{new_filename}'")

        except AttributeError:
            print('No movies have been imported.')




    def convert_ca_movies(self, filenames=None, new_file_type='.tif', join_movies=False, metadata_convert=True):
        """
        Convert calcium movies from one type to another. File types must be supported by CaImAn.
        
        The new filename(s) is based on the first filename in 'filenames', with new_file_type appended.
        'join_movies' determines whether all movie files in 'filenames' are combined into a single movie,
        or whether each file is converted separately.
        
        If 'filenames' is None, the method will attempt to load filenames from self.movieFilePaths.
        """
        print("Converting movies...")
        original_filenames = filenames  # Preserve the original argument
        error_videos = []

        # If no filenames provided, try to load from self.movieFilePaths
        if filenames is None:
            if hasattr(self, 'movie'):
                print("self.movie exists, but no filenames were provided. Loading filenames from self.experiment['calcium imaging directory']")
            self.find_movie_file_paths()  # Assumes this method updates self.movieFilePaths
            filenames = self.movieFilePaths

        # Ensure filenames is a list
        if not isinstance(filenames, list):
            filenames = [filenames]

        # Use the first filename as a basis for the new filename.
        base_new_filename = os.path.splitext(filenames[0])[0]

        # If self.movie exists and no filenames were explicitly provided, use the existing movie.
        if hasattr(self, 'movie') and original_filenames is None:
            new_filename = f"{base_new_filename}{new_file_type}"
            self.movie.save(new_filename, compress=0)
        else:
            if join_movies:
                # Join movies: load the movie chain and save as a single new movie.
                try:
                    movies = cm.load_movie_chain(filenames)
                    new_filename = f"{base_new_filename}{new_file_type}"
                    movies.save(new_filename)
                except Exception as e:
                    print(f"Error converting joined movies: {e}")
                    error_videos.extend(filenames)
            else:
                # Convert each movie separately.
                for filename in filenames:
                    try:
                        # If the file doesn't exist, assume it might be in a default Miniscope directory.
                        if not os.path.isfile(filename):
                            default_dir = os.path.join(self.experiment['calcium imaging directory'], 'Miniscope')
                            filename = os.path.join(default_dir, filename)
                        movie = cm.load(filename)
                        new_filename = f"{os.path.splitext(filename)[0]}{new_file_type}"
                        movie.save(new_filename, compress=0)
                    except Exception as e:
                        print(f"Error converting movie '{filename}': {e}")
                        error_videos.append(filename)

        if metadata_convert:
            self._metaDataConverter()

        if error_videos:
            print(f"ERRORS with: {error_videos}")
            print("Consider investigating")


    def _metaDataConverter(self):  
        # Suggestion: it might be good to start combining the metaDatas and marking them with the animalID or some experiment identifier (not sure how this program will work if you have a lot of different videos/metaData)
        fileExts = self._find_metadata_paths()
        for fileExt in fileExts:
            with open(fileExt) as f:
                data = json.loads(f.read())
                if 'animalID' in data:
                    ext = fileExt.replace('\\metaData.json', '\\Miniscope\\metaData.json')
                    animalID = data['animalID']
                    timeStamp = data['recordingStartTime']
                    year = str(timeStamp['year'])
                    month = str('%02d' % timeStamp['month'])
                    day = str('%02d' % timeStamp['day'])
                    second = str('%02d' % timeStamp['second'])
                    minute = str('%02d' % timeStamp['minute'])
                    hour = str('%02d' % timeStamp['hr'])
                    date = year + month + day + '_' + hour + minute + second
                    with open(ext) as d:
                        data2 = json.loads(d.read())
                        if 'frameRate' in data2:
                            try:
                                frameRate = float(data2['frameRate'])
                            except ValueError:
                                frameRate = float(data2['frameRate'].replace('FPS', ''))
                        jdict = {'origin': animalID, 'fps': frameRate, 'date': date,
                                    'orig_meta': [data, data2]}
                        jsonFile = json.dumps(jdict, indent=4)
                        newFileName = ext.replace('\\metaData.json', '\\metaDataTif.json')
                        n = open(newFileName, 'w')
                        n.write(jsonFile)
                        n.close()







    def _get_miniscope_metadata(self) -> dict:
        """
        Imports miniscope metadata from a JSON file or multiple located at the paths returned by self._find_metadata_paths().
        Converts the 'frameRate' value to a float (removing any 'FPS' suffix if necessary).

        Returns:
            Dict: The metadata dictionary with a converted 'frameRate' value if present and converts any whole numbers to ints.
        """
        metadata_paths = self._find_metadata_paths()
        print(f"Reading metadata from {metadata_paths}...")
        for metadata_path in metadata_paths:
            try:
                with open(metadata_path, 'r') as file:
                    metadata = json.load(file)
            except (IOError, json.JSONDecodeError) as e:
                raise RuntimeError(f"Error reading or parsing metadata file '{metadata_path}': {e}")
    
            # If 'frameRate' exists, try to convert it to a float
            if 'frameRate' in metadata:
                value = metadata['frameRate']
                try:
                    metadata['frameRate'] = float(value)
                except ValueError:
                    # Remove 'FPS' and any surrounding whitespace, then convert again
                    cleaned_value = value.replace('FPS', '').strip()
                    try:
                        metadata['frameRate'] = float(cleaned_value)
                    except ValueError:
                        raise ValueError(f"Unable to convert frameRate value '{value}' to float.")
        return metadata



    def _get_timestamps(self):
         #print('Reading miniscope software timestamps from ' + os.path.abspath(timeStampsFilename) + '...')
        file_path = self._find_timestamps_path()
        time_stamps = []
        frame_numbers = []
        with open(file_path, newline='') as t:
            next(t)
            reader = csv.reader(t)
            for row in reader:
                frame_numbers.append(int(row[0]))
                time_stamps.append(float(row[1]))
        time_stamps = np.divide(np.asarray(time_stamps), 1000)  # convert from ms to s
        return time_stamps, frame_numbers


    def _get_movies(self, filenames=None):
        """Import calcium imaging data. Not necessary if using processCaMovies().
        FILENAMES can be a single movie file or a list of movie files (in the order that you want them). If FILENAMES doesn't point to a file (either absolute or relative path from the PWD), it will append the path to the calcium imaging directory to the front of the filename."""
        if filenames == None:
            filenames = self._find_movie_file_paths()

        # Convert PosixPath objects to strings if necessary.
        if isinstance(filenames, list):
            filenames = [str(f) for f in filenames]
        else:
            filenames = str(filenames)

        # Load a movie chain if there are multiple files, otherwise load a single movie.
        if type(filenames) is list:
            print(filenames)
            movie = cm.load_movie_chain(filenames)
        else:
            movie = cm.load(filenames)

        return movie
    



    @property
    def _calcium_imaging_directory(self):
        """Returns the directory where calcium imaging data is stored."""
        return self.metadata['calcium imaging directory']

    def _find_file_paths(self, suffix: str, prefix: str = ""):
        """Generalized helper to find files with the given suffix and prefix."""
        return self.path_finder.find(
            directory=self._calcium_imaging_directory,
            suffix=suffix,
            prefix=prefix
        )

    def _find_metadata_paths(self) -> list:
        """Finds and returns the metadata JSON file path."""
        return self._find_file_paths(suffix=".json", prefix="metaData")

    def _find_timestamps_path(self) -> str:
        """Finds and returns the timestamps CSV file path."""
        return self._find_file_paths(suffix=".csv", prefix="timeStamps")[0]

    def _find_movie_file_paths(self) -> list:
        """Finds and returns the list of movie file paths (.avi)."""
        return self._find_file_paths(suffix=".avi")
        
    def _extract_numeric_suffix(self, filename: str) -> str:
        """
        Extracts and returns the substring of filename starting from the first digit.
        If no digit is found, returns the original filename.
        """
        for i, char in enumerate(filename):
            if char.isdigit():
                return filename[i:]
        return filename
        