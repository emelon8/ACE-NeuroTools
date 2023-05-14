# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 08:43:50 2020

@author: eric
"""

import csv
import io
import os.path
import warnings

import experiment
import numpy as np
from scipy.signal import detrend
import matplotlib.pyplot as plt

plt.rcParams['svg.fonttype'] = 'none'
import caiman as cm
import misc_functions
import sys
import json
import base64
import PySimpleGUI as sg


class UCLAMiniscope(experiment.experiment):
    """This is the class definition for handling data from the UCLA Miniscope V4 (1-photon calcium imaging).
    Used with version 1.11 of the DAQ software released by the UCLA Miniscope group."""

    # @staticmethod
    # def main():
    #     program = miniscope(lineNum=16)
    #     #program.findMovieFilePaths()
    #     # cutFile = []
    #     #for file in program.movieFilePaths:
    #      #   cutFile.append(int(file[114:-4]))
    #     #sortIdx = np.argsort(np.array(cutFile))
    #     #program.movieFilePaths = list(np.array(program.movieFilePaths)[sortIdx])
    #     program.importCaMovies(['D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/0.avi','D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/1.avi','D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/2.avi','D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/3.avi','D:/Dropbox/Documents/Brown_Lab/experimental_data/miniscope_data/test/R220606/2022_07_21/14_40_42/Miniscope/4.avi'])
    #     program.preprocessCaMovies(crop=True)
    #     # program.processCaMovies(inspectMotionCorrection=True, runCNMFE=False)
    
#%% Methods for importing experiment info, metadata, events, and analysis parameters
    def __init__(self, lineNum=None, filename='experiments.csv', filenameMiniscope='metaData.json', analysisFilename='analysis_parameters.csv', jobID=''):
        if lineNum != None:
            super().__init__(lineNum=lineNum, filename=filename, jobID=jobID)
        else:
            self.experiment = {}

        # Import the metadata files and add to the experiment dictionary

        try:
            metaDataPaths = misc_functions._findFilePaths(self.experiment['calcium imaging directory'], fileExtensions='.json',
                                                          fileStartsWith='metaData')
            for path in metaDataPaths:
                with open(path) as m:
                    data = json.loads(m.read())
                    for key in data:
                        if key == 'frameRate':
                            try:
                                self.experiment[key] = float(data[key])
                            except ValueError:
                                self.experiment[key] = float(data[key].replace('FPS', ''))
                                if not self.experiment[key].isdecimal():
                                    raise ValueError(f"{self.experiment['id']} from {self.experiment['date']} has no framerate")
                        else:
                            self.experiment[key] = data[key]

                    m.close()
        except AttributeError:
            pass
        '''
        self.experiment['Miniscope settings filename'] = filenameMiniscope
        with open(filenameMiniscope) as s:
            self.experiment.update(load(s))
       
        settingsFilename = os.path.split(filenameMiniscope)     # FIXME take a look to see if this can be deleted
        with open('Miniscope/' + settingsFilename[1]) as s: 
            self.experiment.update(load(s)) 
        '''
        if 'calcium imaging directory' not in self.experiment:
            self.experiment['calcium imaging directory'] = os.path.abspath(os.path.dirname(filenameMiniscope))

        if lineNum != None:
            self.importAnalysisParams(lineNum, analysisFilename)
        else:
            self._analysisParamsDict = {}

        timeStampsFilename = misc_functions._findFilePaths(self.experiment['calcium imaging directory'], '.csv', 'timeStamps', removeFile=False, printPath=False, fileAndDirectory=False)

        if len(timeStampsFilename) == 1:
            timeStampsFilename = timeStampsFilename[0]
        else:
            raise ValueError('More than one timeStamps files found')
        self.timeStamps = []
        self.frameNum = []
        with open(timeStampsFilename, newline='') as t:
            next(t)
            reader = csv.reader(t)
            for row in reader:
                self.frameNum.append(int(row[0]))
                self.timeStamps.append(float(row[1]))
        self.timeStamps = np.divide(np.asarray(self.timeStamps), 1000)  # convert from ms to s
        # self.timeStamps = np.divide((np.asarray(self.timeStamps) - self.timeStamps[0]), 1000)  # start timestamps at 0 and convert from ms to s


    def importMiniscopeEvents(self):
        """Import calcium imaging experiment events."""
        miniscopeEventsFilename = misc_functions._findFilePaths(self.experiment['calcium imaging directory'], '.csv', 'notes', removeFile=False, printPath=False, fileAndDirectory=False)

        if len(miniscopeEventsFilename) == 1:
            miniscopeEventsFilename = miniscopeEventsFilename[0]
        else:
            raise ValueError('More than one notes files found')
        
        self.miniscopeEvents = {}
        self.miniscopeEvents['timestamps'] = []
        self.miniscopeEvents['labels'] = []
        with open(miniscopeEventsFilename, newline='') as t:
            next(t)
            reader = csv.reader(t)
            for row in reader:
                self.miniscopeEvents['timestamps'].append(int(row[0]))
                self.miniscopeEvents['labels'].append(row[1])
        self.miniscopeEvents['timestamps'] = np.divide(np.asarray(self.miniscopeEvents['timestamps']), 1000)  # converts from ms to s


#%% Methods for importing and saving calcium movies
    def findMovieFilePaths(self, directory=None, fileExtensions='.avi',
                           fileStartsWith='', removeFile=False, printPath=False,
                           fileAndDirectory=False):
        """Makes a list of the full paths of all movie files in DIRECTORY.
        FILEEXTENSIONS is a string of the file extension or a list or tuple with multiple file extensions."""
        if directory == None:
            directory = self.experiment['calcium imaging directory']
        self.movieFilePaths = misc_functions._findFilePaths(directory, fileExtensions, fileStartsWith,
                                                            removeFile, printPath, fileAndDirectory)


    def importCaMovies(self, filenames=None, fileExtensions='.avi'):
        """Import calcium imaging data. Not necessary if using processCaMovies().
        FILENAMES can be a single movie file or a list of movie files (in the order that you want them)."""
        if filenames == None:
            self.findMovieFilePaths(fileExtensions=fileExtensions)
            filenames = self.movieFilePaths
        else:
            self.movieFilePaths = filenames
        if type(filenames) is str:
            self.movie = cm.load(filenames)
        else:
            self.movie = cm.load_movie_chain(filenames)


    def convertCaMovies(self, filenames=None, newFileType='.tif', joinMovies=False, metaDataConvert=True):
        """Convert calcium movies from one type to another. File types must be supported by CaImAn.
        The new filename(s) is the same as the first filename in FILENAMES, with NEWFILETYPE appended to the end.
        JOINMOVIES determines whether all of the movie files in FILENAMES are converted to a single new movie, or whether they are saved in len(FILENAMES) movies."""
        print('Converting movies...')
        filenamesArg = filenames
        difVideos = []
        if (filenames == None):
            if 'movie' in self.__dir__():
                print('self.movie exists, but there are no filenames associated with it. Loading filenames from self.experiment[\'directory\']')
            self.findMovieFilePaths()
            filenames = self.movieFilePaths
        if type(filenames) is not list:
            filenames = [filenames]
        if joinMovies:
            if ('movie' in self.__dir__()) and (filenamesArg == None):
                self.movie.save(os.path.splitext(filenames[0])[0] + newFileType)
            else:
                movies = cm.load_movie_chain(filenames)
                movies.save(os.path.splitext(filenames[0])[0] + newFileType)
        else:
            if ('movie' in self.__dir__()) and (filenamesArg == None):
                self.movie.save(os.path.splitext(filenames[0])[0] + newFileType)
            else:
                for k in range(len(filenames)):
                    try:
                        movie = cm.load(filenames[k])
                        movie.save(os.path.splitext(filenames[k])[
                                       0] + newFileType)  ###########FIXME maybe use the saveCaMovie method here and elsewhere in this method?
                    except:
                        difVideos.append(filenames[k])
        if metaDataConvert:
            self._metaDataConverter()
        if len(difVideos) != 0:
            print('ERRORS with: ' + str(difVideos))
            print('Consider investigating')


    def _metaDataConverter(
            self):  # Suggestion: it might be good to start combining the metaDatas and marking them with the animalID or some experiment identifier (not sure how this program will work if you have a lot of different videos/metaData)
        directory = self.experiment['calcium imaging directory']
        fpath = misc_functions._findFilePaths(directory=directory, fileExtensions='.json', fileStartsWith='metaData')
        for fileExt in fpath:
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


    def saveCaMovie(self, processingStep=''):
        """Saves the calcium movie that is currently in SELF.MOVIE."""
        try:
            if (type(self.movieFilePaths) is not list) or ((type(self.movieFilePaths) is list) and (len(self.movieFilePaths)==1)):
                if type(self.movieFilePaths) is list:
                    self.movieFilePaths = self.movieFilePaths[0]
                filepath, filename = os.path.split(self.movieFilePaths)
                filename, filetype = os.path.splitext(filename)
                filename += processingStep
                newFilename = filepath + '/' + self.jobID + filename + filetype
                self.movie.save(newFilename, compress=9)
            else:
                filepath, filenameFirst = os.path.split(self.movieFilePaths[0])
                filenameFirst, filetype = os.path.splitext(filenameFirst)
                _, filenameLast = os.path.split(self.movieFilePaths[-1])
                filenameLast, _ = os.path.splitext(filenameLast)
                filenumFirstIdx = [f.isdecimal() for f in filenameFirst]
                filenumLastIdx = [f.isdecimal() for f in filenameLast]
                filenumFirst = filenameFirst[np.where(filenumFirstIdx)[0][0]:]
                filenumLast = filenameLast[np.where(filenumLastIdx)[0][0]:]
                filenumLast += processingStep
                newFilename = filepath + '/' + self.jobID + filenumFirst + '_' + filenumLast + filetype
                self.movie.save(newFilename, compress=9)
            self.movieFilePaths = newFilename
        except AttributeError:
            print('No movies have been imported.')


#%% Methods for preprocessing calcium movies, including computing the projections, cropping, denoising, detrending, and computing dF/F
    def computeProjections(self):
        """Calculates the projections of self.movie and stores the result in self.projections."""
        try:
            Max = np.amax(self.movie, axis=0)
            Std = np.std(self.movie, axis=0)
            Min = np.amin(self.movie, axis=0)
            Mean = np.mean(self.movie, axis=0)
            Med = np.median(self.movie, axis=0)
            Range = Max - Min
            self.projections = {"Max": Max, "Std": Std, "Min": Min, "Mean": Mean, "Med": Med, "Range": Range}
        except:
            print('Projection cannot be done, as no movie has been loaded. Loading movie from self.movieFilePaths and proceeding with projection...')
            if 'movie' not in self.__dir__():
                self.importCaMovies()
            Max = np.amax(self.movie, axis=0)
            Std = np.std(self.movie, axis=0)
            Min = np.amin(self.movie, axis=0)
            Mean = np.mean(self.movie, axis=0)
            Med = np.median(self.movie, axis=0)
            Range = Max - Min
            self.projections = {"Max": Max, "Std": Std, "Min": Min, "Mean": Mean, "Med": Med, "Range": Range}


    def preprocessCaMovies(self, saveMovie=True, crop=False, cropGUI=False, denoise=False, detrend=False, dFoverF=False):
        """Run all preprocessing steps in one method, using their default options."""
        try:
            self.movie.shape
        except:
            print('Prepocessing cannot be done, as no movie has been loaded. Loading movie from self.movieFilePaths and proceeding with preprocessing...')
            if 'movie' not in self.__dir__():
                self.importCaMovies()
        newFileName = ''
        if crop:
            self._crop(self.movie, GUI=cropGUI)
            newFileName += '_cropped'
        if denoise:
            self.denoiseCaMovie(saveMovie=False)
            newFileName += '_denoised'
        if detrend:
            self.detrendCaFluorescence(saveMovie=False)
            newFileName += '_detrend'
        if dFoverF:
            self.computedFoverF(saveMovie=False)
            newFileName += '_dFoverF'
        if saveMovie:
            self.saveCaMovie(processingStep=newFileName)


    def _cropMovie(self, crop_top=0, crop_bottom=0, crop_left=0, crop_right=0, crop_begin=0, crop_end=0) -> None:
        """
        Crop movie (inline). Code altered from caiman.movie.crop https://github.com/flatironinstitute/CaImAn/blob/dev/caiman/base/movies.py, which throws an error when it is run.
        Args:
            crop_top/crop_bottom/crop_left,crop_right: Distance from edge of frame in pixels

            crop_begin/crop_end: Start Frame to end Frame
        """
        t, h, w = self.movie.shape
        tempArray = self.movie[crop_begin:t - crop_end, crop_top:h - crop_bottom, crop_left:w - crop_right]
        return tempArray


    def _crop(self, movie, GUI=False):
        """
        Takes previously save coordinates from analysis params.csv and optionally displays a GUI to allow the user to select
        new ones or crop at the previously saved site. This function then saves the new cropping coords and writes them
        back into analysis params and also the new size of self.movie
        """
        # Get all projections
        self.computeProjections()
        # Grab saved crop coords from .csv file that has been read
        if self._analysisParamsDict['crop'] is None:
            self.cropCoordinates = {'x0': 0, 'x1': 0, 'y0': 0, 'y1': 0}
        else:
            self.cropCoordinates = {
                'x0': self._analysisParamsDict['crop'][0],
                'y0': self._analysisParamsDict['crop'][1],
                'x1': self._analysisParamsDict['crop'][2],
                'y1': self._analysisParamsDict['crop'][3]
                }

        if GUI:
            self._cropWindow(movie)

        croppedMovie = None
        if self.cropCoordinates['x1'] and self.cropCoordinates['x0'] and self.cropCoordinates['y1'] and self.cropCoordinates['y0'] != 0:
            if self.cropCoordinates['x1'] > self.cropCoordinates['x0']:
                # rectangle was drawn from Left -> Right
                if self.cropCoordinates['y1'] > self.cropCoordinates['y0']:
                    #Bottom L -> Upper R
                    cropBottom = self.cropCoordinates['y0']
                    cropTop = movie.shape[1] - self.cropCoordinates['y1']
                    cropLeft = self.cropCoordinates['x0']
                    cropRight = movie.shape[2] - self.cropCoordinates['x1']
                    croppedMovie = self._cropMovie(crop_right=cropRight, crop_top=cropTop, crop_bottom=cropBottom, crop_left=cropLeft)
                else:
                    #Upper L -> Bottom R
                    cropBottom = self.cropCoordinates['y1']
                    cropTop = movie.shape[1] - self.cropCoordinates['y0']
                    cropLeft = self.cropCoordinates['x0']
                    cropRight = movie.shape[2] - self.cropCoordinates['x1']
                    croppedMovie = self._cropMovie(crop_right=cropRight, crop_top=cropTop, crop_bottom=cropBottom,
                                                   crop_left=cropLeft)
            else:
                # rectangle was drawn from R -> L
                if self.cropCoordinates['y1'] > self.cropCoordinates['y0']:
                    # Bottom R -> Upper L
                    cropBottom = self.cropCoordinates['y0']
                    cropTop = movie.shape[1] - self.cropCoordinates['y1']
                    cropLeft = self.cropCoordinates['x1']
                    cropRight = movie.shape[2] - self.cropCoordinates['x0']
                    croppedMovie = self._cropMovie(crop_right=cropRight, crop_top=cropTop, crop_bottom=cropBottom,
                                                   crop_left=cropLeft)
                else:
                    # Upper R -> Bottom L
                    cropBottom = self.cropCoordinates['y1']
                    cropTop = movie.shape[1] - self.cropCoordinates['y0']
                    cropLeft = self.cropCoordinates['x1']
                    cropRight = movie.shape[2] - self.cropCoordinates['x0']
                    croppedMovie = self._cropMovie(crop_right=cropRight, crop_top=cropTop, crop_bottom=cropBottom,
                                                   crop_left=cropLeft)
        #protects against no cropping
        if croppedMovie is not None:
            self.movie = croppedMovie
            if GUI:
                # update analysis params to reflect new movie size
                misc_functions.updateCSVCell(data=f'({self.movie.shape[1]} ,{self.movie.shape[2]})', columnTitle="dims",
                                                        lineNum=self.lineNum, csvFile=self.analysisParamsFilename)

                # update analysis params to have new crop coords
                misc_functions.updateCSVCell(
                    data=f'({self.cropCoordinates["x0"]},{self.cropCoordinates["y0"]}, {self.cropCoordinates["x1"]},{self.cropCoordinates["y1"]})',
                    columnTitle="crop", lineNum=self.lineNum, csvFile=self.analysisParamsFilename)


    def _updateCoords(self, window, x0, y0, x1, y1):
        """
        Update cropping rectangle information
        """
        if x0 is not None:
            self.cropCoordinates['x0'] = x0
        if y0 is not None:
            self.cropCoordinates['y0'] = y0
        if x1 is not None:
            self.cropCoordinates['x1'] = x1
        if y1 is not None:
            self.cropCoordinates['y1'] = y1
        window['-START-'].update(f'Start: ({x0}, {y0})')
        window['-STOP-'].update(f'Stop: ({x1}, {y1})')
        window['-BOX-'].update(f'Box: ({abs(x1 - x0 + 1)}, {abs(y1 - y0 + 1)})')


    def _updateImage(self, graph, max=False, min=False, STD=False, mean=False, median=False, range=False, cmap='viridis'):
        """
        Redraws the desired projection(image) to the pysimplegui graph object
        """
        # adds projection to GUI
        pic_IObytes = io.BytesIO()
        if max:
            plt.imsave(pic_IObytes, self.projections['Max'], format='png', cmap=cmap)
        elif min:
            plt.imsave(pic_IObytes, self.projections['Min'], format='png', cmap=cmap)
        elif STD:
            plt.imsave(pic_IObytes, self.projections['Std'], format='png', cmap=cmap)
        elif mean:
            plt.imsave(pic_IObytes, self.projections['Mean'], format='png', cmap=cmap)
        elif median:
            plt.imsave(pic_IObytes, self.projections['Med'], format='png', cmap=cmap)
        elif range:
            plt.imsave(pic_IObytes, self.projections['Range'], format='png', cmap=cmap)
        plt.close()
        pic_IObytes.seek(0)
        pic_hash = base64.b64encode(pic_IObytes.read())
        # Draw image in graph
        graph.draw_image(data=pic_hash, location=(0, self.movie.shape[1]))


    def _cropWindow(self, movie):
        """
        Creates and handles all events for the pysimplegui cropping application
        """
        # define the window layout
        cmapOptions = ['viridis', 'jet', 'plasma', 'inferno', 'magma', 'cividis', 'Greys', 'Purples', 'Blues', 'Greens', 'Oranges', 'Reds',
                      'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
                      'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn', 'binary', 'gist_yarg', 'gist_gray', 'gray', 'bone',
                      'pink', 'spring', 'summer', 'autumn', 'winter', 'cool',
                      'Wistia', 'hot', 'afmhot', 'gist_heat', 'copper', 'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu', 'RdYlBu',
                      'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic', 'Pastel1', 'Pastel2', 'Paired', 'Accent', 'Dark2',
                      'Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b',
                      'tab20c']

        boxOptions = ['red/white', 'blue/white', 'red/yellow', 'blue/yellow', 'blue/green',
                      'green/yellow', 'red/green', 'green/white']

        layout = [[sg.Text('Max Projection', key='-TITLE-')],
                  [sg.Graph((movie.shape[2], movie.shape[1]), (0, 0), (movie.shape[1], movie.shape[2]), key='-GRAPH-', drag_submits=True, enable_events=True)],
                  [sg.Text("Start: None", key="-START-"), sg.Text("Stop: None", key="-STOP-"),
                   sg.Text("Box: None", key="-BOX-")],
                  [sg.Text("Projection Type:"), sg.Combo(['Max', 'Min', 'Mean', 'Median', 'STD', "Range"], key='-OPTION-', default_value='Max', readonly=True,
                            auto_size_text=True, enable_events=True)],
                  [sg.Text("CMAP:"), sg.Combo(cmapOptions, key='-CMAP-', default_value='viridis', readonly=True,
                            auto_size_text=True, enable_events=True)],
                  [sg.Text("Box Colors:"), sg.Combo(boxOptions, key='-COLORBOX-', default_value='red/white', readonly=True,
                                                    auto_size_text=True, enable_events=True)],
                  [sg.Button('Cancel', key="-CANCEL-"), sg.Button('Submit', key="-SUBMIT-")]]

        # create the form and show it without the plot
        window = sg.Window('CropGUI', layout, finalize=True, resizable=True,
                           element_justification='center', font='Helvetica 18')

        # add the plot to the window
        graph = window['-GRAPH-']
        x0, y0 = None, None
        colors = ['red', 'white']
        index = False
        box = None

        #adds image to window
        self._updateImage(graph, max=True)
        box = graph.draw_rectangle((self.cropCoordinates['x0'], self.cropCoordinates['y0']),
                                   (self.cropCoordinates['x1'], self.cropCoordinates['y1']),
                                   line_color=colors[index])

        while True:
            #controls events to update window
            event, values = window.read(timeout=100)

            if event == sg.WINDOW_CLOSED or event in '-CANCEL-':
                # Make sure that nothing gets cropped
                self.cropCoordinates['x0'] = 0
                self.cropCoordinates['y0'] = 0
                self.cropCoordinates['x1'] = 0
                self.cropCoordinates['y1'] = 0
                break

            #color of box options
            elif event in '-COLORBOX-':
                if values['-COLORBOX-'] == 'red/white':
                    colors = ['red', 'white']
                elif values['-COLORBOX-'] == 'blue/white':
                    colors = ['blue', 'white']
                elif values['-COLORBOX-'] == 'red/yellow':
                    colors = ['red', 'yellow']
                elif values['-COLORBOX-'] == 'blue/yellow':
                    colors = ['blue', 'yellow']
                elif values['-COLORBOX-'] == 'blue/green':
                    colors = ['blue', 'green']
                elif values['-COLORBOX-'] == 'green/yellow':
                    colors = ['green', 'yellow']
                elif values['-COLORBOX-'] == 'red/green':
                    colors = ['red', 'green']
                elif values['-COLORBOX-'] == 'green/white':
                    colors = ['green', 'white']
                # Redraw crop rectangle
                if box:
                    graph.delete_figure(box)
                index = not index
                box = graph.draw_rectangle((self.cropCoordinates['x0'], self.cropCoordinates['y0']),
                                           (self.cropCoordinates['x1'], self.cropCoordinates['y1']),
                                           line_color=colors[index])

            #Type of image options
            elif event in '-OPTION-':
                window['-TITLE-'].update(values['-OPTION-'] + " Projection")
                if values['-OPTION-'] == 'Max':
                    self._updateImage(graph, max=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Min':
                    self._updateImage(graph, min=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'STD':
                    self._updateImage(graph, STD=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Mean':
                    self._updateImage(graph, mean=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Median':
                    self._updateImage(graph, median=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Range':
                    self._updateImage(graph, range=True, cmap=values['-CMAP-'])
                # Redraw crop rectangle
                if box:
                    graph.delete_figure(box)
                index = not index
                box = graph.draw_rectangle((self.cropCoordinates['x0'], self.cropCoordinates['y0']),
                                           (self.cropCoordinates['x1'], self.cropCoordinates['y1']),
                                           line_color=colors[index])

            #CMAP of image
            elif event in '-CMAP-':
                if values['-OPTION-'] == 'Max':
                    self._updateImage(graph, max=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Min':
                    self._updateImage(graph, min=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'STD':
                    self._updateImage(graph, STD=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Mean':
                    self._updateImage(graph, mean=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Median':
                    self._updateImage(graph, median=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Range':
                    self._updateImage(graph, range=True, cmap=values['-CMAP-'])
                # Redraw crop rectangle
                if box:
                    graph.delete_figure(box)
                index = not index
                box = graph.draw_rectangle((self.cropCoordinates['x0'], self.cropCoordinates['y0']),
                                           (self.cropCoordinates['x1'], self.cropCoordinates['y1']),
                                           line_color=colors[index])

            elif event in '-SUBMIT-':
                break

            #drawing the box and getting x/y values
            elif event in '-GRAPH-':
                if (x0, y0) == (None, None):
                    x0, y0 = values['-GRAPH-']
                    if values['-GRAPH-'][0] < 0:
                        x0 = 0
                    if values['-GRAPH-'][0] > movie.shape[2]:
                        x0 = movie.shape[2]
                    if values['-GRAPH-'][1] < 0:
                        y0 = 0
                    if values['-GRAPH-'][1] > movie.shape[1]:
                        y0 = movie.shape[1]
                x1, y1 = values['-GRAPH-']
                if values['-GRAPH-'][0] < 0:
                    x1 = 0
                if values['-GRAPH-'][0] > movie.shape[2]:
                    x1 = movie.shape[2]
                if values['-GRAPH-'][1] < 0:
                    y1 = 0
                if values['-GRAPH-'][1] > movie.shape[1]:
                    y1 = movie.shape[1]
                self._updateCoords(window, x0, y0, x1, y1)
                if box:
                    graph.delete_figure(box)
                if None not in (x0, y0, x1, y1):
                    box = graph.draw_rectangle((x0, y0), (x1, y1), line_color=colors[index])
                    index = not index
            elif event.endswith('+UP'):
                 x0, y0 = None, None

        window.close()


    def denoiseCaMovie(self, saveMovie=True):
        """Loads a movie and removes both the horizontal bands (that slowly travel upwards) from the movie and the slow flicker of the entire image.
        SAVEMOVIE determines whether to save the filtered movie (with '_denoised' appended to the filename)."""
        mode = 'display'
        if saveMovie:
            mode = 'save'
        misc_functions.denoiseMovie(self.experiment['calcium imaging directory'], mode=mode, jobID=self.jobID) # TODO Currently doesn't save this info for later use


    def detrendCaFluorescence(self, saveMovie=True, detrendType='median', plotTrend=False):
        """Loads the calcium movie and detrends it based on the fluorescence of the entire movie.
        SAVEMOVE determines whether to save the debleached movie (with '_detrended' appended to the filename).
        DETRENDTYPE determines which method is used for detrending. 'median' debleaches by fitting a model to the median intensity.
        'linear' debleaches by linearly detrending the mean fluorescence, and includes subtracting the mean of the fluorescence over time."""
        if 'movie' not in self.__dir__():
            self.importCaMovies()
        if plotTrend:
            h, ax = misc_functions._prepAxes(xLabel='Frames', yLabel='Mean Fluorescence')
            ax.plot(np.mean(np.mean(self.movie, axis=1), axis=1), label='Original Data')
        if detrendType == 'linear':
            detrend(self.movie, axis=0, overwrite_data=True)
        elif detrendType == 'median':
            self.movie.debleach()
        else:
            print('detrendType is not a supported detrending method.')
        if plotTrend:
            ax.plot(np.mean(np.mean(self.movie, axis=1), axis=1), label='Detrended Data')
            ax.legend()
        if saveMovie:
            self.saveCaMovie(processingStep='_detrended')


    def computedFoverF(self, saveMovie=True, secsWindow=5, quantilMin=8, method='delta_f_over_sqrt_f'):
        """
        compute the dF/F or dF/sqrt(F) of the movie, or removes the baseline
        
        Args:
            secsWindow: length of the windows used to compute the quantile
            quantilMin : value of the quantile used to compute the movie baseline
            method='only_baseline','delta_f_over_f','delta_f_over_sqrt_f'
        Raises: 
            Exception 'Unknown method' if inputed method is not one of the
            three accepted methods
        """
        # adds ones to all pixel values because function does not take in non-positive values (including zero)
        self.movie, _ = cm.movie.computeDFF(self.movie+np.ones(np.shape(self.movie)), secsWindow, quantilMin, method)
        if saveMovie:
            self.saveCaMovie(processingStep='_dFoverF')


#%% Methods for processing calcium movies, including motion correction, CNMF-E, and deconvolution
    def processCaMovies(self, parallel=True, n_processes=12, motionCorrect=True, saveMotionCorrect=True, inspectMotionCorrection=False,
                        inspectCorrPNR=False, downsampleForCorrPNR=1, runCNMFE=True, saveCNMFEFilename='estimates.hdf5',
                        editComponents=False, deconvolve=False, saveProcessedData=False):
        """Preprocess calcium imaging data."""
        print('Processing movie...')
        if 'movieFilePaths' not in dir(self):
            self.findMovieFilePaths()
        self._analysisParamsDict['fnames'] = self.movieFilePaths
        self.optsCaImAn = cm.source_extraction.cnmf.params.CNMFParams(params_dict=self._analysisParamsDict)
        if parallel:
            print('Setting up cluster...')
            c, dview, nProcesses = cm.cluster.setup_cluster(backend='local', n_processes=n_processes, single_thread=False)
        else:
            dview = None
            nProcesses = 1
        if motionCorrect:
            self._motionCorrection(dview, saveMotionCorrect, inspectMotionCorrection)
        else:
            if saveMotionCorrect: #FIXME I'm not sure if the naming here works as expected...
                fileName = self.jobID
                if type(self.movieFilePaths) is str:
                    fileName += os.path.splitext(self.movieFilePaths)[0] + '_'
                else:
                    for file in self.movieFilePaths:
                        fileName += os.path.splitext(file)[0] + '_' #Changed so that the first part of memmap file is the filename rather than 'memmap'
                print('Saving memmapped file...')
                fname_new = cm.save_memmap(self.optsCaImAn.get('data', 'fnames'), base_name=fileName, order='C',
                                           border_to_0=0,
                                           dview=dview)  # if no motion correction just memory map the file
                self.optsCaImAn.change_params({'fnames': fname_new})

        if inspectCorrPNR or runCNMFE:
            Yr, dims_new, T = cm.load_memmap(self.optsCaImAn.get('data', 'fnames')[0])
            self.optsCaImAn.change_params({'dims': dims_new})
            self.images = Yr.T.reshape((T,) + dims_new, order='F')
            if inspectCorrPNR:
                self._corrPNR(inspectCorrPNR, downsampleForCorrPNR)
            if runCNMFE:
                self._CNMFE(nProcesses, dview=dview, saveCNMFEFilename=saveCNMFEFilename)
                if editComponents:
                    pass #FIXME point to the edit components GUI? Or maybe the removeComponents method?

        if deconvolve:
            self._deconvolve()

        if saveProcessedData:
            self.saveObj(includejobID=True, includeSubjectID=True, includeTimeStamp=True)

        cm.stop_server(dview=dview) #FIXME will this throw an error if it's not parallel? if so, uncomment the next two lines
        # if parallel:
        #     cm.stop_server(dview=dview)


    def _motionCorrection(self, dview=None, saveMotionCorrect=True, inspectMotionCorrection=True):
        """Use motion correction to correct for movement during the calcium movies."""
        print('Setting up motion correction object...')
        mc = cm.motion_correction.MotionCorrect(self.optsCaImAn.get('data', 'fnames'), dview=dview,
                                                **self.optsCaImAn.get_group('motion'))
        print('Motion correcting...')
        mc.motion_correct(save_movie=saveMotionCorrect)
        if self.optsCaImAn.get('motion', 'pw_rigid'):
            bord_px = np.ceil(np.maximum(np.max(np.abs(mc.x_shifts_els)), np.max(np.abs(mc.y_shifts_els)))).astype(int)
        else:
            bord_px = np.ceil(np.max(np.abs(mc.shifts_rig))).astype(int)

        if inspectMotionCorrection:
            self._inspectMotionCorrection(mc)

        bord_px = 0 if self.optsCaImAn.get('motion', 'border_nan') == 'copy' else bord_px
        self.optsCaImAn.change_params({'border_pix': bord_px})

        if saveMotionCorrect:
            print('Saving motion corrected movies...')
            # fileName = ''
            # if type(self.movieFilePaths) is str:
            #     fileNameTemp = os.path.split(self.movieFilePaths)[1]
            #     fileName = os.path.splitext(fileNameTemp)[0]
            # else:
            #     for file in self.movieFilePaths:
            #         fileNameTemp = os.path.split(file)[1]
            #         fileName += os.path.splitext(fileNameTemp)[0] + '_' #Changed so that the first part of memmap file is the filename rather than 'memmap'
            fname_new = cm.save_memmap(mc.mmap_file, base_name=self.jobID + 'Yr', order='C', border_to_0=bord_px) # If you uncomment all of the code after "if saveMotionCorrect:" and put "base_name=fileName" as an argument in cm.save_memmap, it will append the concatenated filenames (with underscores in between) of all the videos you're analyzing to the front of the C-order memmap files (both individual ones and the overall one).
            self.optsCaImAn.change_params({'fnames': fname_new})


    def _CNMFE(self, nProcesses, dview=None, saveCNMFEFilename='estimates.h5'):
        """Segments neurons, demixes spatially overlapping neurons, and denoises the calcium activity from calcium movies.
        See paper describing the method: https://www.cell.com/neuron/fulltext/S0896-6273(15)01084-3"""
        print('Setting up CNMF-E object...')
        cnm = cm.source_extraction.cnmf.CNMF(n_processes=nProcesses, dview=dview, Ain=None, params=self.optsCaImAn)
        print('Running CNMF-E...')
        cnm.fit(self.images)
        self.estimates = cnm.estimates
        if saveCNMFEFilename:
            self.CNMFEFilename = os.path.join(self.experiment['calcium imaging directory'], self.jobID + saveCNMFEFilename)
            print('Saving CNMF-E estimates in ' + self.CNMFEFilename)
            cnm.save(self.CNMFEFilename)


    def _deconvolve(self, p=None, method_deconvolution=None, bas_nonneg=None,
                    noise_method=None, optimize_g=0, s_min=None, **kwargs):
        """Performs deconvolution on already extracted traces using
        constrained foopsi.
        """
        print('Setting up for deconvolution...')
        p = (self.optsCaImAn.get('preprocess', 'p')
             if p is None else p)
        method_deconvolution = (self.optsCaImAn.get('temporal', 'method_deconvolution')
                                if method_deconvolution is None else method_deconvolution)
        bas_nonneg = (self.optsCaImAn.get('temporal', 'bas_nonneg')
                      if bas_nonneg is None else bas_nonneg)
        noise_method = (self.optsCaImAn.get('temporal', 'noise_method')
                        if noise_method is None else noise_method)
        s_min = self.optsCaImAn.get('temporal', 's_min') if s_min is None else s_min

        F = self.estimates.C + self.estimates.YrA
        args = dict()
        args['p'] = p
        args['method_deconvolution'] = method_deconvolution
        args['bas_nonneg'] = bas_nonneg
        args['noise_method'] = noise_method
        args['s_min'] = s_min
        args['optimize_g'] = optimize_g
        args['noise_range'] = self.optsCaImAn.get('temporal', 'noise_range')
        args['fudge_factor'] = self.optsCaImAn.get('temporal', 'fudge_factor')

        args_in = [(F[jj], None, jj, None, None, None, None,
                    args) for jj in range(F.shape[0])]

        print('Deconvolving...')
        if 'multiprocessing' in str(type(self.dview)):
            fluor = self.optsCaImAn
            results = self.dview.map_async(cm.deconvolve.constrained_foopsi(fluor, p=p,
                                                                            method_deconvolution=method_deconvolution,
                                                                            noise_method=noise_method,
                                                                            optimize_g=optimize_g,
                                                                            s_min=s_min), args_in).get(4294967)
        elif self.dview is not None:
            results = self.dview.map_sync(cm.deconvolve.constrained_foopsi_parallel(), args_in)
        else:
            results = list(map(cm.deconvolve.constrained_foopsi_parallel(), args_in))

        if sys.version_info >= (3, 0):
            results = list(zip(*results))
        else:  # python 2
            results = zip(*results)

        order = list(results[7])
        self.estimates.C = np.stack([results[0][i] for i in order])
        self.estimates.S = np.stack([results[1][i] for i in order])
        self.estimates.bl = [results[3][i] for i in order]
        self.estimates.c1 = [results[4][i] for i in order]
        self.estimates.g = [results[6][i] for i in order]
        self.estimates.neurons_sn = [results[5][i] for i in order]
        self.estimates.lam = [results[8][i] for i in order]
        self.estimates.YrA = F - self.estimates.C
        return self #FIXME Do we really need to return self?


