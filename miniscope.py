# -*- coding: utf-8 -*-
"""
Created on Mon Oct 19 08:43:50 2020

@author: eric
"""

import csv
import os.path
from json import load
import experiment
import numpy as np
from scipy.signal import detrend
import matplotlib.pyplot as plt
plt.rcParams['svg.fonttype'] = 'none'
import caiman as cm
import misc_Functions

class miniscope(experiment.experiment):
    """This is the class definition for handling miniscopes (1-photon calcium imaging) data."""
    def __init__(self):
        print('init')
    """
    def __init__(self, filenameMiniscope='metaData.json', lineNum=None, filename='experiments.csv', analysisFilename='analysis_parameters.csv'):
        if lineNum != None:
            super().__init__(lineNum, filename=filename)
        else:
            self.experiment = {}
        
        # Import the meta data files and add to the experiment dictionary
        self.experiment['Miniscope settings filename'] = filenameMiniscope
        with open(filenameMiniscope) as s:
            self.experiment.update(load(s))
        settingsFilename = os.path.split(filenameMiniscope)
        with open(settingsFilename[0] + '/Miniscope/' + settingsFilename[1]) as s:
            self.experiment.update(load(s))
        
        if 'directory' not in self.experiment:
            self.experiment['directory'] = os.path.abspath(os.path.dirname(filenameMiniscope))
        
        if lineNum != None:
            self.miniscopeImportAnalysisParams(lineNum, analysisFilename)
        else:
            self._analysisParamsDict = {}
        """

    def miniscopeImportAnalysisParams(self, lineNum, filename):
        """Import parameters for calcium movie analysis using CaImAn."""
        analysisParamsCSV = []
        with open(filename, newline='') as s:
            reader = csv.reader(s)
            for row in reader:
                analysisParamsCSV.append(row)
        
        # Make a dictionary with each of the columns in the CSV file
        self._analysisParamsDict = {}
        for k, columnTitle in enumerate(analysisParamsCSV[0]):
            self._analysisParamsDict[columnTitle] = analysisParamsCSV[lineNum][k]
            
            # Fix the types of different parameters if they're not supposed to be strings
            if (self._analysisParamsDict[columnTitle] == 'False') or (self._analysisParamsDict[columnTitle] == 'True'):
                self._analysisParamsDict[columnTitle] = bool(self._analysisParamsDict[columnTitle])
            elif self._analysisParamsDict[columnTitle] == 'None':
                self._analysisParamsDict[columnTitle] = None
            elif self._analysisParamsDict[columnTitle][0] == '(':
                convertParamTuple = []
                for k, c in enumerate(self._analysisParamsDict[columnTitle].replace('(', '').replace(')', '').replace(' ', '').split(',')):
                    convertParamTuple.append(int(c))
                self._analysisParamsDict[columnTitle] = tuple(convertParamTuple)
            elif self._analysisParamsDict[columnTitle].isdecimal():
                self._analysisParamsDict[columnTitle] = int(self._analysisParamsDict[columnTitle])
            elif ('.' in self._analysisParamsDict[columnTitle]) and (self._analysisParamsDict[columnTitle].split('.')[0].isdecimal()):
                self._analysisParamsDict[columnTitle] = float(self._analysisParamsDict[columnTitle])


    def miniscopeImportEvents(self):
        """Import calcium imaging experiment events."""
        self.miniscopeEvents = {}
        # Make a dictionary with each of the columns in the DAT file
        for k, columnTitle in enumerate(self._miniscopeExperimentDAT[3]): # self._miniscopeExperimentDAT was previously imported in __init__, but the format of this file ('settings_and_notes.dat') changed.
            self.miniscopeEvents[columnTitle] = []
            for h in range(4, len(self._miniscopeExperimentDAT)):
                self.miniscopeEvents[columnTitle].append(self._miniscopeExperimentDAT[h][k])
        timestamps = list(self.miniscopeEvents.keys())[0]
        labels = list(self.miniscopeEvents.keys())[1]
        self.miniscopeEvents['timestamps'] = np.array(self.miniscopeEvents[timestamps], dtype=int)
        self.miniscopeEvents['labels'] = np.array(self.miniscopeEvents[labels])


    def findMovieFilePaths(self, directory=None, fileExtensions='.avi', fileStartsWith='msCam'):
        """Makes a list of the full paths of all movie files in DIRECTORY.
        FILEEXTENSIONS is a string of the file extension or a list or tuple with multiple file extensions."""
        if directory == None:
            directory = self.experiment['directory']
        self.movieFilePaths = misc_Functions._findFilePaths(directory, fileExtensions, fileStartsWith=fileStartsWith)


    def importCaMovies(self, filenames=None):
        """Import calcium imaging data. Not necessary if using processCaMovies().
        FILENAMES can be a single movie file or a list of movie files (in the order that you want them).
        SYNCTOEEGCHANNEL is the string representing the channel to which the timing of the movie frames will be synced."""
        if filenames == None:
            self.findMovieFilePaths()
            filenames = self.movieFilePaths
        if type(filenames) is str:
            self.movie = cm.load(filenames)
        else:
            self.movie = cm.load_movie_chain(filenames)
        self._importCaMoviesFilenames = filenames


    def convertCaMovies(self, filenames=None, newFileType='.tif', joinMovies=False):
        """Convert calcium movies from one type to another. File types must be supported by CaImAn.
        The new filename(s) is the same as the first filename in FILENAMES, with NEWFILETYPE appended to the end.
        JOINMOVIES determines whether all of the movie files in FILENAMES are converted to a single new movie, or whether they are saved in len(FILENAMES) movies."""
        filenamesArg = filenames
        if (filenames == None) and ('movie' in self.__dir__()):
            filenames = self._importCaMoviesFilenames
        elif filenames == None:
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
                    movie = cm.load(filenames[k])
                    movie.save(os.path.splitext(filenames[k])[0] + newFileType) ###########maybe use the saveCaMovie method here and elsewhere in this method?


    def saveCaMovie(self, processingStep=''):
        """Saves the calcium movie that is currently in SELF.MOVIE."""
        if '_importCaMoviesFilenames' in self.__dir__():
            if type(self._importCaMoviesFilenames) is not list:
                filename, filetype = os.path.splitext(self._importCaMoviesFilenames)
                filename += processingStep
                self.movie.save(filename + filetype)###############
            else:
                filenameFirst, filetype = os.path.splitext(self._importCaMoviesFilenames[0])
                filenameLast, _ = os.path.splitext(self._importCaMoviesFilenames[-1])
                filenumFirstIdx = [f.isdecimal() for f in filenameFirst[-5:]]
                filenumLastIdx = [f.isdecimal() for f in filenameLast[-5:]]
                filenumFirst = filenameFirst[np.where(filenumFirstIdx)[0][0]:]
                filenumLast = filenameLast[np.where(filenumLastIdx)[0][0]:]
                filenumLast += processingStep
                self.movie.save(filename + '_' + filenumFirst + '_' + filenumLast + filetype)


    def denoiseCaMovie(self, saveMovie=True):
        """Loads a movie and removes both the horizontal bands (that slowly travel upwards) from the movie and the slow flicker of the entire image.
        SAVEMOVIE determines whether to save the filtered movie (with '_denoised' appended to the filename)."""
        mode = 'display'
        if saveMovie:
            mode = 'save'
        misc_Functions.denoiseMovie(self.experiment['directory'], mode=mode)


    def detrendCaFluorescence(self, saveMovie=True, detrendType='median', plotTrend=False):
        """Loads the calcium movie and detrends it based on the fluorescence of the entire movie.
        SAVEMOVE determines whether to save the debleached movie (with '_detrended' appended to the filename).
        DETRENDTYPE determines which method is used for detrending. 'median' debleaches by fitting a model to the median intensity.
        'linear' debleaches by linearly detrending the mean fluorescence, and includes subtracting the mean of the fluorescence over time."""
        if 'movie' not in self.__dir__():
            self.importCaMovies()
        if plotTrend:
            h, ax = misc_Functions._prepAxes(xLabel='Frames', yLabel='Mean Fluorescence')
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


    def computedFoverF(self, saveMovie=True):
        """"""
        if saveMovie:
            self.saveCaMovie(processingStep='_dFoverF')


    def preprocessCaMovies(self, saveMovie=True, denoise=True, detrend=True, dFoverF=True):
        """Run all preprocessing steps in one method, using their default options."""
        if saveMovie:
            if denoise:
                self.denoiseMovie()
            if detrend and dFoverF:
                self.detrendCaFluorescence(saveMovie=False)
                self.computedFoverF(saveMovie=False)
                self.saveCaMovie(processingStep='_detrended_dFoverF')
            elif detrend:
                self.detrendCaFluorescence(saveMovie=True)
            elif dFoverF:
                self.computedFoverF(saveMovie=True)
        else:
            if denoise:
                self.denoiseMovie(saveMovie=False)
            if detrend:
                self.detrendCaFluorescence(saveMovie=False)
            if dFoverF:
                self.computedFoverF(saveMovie=False)


    def processCaMovies(self, motionCorrect=True, saveMotionCorrect=True, inspectMotionCorrection=False, inspectCorrPNR=False, downsampleForCorrPNR=1, runCNMFE=True, saveCNMFEFilename='', editComponents=True, deconvolve=True):
        """Preprocess calcium imaging data."""
        if 'movieFilePaths' not in dir(self):
            self.findMovieFilePaths()
        self._analysisParamsDict['fnames'] = self.movieFilePaths
        self.optsCaImAn = cm.source_extraction.cnmf.params.CNMFParams(params_dict=self._analysisParamsDict)
        c, dview, nProcesses = cm.cluster.setup_cluster(backend='local', n_processes=24, single_thread=False)
        if motionCorrect:
            self._motionCorrection(dview, saveMotionCorrect, inspectMotionCorrection)
        else:
            if saveMotionCorrect:
                fname_new = cm.save_memmap(self.optsCaImAn.get('data', 'fnames'), base_name='memmap_', order='C', border_to_0=0, dview=dview) # if no motion correction just memory map the file
                self.optsCaImAn.change_params({'fnames': fname_new})
        
        if inspectCorrPNR or runCNMFE:
            Yr, dims_new, T = cm.load_memmap(self.optsCaImAn.get('data', 'fnames'))
            self.optsCaImAn.change_params({'dims': dims_new})
            self.images = Yr.T.reshape((T,) + dims_new, order='F')
            if inspectCorrPNR:
                self._corrPNR(inspectCorrPNR, downsampleForCorrPNR)
            if runCNMFE:
                self._CNMFE(nProcesses, dview, saveCNMFEFilename)
        
        if deconvolve:
            self._deconvolve()
        
        cm.stop_server(dview=dview)


    def _motionCorrection(self, dview, saveMotionCorrect, inspectMotionCorrection):
        """Use motion correction to correct for movement during the calcium movies."""
        mc = cm.motion_correction.MotionCorrect(self.optsCaImAn.get('data', 'fnames'), dview=dview, **self.optsCaImAn.get_group('motion'))
        mc.motion_correct(save_movie=saveMotionCorrect)
        if self.optsCaImAn.get('motion', 'pw_rigid'):
            bord_px = np.ceil(np.maximum(np.max(np.abs(mc.x_shifts_els)), np.max(np.abs(mc.y_shifts_els)))).astype(np.int)
        else:
            bord_px = np.ceil(np.max(np.abs(mc.shifts_rig))).astype(np.int)
        
        if inspectMotionCorrection:
            self._inspectMotionCorrection(mc)
        
        bord_px = 0 if self.optsCaImAn.get('motion', 'border_nan') == 'copy' else bord_px
        self.optsCaImAn.change_params({'border_pix': bord_px})
        
        if saveMotionCorrect:
            fname_new = cm.save_memmap(mc.mmap_file, base_name='memmap_', order='C', border_to_0=bord_px)
            self.optsCaImAn.change_params({'fnames': fname_new})


    def _inspectMotionCorrection(self, mc, plotRigidMotionCorrection=True, plotShifts=True, playConcatenatedMovies=True, downsampleRatio=0.2, plotCorrelation=True, plotAdvancedMCInspection=True):
        """Various plots and movies to help with the inspection of motion correction effectiveness.
        MC is the motion correction object obtained from SELF._MOTIONCORRECTION().
        PLOTRIGIDMOTIONCORRECTION is a boolean that determines whether rigid motion correction is plotted.
        PLAYCONCATENATEDMOVIES is a boolean that determines whether the original and motion-corrected movies are plotted side-by-side.
        DOWNSAMPLERATIO is a float that determines the factor by which to shrink the duration of the playback (helpful for making the motion more obvious).
        PLOTSHIFTS is a boolean that determines whether to plot the x and y pixel shifts over time.
        PLOTCORRELATION is a boolean that determines whether to plot the correlation images for the original and motion-corrected movies side-by-side.
        """
        if plotRigidMotionCorrection:
            h, ax = misc_Functions._prepAxes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
            ax[0].imshow(mc.total_template_rig)  # % plot template
            ax[1].plot(mc.shifts_rig)  # % plot rigid shifts
            ax[1].legend(['X Shifts', 'Y Shifts'])
        
        if plotShifts:
            if self.optsCaImAn.get('motion', 'pw_rigid'):
                h, ax = misc_Functions._prepAxes(xLabel='Frames', yLabel='Pixels')
                ax.plot(mc.shifts_rig)
                ax.legend(['X Shifts','Y Shifts'])
            else:
                h, ax = misc_Functions._prepAxes(xLabel=['', 'Frames'], yLabel=['X Shifts (Pixels)', 'Y Shifts (Pixels)'], subPlots=[2, 1])
                ax[0].plot(mc.x_shifts_els)
                ax[1].plot(mc.y_shifts_els)
        
        if playConcatenatedMovies or plotCorrelation:
            if 'movie' not in self.__dir__():
                self.importCaMovies(fnames=self.movieFilePaths)
            mcMovie = cm.load(mc.mmap_file)
            if playConcatenatedMovies:
                cm.concatenate([self.movie.resize(1, 1, downsampleRatio) - mc.min_mov*mc.nonneg_movie,
                                mcMovie.resize(1, 1, downsampleRatio)], axis=2).play(fr=self._analysisParamsDict['fr'], q_max=99.5, magnification=2, bord_px=self.optsCaImAn.get('patch', 'border_pix'))
            if plotCorrelation:
                h, ax = misc_Functions._prepAxes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
                ax[0].imshow(self.movie.local_correlations(eight_neighbours=True, swap_dim=False))
                ax[1].imshow(mcMovie.local_correlations(eight_neighbours=True, swap_dim=False))
        
        if plotAdvancedMCInspection:
            final_size = np.subtract(self.optsCaImAn.get('data', 'dims'), 2 * mc.border_to_0) # remove pixels in the boundaries
            winsize = 100
            swap_dim = False
            resize_fact_flow = .2    # downsample for computing ROF
            
            tmpl_orig, correlations_orig, flows_orig, norms_orig, crispness_orig = cm.motion_correction.compute_metrics_motion_correction(
            mc.fname[0], final_size[0], final_size[1], swap_dim, winsize=winsize, play_flow=False, resize_fact_flow=resize_fact_flow)
            
            tmpl_mc, correlations_mc, flows_mc, norms_mc, crispness_mc = cm.motion_correction.compute_metrics_motion_correction(
                mc.mmap_file[0], final_size[0], final_size[1],
                swap_dim, winsize=winsize, play_flow=False, resize_fact_flow=resize_fact_flow)
            
            h, ax = misc_Functions._prepAxes(xLabel=['Frame', 'Original'], yLabel=['Correlation', 'Motion Corrected'], subPlots=[2, 1])
            ax[0].plot(correlations_orig)
            ax[0].plot(correlations_mc)
            plt.legend(['Original','Motion Corrected'])
            ax[1].scatter(correlations_orig, correlations_mc)
            ax[1].plot([0,1],[0,1],'r--')
            ax[1].axis('square')
            
            # print crispness values
            print('Crispness original: '+ str(int(crispness_orig)))
            print('Crispness motion corrected: '+ str(int(crispness_mc)))
            
            # plot the results of Residual Optical Flow
            fls = [mc.fname[0][:-4] + '_metrics.npz', mc.mmap_file[0][:-4] + '_metrics.npz']
            
            h, ax = misc_Functions._prepAxes(title=['Mean', 'Corr Image', 'Mean Optical Flow', '', '', ''], xLabel=['Original', '', '', 'Motion Corrected', '', ''], yLabel=[], subPlots=[2, 3])
            
            for cnt, fl in zip(range(len(fls)),fls):
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
                    #ax[3 * cnt + 3].plot(ld['norms'])
                    #ax[3 * cnt + 3].xlabel('frame')
                    #ax[3 * cnt + 3].ylabel('norm opt flow')
                    ax[3 * cnt + 3].imshow(np.mean(
                        np.sqrt(ld['flows'][:, :, :, 0]**2 + ld['flows'][:, :, :, 1]**2), 0), vmin=0, vmax=0.3)
                    ax[3 * cnt + 3].colorbar()


    def _corrPNR(self, inspectCorrPNR, downsampleForCorrPNR):
        """Create the correlation and peak-noise-ratio (PNR) images and, if desired, inspect them with an interactive plot to determine min_corr and min_pnr."""
        self.cn_filter, self.pnr = cm.summary_images.correlation_pnr(self.images[::downsampleForCorrPNR], gSig=self.optsCaImAn.get('init_params', 'gSig')[0], swap_dim=False)
        if inspectCorrPNR:
            cm.utils.visualization.inspect_correlation_pnr(self.cn_filter, self.pnr)


    def _CNMFE(self, nProcesses, dview, saveCNMFEFilename):
        """Segments neurons, demixes spatially overlapping neurons, and denoises the calcium activity from calcium movies. See paper describing the method: https://www.cell.com/neuron/fulltext/S0896-6273(15)01084-3"""
        cnm = cm.source_extraction.cnmf.CNMF(n_processes=nProcesses, dview=dview, Ain=None, params=self.optsCaImAn)
        cnm.fit(self.images)
        if saveCNMFEFilename:
            self.CNMFEFilename = os.path.join(self.experiment['directory'], saveCNMFEFilename)
            cnm.save(self.CNMFEFilename)
    
    
    def removeComponents(self, idxToRemove, filename=None, saveNewCNMFE=True):
        """Remove or merge components extracted using the CNMF-E algorithm.
        IDXTOREMOVE are the indices of components to remove.
        FILENAME is the name of the HDF5 file where the output of the CNMF-E algorithm is stored. This file must be created prior to running this method.
        SAVENEWCNMFE determines whether to save the output with the removed components as a new HDF5 file."""
        if filename == None:
            filename = self.CNMFEFilename
        cnmObj = cm.source_extraction.cnmf.cnmf.load_CNMF(filename)
        cnmObj.remove_components(idxToRemove)
        if saveNewCNMFE:
            filenameParts = os.path.splitext(filename)
            self.CNMFEFilename = os.path.join(filenameParts[0] + '_components_removed' + filenameParts[1])
            cnmObj.save(self.CNMFEFilename)


    def _deconvolve(self):
        """"""
        pass


    def multiSessionRegistration(self):
        """Register components (neurons) between different recording sessions."""
        pass
    
    def quatFile_to_eulerFile(self, filename='headOrientation.csv', nf='True'): ##returns newfilename
        newfilename = filename.replace('.csv', 'inEulerAngles.csv')
        if os.path.exists(filename):
            print('File exists') 
            with open(filename, newline='') as f:
                reader = csv.reader(f)
                if nf == 'True':
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
                            eulerAngles = self.conv_quat_to_euler(line)
                            writer.writerow(eulerAngles)
                    return newfilename
                else:
                    matrix = []
                    next(f)
                    for line in reader:
                        eulerAngles = self.conv_quat_to_euler(line)
                        matrix.append(eulerAngles)
                    return matrix
        else:
            print('!!! ERROR: File not found') 
            return
        
        def conv_quat_to_euler(line):
            if len(line) != 5:
                print ('!!! ERROR: Invalid file')
                return
            time = line[0]
            qw = line[1]
            qx = line[2]
            qy = line[3]
            qz = line[4]
            eulerAngles = list(misc_Functions.quat_to_euler(qw,qx,qy,qz, degrees=False))
            eulerAngles.insert(0, time) ##time in matrix?
            return eulerAngles
            
        
        def graph_Movement(self,filename='headOrientationinEulerAngles.csv',plotName='movementPlot.png'): ##eulerAngle file
        
            if 'inEulerAngles.csv' not in filename and '.csv' in filename:
                filename = self.quatFile_to_eulerFile(filename)
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
                    next(f) ##skip header line
                    for line in reader:
                        if len(line) != 4:
                            print ('!!! ERROR: Invalid file')
                            return
                        eulerAngleSum = (float(line[1]) + float(line[2]) + float(line[3]))/3 ##ac
                        avgAngle.append(eulerAngleSum)
                        time.append(float(line[0]))
                    count = 1 ##skips first line
                    while count < len(avgAngle):
                        deltaAngle = abs((avgAngle[count])-avgAngle[count-1])
                        deltaTime = abs(time[count]-avgAngle[count-1])
                        y.append(deltaAngle/deltaTime)
                        count += 1
                    x = list(time[1:]) ##skips first time
                    y = list(y)
                    plt.plot(x, y)
                    plt.xlabel('time(ms)')
                    plt.ylabel('angle change over time (rad/s)')
                    plt.title('movement over time')
                    plt.show()
                    plt.savefig(plotName)
            else:
                print('!!! ERROR: File not found')
                return
