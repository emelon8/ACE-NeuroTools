# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 09:36:36 2020

@author: eric
"""

import csv
import pickle
import os.path
import numpy as np
from json import loads
from datetime import datetime

class experiment:
    """Base class for experiment analysis.
    LINENUM is the line number of the experiment on the csv file.
    FILENAME is the filename of the csv file."""
    def __init__(self, lineNum, filename='experiments.csv', jobID=''):
        self.lineNum = lineNum
        # Import the CSV file 
        experimentCSV = []
        with open(filename, newline='') as s:
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
        
        self.jobID = jobID # used for naming output files
    
    def importAnalysisParams(self, filename='analysis_parameters.csv'):
        """Import parameters for calcium movie analysis using CaImAn."""
        analysisParamsCSV = []
        self.analysisParamsFilename = filename
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
                        if (self._analysisParamsDict[columnTitle] == 'False') or (self._analysisParamsDict[columnTitle] == 'True'):
                            self._analysisParamsDict[columnTitle] = bool(self._analysisParamsDict[columnTitle] == 'True')               # string to boolean
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
                time = str(np.datetime64('now')).replace(":","-")
            fileToStore = open(jobID + subjectID + "_" + os.path.splitext(str(self.__class__)[:-2])[-1][1:] + "_" + time + '.pickle', 'wb')
        else:
            fileToStore = open(filename, 'wb')
        pickle.dump(self, fileToStore)
        fileToStore.close()
        

