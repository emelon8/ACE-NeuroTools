# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 09:36:36 2020

@author: eric
"""

import csv
import pickle
import os.path
import numpy

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
        try:
            self.experiment['zero time (s)'] = float(self.experiment['zero time (s)'])
        except:
            self.experiment['zero time (s)'] = 0
        
        self.jobID = jobID # used for naming output files
    
    def importAnalysisParams(self, lineNum, filename):
        """Import parameters for calcium movie analysis using CaImAn."""
        analysisParamsCSV = []
        with open(filename, newline='') as s:
            reader = csv.reader(s)
            for row in reader:
                analysisParamsCSV.append(row)

        # Make a dictionary with each of the columns in the CSV file
        self._analysisParamsDict = {}
        for k, columnTitle in enumerate(analysisParamsCSV[0]):
            try:
                self._analysisParamsDict[columnTitle] = analysisParamsCSV[lineNum][k]
            except IndexError:
                self._analysisParamsDict[columnTitle] = None
            else:
                # Fix the types of different parameters if they're not supposed to be strings
                if (self._analysisParamsDict[columnTitle] == 'False') or (
                        self._analysisParamsDict[columnTitle] == 'True'):
                    self._analysisParamsDict[columnTitle] = bool(self._analysisParamsDict[columnTitle])
                elif (self._analysisParamsDict[columnTitle] == 'None') or (not self._analysisParamsDict[columnTitle]):
                    self._analysisParamsDict[columnTitle] = None
                elif (self._analysisParamsDict[columnTitle][0] == '('):
                    convertParamTuple = []
                    for k, c in enumerate(
                            self._analysisParamsDict[columnTitle].replace('(', '').replace(')', '').replace(' ',
                                                                                                            '').split(
                                    ',')):
                        if c.isnumeric():
                            convertParamTuple.append(int(c))
                    self._analysisParamsDict[columnTitle] = tuple(convertParamTuple)
                elif self._analysisParamsDict[columnTitle].isdecimal():
                    self._analysisParamsDict[columnTitle] = int(self._analysisParamsDict[columnTitle])
                elif ('.' in self._analysisParamsDict[columnTitle]) and ( self._analysisParamsDict[columnTitle].split('.')[0] == "" and
                self._analysisParamsDict[columnTitle].split('.')[1].isdecimal()) or (( self._analysisParamsDict[columnTitle].split('.')[0] != "" and
                self._analysisParamsDict[columnTitle].split('.')[0].isdecimal()) and ( not self._analysisParamsDict[columnTitle].split('.')[1].isalpha())):
                    self._analysisParamsDict[columnTitle] = float(self._analysisParamsDict[columnTitle])


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
                time = str(numpy.datetime64('now')).replace(":","-")
            fileToStore = open(jobID + subjectID + "_" + os.path.splitext(str(self.__class__)[:-2])[-1][1:] + "_" + time + '.pickle', 'wb')
        else:
            fileToStore = open(filename, 'wb')
        pickle.dump(self, fileToStore)
        fileToStore.close()
        