#%% Methods for evaluating motion correction and CNMF-E
    def _inspectMotionCorrection(self, mc, plotRigidMotionCorrection=True, plotShifts=True, playConcatenatedMovies=True,
                                 downsampleRatio=0.2, plotCorrelation=True, plotAdvancedMCInspection=True):
        """Various plots and movies to help with the inspection of motion correction effectiveness.
        MC is the motion correction object obtained from SELF._MOTIONCORRECTION().
        PLOTRIGIDMOTIONCORRECTION is a boolean that determines whether rigid motion correction is plotted.
        PLAYCONCATENATEDMOVIES is a boolean that determines whether the original and motion-corrected movies are plotted side-by-side.
        DOWNSAMPLERATIO is a float that determines the factor by which to shrink the duration of the playback (helpful for making the motion more obvious).
        PLOTSHIFTS is a boolean that determines whether to plot the x and y pixel shifts over time.
        PLOTCORRELATION is a boolean that determines whether to plot the correlation images for the original and motion-corrected movies side-by-side.
        """
        print('Inspecting motion correction...')
        if plotRigidMotionCorrection:
            h, ax = misc_functions._prepAxes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
            ax[0].imshow(mc.total_template_rig)  # % plot template
            ax[1].plot(mc.shifts_rig)  # % plot rigid shifts
            ax[1].legend(['X Shifts', 'Y Shifts'])

        if plotShifts:
            if self.optsCaImAn.get('motion', 'pw_rigid'):
                h, ax = misc_functions._prepAxes(xLabel='Frames', yLabel='Pixels')
                ax.plot(mc.shifts_rig)
                ax.legend(['X Shifts', 'Y Shifts'])
            else:
                h, ax = misc_functions._prepAxes(xLabel=['', 'Frames'],
                                                 yLabel=['X Shifts (Pixels)', 'Y Shifts (Pixels)'], subPlots=[2, 1])
                ax[0].plot(mc.x_shifts_els)
                ax[1].plot(mc.y_shifts_els)

        if playConcatenatedMovies or plotCorrelation:
            if 'movie' not in self.__dir__():
                self.importCaMovies(filenames=self.movieFilePaths)
            mcMovie = cm.load(mc.mmap_file)
            if playConcatenatedMovies:
                cm.concatenate([self.movie.resize(1, 1, downsampleRatio) - mc.min_mov * mc.nonneg_movie,
                                mcMovie.resize(1, 1, downsampleRatio)], axis=2).play(fr=self._analysisParamsDict['fr'],
                                                                                     q_max=99.5, magnification=2,
                                                                                     bord_px=self.optsCaImAn.get(
                                                                                         'patch', 'border_pix'))
            if plotCorrelation:
                h, ax = misc_functions._prepAxes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
                ax[0].imshow(self.movie.local_correlations(eight_neighbours=True, swap_dim=False))
                ax[1].imshow(mcMovie.local_correlations(eight_neighbours=True, swap_dim=False))

        if plotAdvancedMCInspection:
            final_size = np.subtract(self.optsCaImAn.get('data', 'dims'),
                                     2 * mc.border_to_0)  # remove pixels in the boundaries
            winsize = 100
            swap_dim = False
            resize_fact_flow = .2  # downsample for computing ROF

            tmpl_orig, correlations_orig, flows_orig, norms_orig, crispness_orig = cm.motion_correction.compute_metrics_motion_correction(
                mc.fname[0], final_size[0], final_size[1], swap_dim, winsize=winsize, play_flow=False,
                resize_fact_flow=resize_fact_flow)

            tmpl_mc, correlations_mc, flows_mc, norms_mc, crispness_mc = cm.motion_correction.compute_metrics_motion_correction(
                mc.mmap_file[0], final_size[0], final_size[1],
                swap_dim, winsize=winsize, play_flow=False, resize_fact_flow=resize_fact_flow)

            h, ax = misc_functions._prepAxes(xLabel=['Frame', 'Original'], yLabel=['Correlation', 'Motion Corrected'],
                                             subPlots=[2, 1])
            ax[0].plot(correlations_orig)
            ax[0].plot(correlations_mc)
            plt.legend(['Original', 'Motion Corrected'])
            ax[1].scatter(correlations_orig, correlations_mc)
            ax[1].plot([0, 1], [0, 1], 'r--')
            ax[1].axis('square')

            # print crispness values
            print('Crispness original: ' + str(int(crispness_orig)))
            print('Crispness motion corrected: ' + str(int(crispness_mc)))

            # plot the results of Residual Optical Flow
            fls = [mc.fname[0][:-4] + '_metrics.npz', mc.mmap_file[0][:-4] + '_metrics.npz']

            h, ax = misc_functions._prepAxes(title=['Mean', 'Corr Image', 'Mean Optical Flow', '', '', ''],
                                             xLabel=['Original', '', '', 'Motion Corrected', '', ''], yLabel=['', '', '', '', '', ''],
                                             subPlots=[2, 3])

            for cnt, fl in zip(range(len(fls)), fls):
                with np.load(fl) as ld:
                    print(str(np.mean(ld['norms'])) + '+/-' + str(np.std(ld['norms'])) +
                          '; ' + str(ld['smoothness']) + '; ' + str(ld['smoothness_corr']))

                    if cnt == 0:
                        mean_img = np.mean(cm.load(mc.fname[0]), 0)[12:-12, 12:-12]
                    else:
                        mean_img = np.mean(cm.load(mc.mmap_file[0]), 0)[12:-12, 12:-12]

                    lq, hq = np.nanpercentile(mean_img, [0.5, 99.5])
                    ax[3 * cnt + 1].imshow(mean_img, vmin=lq, vmax=hq)
                    ax[3 * cnt + 2].imshow(ld['img_corr'], vmin=0, vmax=0.35)
                    # ax[3 * cnt + 3].plot(ld['norms'])
                    # ax[3 * cnt + 3].xlabel('frame')
                    # ax[3 * cnt + 3].ylabel('norm opt flow')
                    if len(ax) > (3 * cnt + 3):
                        mappable = ax[3 * cnt + 3].imshow(np.mean(
                            np.sqrt(ld['flows'][:, :, :, 0] ** 2 + ld['flows'][:, :, :, 1] ** 2), 0), vmin=0, vmax=0.3)
                        plt.colorbar(mappable=mappable, ax=ax[3 * cnt + 3]) #FIXME colorbar() is NOT an attribute of ax. It is of plt though


    def _corrPNR(self, inspectCorrPNR, downsampleForCorrPNR):
        """Create the correlation and peak-noise-ratio (PNR) images and, if desired, inspect them with an interactive plot to determine min_corr and min_pnr."""
        print('Creating correlation and peak-noise-ratio images...')
        self.cn_filter, self.pnr = cm.summary_images.correlation_pnr(self.images[::downsampleForCorrPNR],
                                                                     gSig=self.optsCaImAn.get('init', 'gSig')[0],
                                                                     swap_dim=False)
        if inspectCorrPNR:
            cm.utils.visualization.inspect_correlation_pnr(self.cn_filter, self.pnr)


