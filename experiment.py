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
    def __init__(self, lineNum, filename='experiments.csv'):
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

            
    def saveObj(self, filename=None, includeSubjectID=False, includeTimeStamp=False, jobID=''):
        """Save the class instance to a pickled file.
        FILENAME is the name of the pickled file the data is saved to."""
        if filename == None:
            subjectID = ''
            time = ''
            if includeSubjectID:
                subjectID = self.experiment['id']
            if includeTimeStamp:
                time = str(numpy.datetime64('now')).replace(":","-")
            fileToStore = open(jobID + subjectID + "_" + os.path.splitext(str(self.__class__)[:-2])[-1][1:] + "_" + time + '.pickle', 'wb')
        else:
            fileToStore = open(filename, 'wb')
        pickle.dump(self, fileToStore)
        fileToStore.close()
        

