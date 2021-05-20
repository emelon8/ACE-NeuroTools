# -*- coding: utf-8 -*-
"""
Created on Thu May 20 10:03:53 2021

@author: Katherine
"""

# Python program to demonstrate
# command line arguments
 
 
import sys

 
# total arguments
n = len(sys.argv)
print("Total arguments passed:", n)
 
# Arguments passed
print("\nName of Python script:", sys.argv[0])
 
print("\nArguments passed:", end = " ")
for i in range(1, n):
    print(sys.argv[i], end = " ")
    