#%% Methods for manipulating components after CNMF-E is run
    def removeComponents(self, idxToRemove, filename=None, saveNewCNMFE=True): #FIXME compare this to evaluate_components and the components GUI to see if there's overlap
        """Remove or merge components extracted using the CNMF-E algorithm.
        IDXTOREMOVE are the indices of components to remove.
        FILENAME is the name of the HDF5 file where the output of the CNMF-E algorithm is stored. This file must be created prior to running this method.
        SAVENEWCNMFE determines whether to save the output with the removed components as a new HDF5 file."""
        print('Loading the CNMF-E estimates object...')
        if filename == None:
            filename = self.CNMFEFilename
        cnmObj = cm.source_extraction.cnmf.cnmf.load_CNMF(filename) #FIXME use try/except to check if self.estimates already exists
        print('Removing components from the CNMF-E estimates object...')
        cnmObj.remove_components(idxToRemove)
        if saveNewCNMFE:
            directory, filename = os.path.split(filename)
            filenameParts = os.path.splitext(filename)
            self.CNMFEFilename = os.path.join(directory, self.jobID + filenameParts[0] + '_components_removed' + filenameParts[1])
            print('Saving new CNMF-E estimates object as ' + self.CNMFEFilename)
            cnmObj.save(self.CNMFEFilename)


    def _createContourFig(self, sfootprints, background, current_selected, thr=None, thr_method='max', maxthr=0.2, nrgthr=0.9, display_numbers=True, max_number=None,
                      cmap=None, unselectcolor='w', selectcolor='r', coordinates=None,
                      contour_args={}, number_args={}):
        """Plots contour of spatial components against a background image
    
         Args:
             A:   np.ndarray or sparse matrix
                       Matrix of Spatial components (d x K)
        
             Cn:  np.ndarray (2D)
                       Background image (e.g. mean, correlation)
        
             thr_method: [optional] string
                      Method of thresholding:
                          'max' sets to zero pixels that have value less than a fraction of the max value
                          'nrg' keeps the pixels that contribute up to a specified fraction of the energy
        
             maxthr: [optional] scalar
                        Threshold of max value
        
             nrgthr: [optional] scalar
                        Threshold of energy
        
             thr: scalar between 0 and 1
                       Energy threshold for computing contours (default 0.9)
                       Kept for backwards compatibility. If not None then thr_method = 'nrg', and nrgthr = thr
        
             display_number:     Boolean
                       Display number of ROIs if checked (default True)
        
             max_number:    int
                       Display the number for only the first max_number components (default None, display all numbers)
        
             cmap:     string
                       User specifies the colormap (default None, default colormap)
        """
    
        if thr is None:
            try:
                thr = {'nrg': nrgthr, 'max': maxthr}[thr_method]
            except KeyError:
                thr = maxthr
        else:
            thr_method = 'nrg'
        plt.figure(1)
        ax = plt.gca()
        fig = plt.imshow(background, interpolation=None, cmap=cmap)
        if coordinates is None:
            coordinates = cm.utils.visualization.get_contours(sfootprints, np.shape(background), thr, thr_method, swap_dim=False)
        for c in coordinates:
            v = c['coordinates']
            c['bbox'] = [np.floor(np.nanmin(v[:, 1])), np.ceil(np.nanmax(v[:, 1])),
                         np.floor(np.nanmin(v[:, 0])), np.ceil(np.nanmax(v[:, 0]))]
            if c['neuron_id'] in current_selected:
                plt.plot(*v.T, c=selectcolor, **contour_args)
            else:
                plt.plot(*v.T, c=unselectcolor, **contour_args)
        if display_numbers:
            d1, d2 = np.shape(background)
            d, nr = np.shape(sfootprints)
            comp = cm.utils.visualization.com(sfootprints, d1, d2)
            if max_number is None:
                max_number = sfootprints.shape[1]
            for i in range(np.minimum(nr, max_number)):
                ax.text(comp[i, 1], comp[i, 0], str(i + 1), color=unselectcolor, **number_args)
        plt.axis('off')
        return fig


    def _componentImage(self, graph, current_selected,  max=False, min=False, STD=False, mean=False, median=False, range=False,
                     cmap='viridis'):
        """Adds projection to GUI."""
        pic_IObytes = io.BytesIO()
        if max:
            self._createContourFig(self.estimates.A, self.projections['Max'], current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
        elif min:
            self._createContourFig(self.estimates.A, self.projections['Min'], current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
        elif STD:
            self._createContourFig(self.estimates.A, self.projections['Std'], current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
        elif mean:
            self._createContourFig(self.estimates.A, self.projections['Mean'], current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
        elif median:
            self._createContourFig(self.estimates.A, self.projections['Med'], current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
        elif range:
            self._createContourFig(self.estimates.A, self.projections['Range'], current_selected, cmap=cmap).figure.savefig(pic_IObytes, format='png', bbox_inches='tight', pad_inches = 0)
        plt.close()
        pic_IObytes.seek(0)
        pic_hash = base64.b64encode(pic_IObytes.read())
        # Draw image in graph
        graph.draw_image(data=pic_hash, location=(0, self.movie.shape[1]))
    
        
    def _componentGUI(self, auto_eval = False):
        """"""
        # Get all projections
        try: 
            a = self.projections['Range']
        except:
            self.computeProjections()
        
        if self.estimates.idx_components_bad is None:
            self.estimates.idx_components = []
            self.estimates.idx_components_bad = []
        
        if auto_eval:
            # preselect rejected components using evaluate_component
            self.evaluateComponents()
            self.estimates.idx_components += np.ones(self.estimates.idx_components.shape, dtype=self.estimates.idx_components.dtype)
            self.estimates.idx_components_bad += np.ones(self.estimates.idx_components_bad.shape, dtype=self.estimates.idx_components_bad.dtype)
        
        # define the window layout
        cmapOptions = ['viridis', 'jet', 'plasma', 'inferno', 'magma', 'cividis', 'Greys', 'Purples', 'Blues', 'Greens',
                       'Oranges', 'Reds',
                       'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu', 'BuPu',
                       'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn', 'binary', 'gist_yarg', 'gist_gray', 'gray',
                       'bone',
                       'pink', 'spring', 'summer', 'autumn', 'winter', 'cool',
                       'Wistia', 'hot', 'afmhot', 'gist_heat', 'copper', 'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'RdBu',
                       'RdYlBu',
                       'RdYlGn', 'Spectral', 'coolwarm', 'bwr', 'seismic', 'Pastel1', 'Pastel2', 'Paired', 'Accent',
                       'Dark2',
                       'Set1', 'Set2', 'Set3', 'tab10', 'tab20', 'tab20b',
                       'tab20c']


        layout = [[sg.Text('Components', key='-TITLE-')],
                  [sg.Graph((self.movie.shape[2], self.movie.shape[1]), (0, 0), (self.movie.shape[1], self.movie.shape[2]), key='-GRAPH-', 
                            enable_events=True)],
                  [sg.Text("Projection Type:"),
                   sg.Combo(['Max', 'Min', 'Mean', 'Median', 'STD', "Range"], key='-OPTION-', default_value='Max',
                            readonly=True,
                            auto_size_text=True, enable_events=True)],
                  [sg.Text("CMAP:"), sg.Combo(cmapOptions, key='-CMAP-', default_value='viridis', readonly=True,
                                              auto_size_text=True, enable_events=True)],
                  [sg.Text("Select to reject: ")],
                  [sg.Listbox(values=range(1, len(self.estimates.C)+1), default_values=self.estimates.idx_components_bad, size=(3, 3), key='-LISTCOMP-', select_mode='multiple', background_color="white", highlight_background_color="red", enable_events = True)],
                  [sg.Button('Cancel', key="-CANCEL-"), sg.Button('Submit', key="-SUBMIT-")]]
        # create the form and show it without the plot
        window = sg.Window('Components', layout, finalize=True, resizable=True,
                           element_justification='center', font='Helvetica 18')

        # adds image to window
        graph = window['-GRAPH-']
        self._componentImage(graph, self.estimates.idx_components_bad, max=True)
        
        # calls view_components to view temporal data
        plt.figure(2)
        self.estimates.view_components(img = self.projections['Range'])
        plt.close(2)
        
        while True:
            # controls events to update window
            event, values = window.read(timeout=100)

            
            if event == sg.WINDOW_CLOSED or event in '-CANCEL-':
                break

            # Type of image options
            elif event in '-OPTION-':
                if values['-OPTION-'] == 'Max':
                    self._componentImage(graph, values['-LISTCOMP-'], max=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Min':
                    self._componentImage(graph, values['-LISTCOMP-'], min=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'STD':
                    self._componentImage(graph, values['-LISTCOMP-'], STD=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Mean':
                    self._componentImage(graph, values['-LISTCOMP-'], mean=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Median':
                    self._componentImage(graph, values['-LISTCOMP-'], median=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Range':
                    self._componentImage(graph, values['-LISTCOMP-'], range=True, cmap=values['-CMAP-'])

            # CMAP of image
            elif event in '-CMAP-':
                if values['-OPTION-'] == 'Max':
                    self._componentImage(graph, values['-LISTCOMP-'], max=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Min':
                    self._componentImage(graph, values['-LISTCOMP-'], min=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'STD':
                    self._componentImage(graph, values['-LISTCOMP-'], STD=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Mean':
                    self._componentImage(graph, values['-LISTCOMP-'], mean=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Median':
                    self._componentImage(graph, values['-LISTCOMP-'], median=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Range':
                    self._componentImage(graph, values['-LISTCOMP-'], range=True, cmap=values['-CMAP-'])

            #Update colors of selected components
            elif event in '-LISTCOMP-':
                if values['-OPTION-'] == 'Max':
                    self._componentImage(graph, values['-LISTCOMP-'], max=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Min':
                    self._componentImage(graph, values['-LISTCOMP-'], min=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'STD':
                    self._componentImage(graph, values['-LISTCOMP-'], STD=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Mean':
                    self._componentImage(graph, values['-LISTCOMP-'], mean=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Median':
                    self._componentImage(graph, values['-LISTCOMP-'], median=True, cmap=values['-CMAP-'])
                elif values['-OPTION-'] == 'Range':
                    self._componentImage(graph, values['-LISTCOMP-'], range=True, cmap=values['-CMAP-'])

            elif event in '-SUBMIT-':
                selected = np.arange(0, len(self.estimates.C))
                selected = [idx for idx in selected if idx not in (np.array(values['-LISTCOMP-'], dtype=int)- np.ones(len(values['-LISTCOMP-']), dtype=int))]
                self.estimates.select_components(idx_components = selected)
                break

        plt.close()
        window.close()


    def evaluateComponents(self, min_SNR=3, r_values_min=0.85):
        """"""
        Yr, dims, T = cm.load_memmap(self.optsCaImAn.get('data', 'fnames')[0])
        images = Yr.T.reshape((T,) + dims, order='F')

        self.optsCaImAn.set('quality', {'min_SNR': min_SNR, 'rval_thr': r_values_min, 'use_cnn': False})
        self.estimates.evaluate_components(images, self.optsCaImAn)


#%% Methods for finding calcium events
    def findCalciumEvents(self, derivative='first', threshold=0.1):
        """This method looks for calcium events in self.estimates.C.
        DERIVATIVE is the number of times to take the derivative before thresholding. The options are 'zeroth', 'first', or 'second'.
        THRESHOLD is the threshold above which to detect calcium events. The units depend on the DERIVATIVE used."""
        print('Finding indices of calcium events...')
        self.CaEventsIdx = 0 #FIXME This variable is currently a placeholder (since it's used in miniscope_ephys.py) for the variable that stores the indices of calcium events in self.estimates.C. It is a list with the same number of elements as components, and each element is, in turn, an array of the indices of the calcium events of the corresponding neuron.
        pass


#%% Methods for computing and plotting head direction data
    def _quatFileToEulerFile(self, filename='headOrientation.csv', nf='True'):  ##returns newfilename
        newfilename =  self.jobID + filename.replace('.csv', 'inEulerAngles.csv')
        if os.path.exists(filename):
            print('File exists')
            with open(filename, newline='') as f:
                reader = csv.reader(f)
                if nf == 'True':  # do you want to create a new file
                    with open(newfilename, 'w', newline='') as nf:
                        writer = csv.writer(nf)
                        header = []
                        header.append('Time Stamp (ms)')
                        header.append('x')
                        header.append('y')
                        header.append('z')
                        writer.writerow(header)
                        next(f)
                        for line in reader:
                            eulerAngles = misc_functions.conv_quat_to_euler(line)
                            writer.writerow(eulerAngles)
                    return newfilename
                else:
                    matrix = []
                    next(f)
                    for line in reader:
                        eulerAngles = misc_functions.conv_quat_to_euler(line)
                        matrix.append(eulerAngles)
                    return matrix
        else:
            print('!!! ERROR: File not found') #FIXME
            return


    def graphMovement(self, filename='headOrientationinEulerAngles.csv',
                       plotName='movementPlot.png'):  ##eulerAngle file

        if 'inEulerAngles.csv' not in filename and '.csv' in filename:
            filename = self._quatFileToEulerFile(filename)
        elif '.csv' not in filename:
            print('!!! ERROR: Invalid file')
            return

        if os.path.exists(filename):
            print('File exists')
            with open(filename, newline='') as f:
                reader = csv.reader(f)
                y = []
                avgAngle = []
                time = []
                next(f)  ##skip header line
                for line in reader:
                    if len(line) != 4:
                        print('!!! ERROR: Invalid file') #FIXME
                        return
                    eulerAngleSum = (float(line[1]) + float(line[2]) + float(
                        line[3])) / 3  # FIXME change to difference between angles instead of averaging the angles
                    avgAngle.append(eulerAngleSum)
                    time.append(float(line[0]))
                count = 1  ##skips first line
                while count < len(avgAngle):
                    deltaAngle = abs((avgAngle[count]) - avgAngle[count - 1])
                    deltaTime = abs(time[count] - avgAngle[count - 1])
                    y.append(deltaAngle / deltaTime)
                    count += 1
                '''
                FIXME
                make an array and take the diff between the rows so you have three columns
                figure out how you want to represent them as one value and graph
                '''
                x = list(time[1:])  ##skips first time
                y = list(y)
                plt.plot(x, y)
                plt.xlabel('time(ms)')
                plt.ylabel('angle change over time (rad/s)')
                plt.title('movement over time')
                plt.show()
                plt.savefig(self.jobID + plotName)
        else:
            print('!!! ERROR: File not found') #FIXME
            return


#%% Functions that don't apply to a single experiment
def findSameNeurons(sessionList, FOVdims, templateList = None, background=None, plotResults=False):
    '''
    Tracks ROIs across multiple imaging sessions
    
    Args:
        sessionList: A numpy array of spacial footprints (estimates.A) from each session
        templateList: A numpy array of one frame from each session's movie
        FOVdims: Dimensions of the field of view as a tuple
        background: If there are only two sessions being compared and plotResults is true,
                    this is the background that results will be plotted over.
        plotResults: If only two sessions are being compared, set true if you want the results to be plotted
        
    Returns:
        If only 2 sessions:
            matched_ROIs1: list
                indices of matched ROIs from session 1
            matched_ROIs2: list
                indices of matched ROIs from session 2
            non_matched1: list
                indices of non-matched ROIs from session 1
            non_matched2: list
                indices of non-matched ROIs from session 2
            performance:  list
                (precision, recall, accuracy, f_1 score) with A1 taken as ground truth
            A2: csc_matrix  # pixels x # of components
                ROIs from session 2 aligned to session 1
                
        If more than 2 sessions:
            A_union: csc_matrix # pixels x # of total distinct components
                union of all kept ROIs 
            assignments: ndarray int of size # of total distinct components x # sessions
                element [i,j] = k if component k from session j is mapped to component
                i in the A_union matrix. If there is no much the value is NaN
            matchings: list of lists
                matchings[i][j] = k means that component j from session i is represented
                by component k in A_union
    '''
    print('Finding common neurons between recordings...')
    if sessionList.size > 2:
        return cm.base.rois.register_multisession(sessionList, FOVdims, templates=templateList)
    else:
        if templateList is not None:
            return cm.base.rois.register_ROIs(sessionList[0], sessionList[1], FOVdims, template1=templateList[0], template2=templateList[1], Cn=background, plot_results=plotResults)
        else:
            return cm.base.rois.register_ROIs(sessionList[0], sessionList[1], FOVdims, Cn=background, plot_results=plotResults)

# if __name__ == "__main__":
#     program = miniscope
#     program.main()