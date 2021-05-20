# -*- coding: utf-8 -*-
"""
Created on Thu May 20 10:51:32 2021

@author: Katherine
"""

import sys, getopt

def main(argv):
   filename = ''
   outputfile = ''
   try:
      opts, args = getopt.getopt(argv,"ho:f:",["ofile=","fname="])
   except getopt.GetoptError:
       print ('test.py -o <outputfile> -f <filename>')
       sys.exit(2)
   for opt, arg in opts:
      if opt == '-h':
          print ('test.py -o <outputfile> -f <filename>')
          sys.exit()
      elif opt in ("-o", "--ofile"):
          outputfile = arg
      elif opt in ("-f", "--fname"):
         filename = arg
   print ('Output file is ', outputfile)
   print ('File name is ', filename)

if __name__ == "__main__":
   main(sys.argv[1:])