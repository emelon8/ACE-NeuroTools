#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 30 12:14:48 2023

@author: lab
"""

import ephys
import csv
import numpy as np
from datetime import datetime

obj = ephys.NeuralynxEphys(104)

def loadAgentAnalyzer(filename='AS3ExportData.csv'):
    filepath = obj.experiment['ephys directory'] + '/' + filename
    agentAnalyzerCSV = []
    with open(filepath, newline='') as s:
        reader = csv.reader(s)
        for row in reader:
            agentAnalyzerCSV.append(row)
            
    # Make a dictionary with each of the columns in the CSV file
    agentAnalyzer = {}
    for k, columnTitle in enumerate(agentAnalyzerCSV[2]):
        try:
            agentAnalyzer[columnTitle] = []
            if columnTitle == 'Date':
                for h in range(3,len(agentAnalyzerCSV)):
                    dateAndTimeString = agentAnalyzerCSV[h][k] + ' ' + agentAnalyzerCSV[h][k+1]
                    tempDateTime = datetime.strptime(dateAndTimeString, "%m/%d/%Y %I:%M:%S %p")
                    agentAnalyzer[columnTitle].append(tempDateTime)
            elif columnTitle != 'Time':
                for h in range(3,len(agentAnalyzerCSV)):
                    agentAnalyzer[columnTitle].append(agentAnalyzerCSV[h][k])
                if (columnTitle == ' AA FI') or (columnTitle == ' O2 FI'):
                    agentAnalyzer[columnTitle] = np.array(agentAnalyzer[columnTitle], dtype=float)
        except:
            break
        
    return agentAnalyzer

aa = loadAgentAnalyzer()

obj.importEphysData()
