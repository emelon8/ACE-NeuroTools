#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 29 10:53:53 2023

@author: lab
"""

import numpy as np
import ephys

obj = ephys.NeuralynxEphys(49)
obj.importEphysData()
obj.importNeuralynxEvents(analogSignalImported=True)

np.where(obj.NeuralynxEvents['labels'][:5]=='start')[0]
np.where(obj.NeuralynxEvents['labels']=='start dex infusion and heating pad')[0]
obj.NeuralynxEvents['timestamps'][37122]
np.where(obj.NeuralynxEvents['labels']=='righted')[0]
obj.NeuralynxEvents['timestamps'][279131]
