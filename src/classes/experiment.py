# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 09:36:36 2020

@author: eric

A general experiment class for all data analysis. This class takes a CSV file
that contains all of the details of the experiment itself. It also can load a
CSV file that contains parameters for the analysis of the experiment. Finally,
the class has a method to save a pickled version of the object for further
analysis.
"""

import csv
import pickle
import os.path
import numpy as np
from json import loads
from datetime import datetime

import os
from pathlib import Path

import sys

#project_root = Path(__file__).resolve().parent.parent
#sys.path.append(str(project_root))

class experiment:
    """Base class for experiment analysis.
    LINENUM is the line number of the experiment on the csv file.
    FILENAME is the filename of the CSV file.
    JOBID is a string that will be appended to the end of the filenames of saved files."""
    def __init__(self, lineNum, filename='data/experiments.csv', jobID=''):
        self.lineNum = lineNum
    


        # Dynamically locate the project root
        project_root = Path(__file__).resolve().parent.parent.parent

        # Resolve the full path to the file
        full_path = project_root / filename

        # Check if the file exists
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")
        
        print('Reading experiment details from ' + str(full_path) + '...')
        experimentCSV = []
        with open(full_path, newline='') as s:
            reader = csv.reader(s)
            for row in reader:
                experimentCSV.append(row)
        
        # Make a dictionary with each of the columns in the CSV file
        self.experiment = {}
        for k, columnTitle in enumerate(experimentCSV[0]):
            try:
                self.experiment[columnTitle] = experimentCSV[lineNum][k]
            except:
                break
        
        self.jobID = jobID  # Used for naming output files




    def importAnalysisParams(self, filename='data/analysis_parameters.csv'):
        """Import parameters for calcium movie analysis using CaImAn.
        FILENAME is the filename of the CSV file."""
        # Dynamically locate the file
        project_root = Path(__file__).resolve().parent.parent.parent
        full_path = project_root / filename
        
        # Store the resolved path
        self.analysisParamsFilename = str(full_path)
        
        # Import the CSV file
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")
            
        print('Reading analysis parameters from ' + os.path.abspath(filename) + '...')
        analysisParamsCSV = []
        with open(self.analysisParamsFilename, newline='') as s:
            reader = csv.reader(s)
            for row in reader:
                analysisParamsCSV.append(row)

        # Make a dictionary with each of the columns in the CSV file
        self._analysisParamsDict = {}
        for k, columnTitle in enumerate(analysisParamsCSV[0]):
            try:
                self._analysisParamsDict[columnTitle] = analysisParamsCSV[self.lineNum][k]
            except IndexError:
                self._analysisParamsDict[columnTitle] = None
            else:
                # Fix the types of different parameters if they're not supposed to be strings
                try:
                    self._analysisParamsDict[columnTitle] = loads(self._analysisParamsDict[columnTitle])                                # string to an int, float, or list
                    if columnTitle == 'date (YYMMDD)':
                        self._analysisParamsDict[columnTitle] = datetime.strptime(str(self._analysisParamsDict[columnTitle]), '%y%m%d') # int to datetime
                except:
                    try:
                        self._analysisParamsDict[columnTitle] = float(self._analysisParamsDict[columnTitle])                            # string to float if above fails
                    except:
                        if self._analysisParamsDict[columnTitle] == 'False' or self._analysisParamsDict[columnTitle] == 'True' or self._analysisParamsDict[columnTitle] == 'FALSE' or self._analysisParamsDict[columnTitle] == 'TRUE':
                            self._analysisParamsDict[columnTitle] = bool(self._analysisParamsDict[columnTitle].capitalize() == 'True')               # string to boolean
                        elif (self._analysisParamsDict[columnTitle] == 'None') or (not self._analysisParamsDict[columnTitle]):
                            self._analysisParamsDict[columnTitle] = None                                                                # 'None' or empty cell to None
                        elif (str(self._analysisParamsDict[columnTitle])[0] == '('):
                            convertParamTuple = []
                            for k, c in enumerate(self._analysisParamsDict[columnTitle].replace('(', '').replace(')', '').replace(' ','').split(',')):
                                if c.isnumeric():
                                    convertParamTuple.append(int(c))
                            self._analysisParamsDict[columnTitle] = tuple(convertParamTuple)                                            # string to tuple
                

    def saveObj(self, filename=None, includejobID=False, includeSubjectID=False, includeTimeStamp=False):
        """Save the class instance to a pickled file.
        FILENAME is the name of the pickled file the data is saved to."""
        if filename == None:
            jobID = ''
            subjectID = ''
            time = ''
            if includejobID:
                jobID = self.jobID
            if includeSubjectID:
                subjectID = self.experiment['id']
            if includeTimeStamp:
                time = str(np.datetime64('now')).replace(':','-')
            fileToStore = open(jobID + subjectID + "_" + os.path.splitext(str(self.__class__)[:-2])[-1][1:] + '_' + time + '.pickle', 'wb')
        else:
            fileToStore = open(filename, 'wb')
        pickle.dump(self, fileToStore)
        fileToStore.close()
        

