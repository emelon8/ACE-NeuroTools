from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.miniscope.movie_io import MovieIO
from src2.shared.path_finder import PathFinder
import src2.shared.misc_functions as misc_functions
import caiman as cm
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

class MiniscopeProcessor():
    
    def __init__(self, data_manager: MiniscopeDataManager, file_path, jobID=""):
        self.data_manager = data_manager
        self.__convert_analysis_params_to_ints()
        self.file_path = file_path
        self.jobID = jobID
        self.data_manager.analysis_params['fnames'] = self.file_path
        self.movie = cm.load(self.file_path)
        self.data_manager.analysis_params['dims'] = self.movie.shape[1:]
        self.data_manager.analysis_params['frame rate'] = self.data_manager.metadata['frameRate']
        self.opts_caiman = cm.source_extraction.cnmf.params.CNMFParams(params_dict=self.data_manager.analysis_params)
        
    
    def process_calcium_movies(self, parallel=True, n_processes=12, apply_motion_correction=True, save_motion_correction=True, 
                               inspect_motion_correction=False, inspect_corr_PNR=False, downsample_for_corr_PNR=1, run_CNMFE=True, 
                               save_CNMFE_estimates_filepath='estimates.hdf5', deconvolve=False):
        
        """Method for organizing how the calcium movie will be processed"""
        
        if parallel:
            print('Setting up cluster for caiman parallel processing on your computer')
            c, dview, n_processes = cm.cluster.setup_cluster(backend='local', n_processes=n_processes, single_thread=False)
        else:
            dview = None
            n_processes = 1
            
            
        if apply_motion_correction:
            motion_correction_object, bord_px = self._motion_correction(dview, save_motion_correction)
            if save_motion_correction: #This if-block does not save anything to disk. It turns our motion_corrected.npz fileninto a temporary mmap that will be used for CNMFE       
                self._create_temporary_motion_corrected_mmap(motion_correction_object.mmap_file, bord_px)
            if inspect_motion_correction:
                self._inspect_motion_correction(motion_correction_object)
        else:
            mmap_filepath = cm.save_memmap(self.opts_caiman.get('data', 'fnames'), order='C',
                                       border_to_0=0,
                                       dview=dview)
            self.opts_caiman.change_params({'fnames': mmap_filepath})
            
        
        Yr, dims_new, T = cm.load_memmap(self.opts_caiman.get('data', 'fnames')[0])
        self.opts_caiman.change_params({'dims': dims_new})
        self.images = Yr.T.reshape((T,) + dims_new, order='F')
        print(self.opts_caiman.get('patch', 'rf'))
        print(self.opts_caiman.get('patch', 'stride'))
        
        if inspect_corr_PNR:
            self._corr_PNR(inspect_corr_PNR, downsample_for_corr_PNR)
            
            
        if run_CNMFE:
            CNMFE_object = self._CNMFE(n_processes, dview=dview)
            self.estimates = CNMFE_object.estimates
                    
            
        if deconvolve:
            self.estimates.deconvolve(self.opts_caiman, dview=dview)
            
        
        if save_CNMFE_estimates_filepath:
            self.CNMFE_filepath = os.path.join(self.data_manager.metadata['calcium imaging directory'],"saved_movies", self.jobID + save_CNMFE_estimates_filepath) #figure out how to save this to our saved file folder, MovieIO currently is not robust enough
            print('Saving CNMF-E estimates in ' + self.CNMFE_filepath)
            estimates_filepath = CNMFE_object.save(self.CNMFE_filepath) #saves the estimates from CNMFE to a file
        
        
        try:
            cm.stop_server(dview=dview)
        except:
            raise("Error, could't stop caiman processing")
        return estimates_filepath, self.opts_caiman
            
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        


    def _motion_correction(self, dview=None, save_movie=False):
        """Use motion correction to correct for movement during the calcium movies."""
        mc = cm.motion_correction.MotionCorrect(self.opts_caiman.get('data', 'fnames'), dview=dview,
                                                **self.opts_caiman.get_group('motion'))
        print('Motion correcting...')
        #save_movie=True below saves the a .npz file for the motion corrected movie to the same folder as the original file
        mc.motion_correct(save_movie=save_movie)
        if self.opts_caiman.get('motion', 'pw_rigid'):
            bord_px = np.ceil(np.maximum(np.max(np.abs(mc.x_shifts_els)), np.max(np.abs(mc.y_shifts_els)))).astype(int)
        else:
            bord_px = np.ceil(np.max(np.abs(mc.shifts_rig))).astype(int)
        bord_px = 0 if self.opts_caiman.get('motion', 'border_nan') == 'copy' else bord_px
        self.opts_caiman.change_params({'border_pix': bord_px})
        return mc, bord_px
    
    def _create_temporary_motion_corrected_mmap(self, filepath, bord_px):
        motion_corrected_mmap_filepath = cm.save_memmap(filepath, base_name="", order='C', border_to_0=bord_px)
        self.opts_caiman.change_params({'fnames': motion_corrected_mmap_filepath}) 

    def _CNMFE(self, n_processes, dview):
        """Segments neurons, demixes spatially overlapping neurons, and denoises the calcium activity from calcium movies.
        See paper describing the method: https://www.cell.com/neuron/fulltext/S0896-6273(15)01084-3"""
        print('Setting up CNMF-E object...')
        cnm = cm.source_extraction.cnmf.CNMF(n_processes=n_processes, dview=dview, Ain=None, params=self.opts_caiman)
        print('Running CNMF-E...')
        cnm.fit(self.images)
        return cnm

    def _inspect_motion_correction(self, mc, plot_rigid_motion_correction=True, plot_shifts=True, play_concatenated_movies=True,
                                 down_sample_ratio=0.2, plot_correlation=True, plot_advanced_MC_inspection=True):
        """Various plots and movies to help with the inspection of motion correction effectiveness.
        MC is the motion correction object obtained from SELF._MOTIONCORRECTION().
        PLOTRIGIDMOTIONCORRECTION is a boolean that determines whether rigid motion correction is plotted.
        PLAYCONCATENATEDMOVIES is a boolean that determines whether the original and motion-corrected movies are plotted side-by-side.
        DOWNSAMPLERATIO is a float that determines the factor by which to shrink the duration of the playback (helpful for making the motion more obvious).
        PLOTSHIFTS is a boolean that determines whether to plot the x and y pixel shifts over time.
        PLOTCORRELATION is a boolean that determines whether to plot the correlation images for the original and motion-corrected movies side-by-side.
        """
        print('Inspecting motion correction...')
        if plot_rigid_motion_correction:
            h, ax = misc_functions._prepAxes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
            ax[0].imshow(mc.total_template_rig)  # % plot template
            ax[1].plot(mc.shifts_rig)  # % plot rigid shifts
            ax[1].legend(['X Shifts', 'Y Shifts'])

        if plot_shifts:
            if self.opts_caiman.get('motion', 'pw_rigid'):
                h, ax = misc_functions._prepAxes(xLabel='Frames', yLabel='Pixels')
                ax.plot(mc.shifts_rig)
                ax.legend(['X Shifts', 'Y Shifts'])
            else:
                h, ax = misc_functions._prepAxes(xLabel=['', 'Frames'],
                                                 yLabel=['X Shifts (Pixels)', 'Y Shifts (Pixels)'], subPlots=[2, 1])
                ax[0].plot(mc.x_shifts_els)
                ax[1].plot(mc.y_shifts_els)

        if play_concatenated_movies or plot_correlation:
            mcMovie = cm.load(mc.mmap_file)
            if play_concatenated_movies:
                cm.concatenate([self.movie.resize(1, 1, down_sample_ratio) - mc.min_mov * mc.nonneg_movie,
                                mcMovie.resize(1, 1, down_sample_ratio)], axis=2).play(fr=self.data_manager.metadata['frameRate'],
                                                                                     q_max=99.5, magnification=2,
                                                                                     bord_px=self.opts_caiman.get(
                                                                                         'patch', 'border_pix'))
            if plot_correlation:
                h, ax = misc_functions._prepAxes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
                ax[0].imshow(self.movie.local_correlations(eight_neighbours=True, swap_dim=False))
                ax[1].imshow(mcMovie.local_correlations(eight_neighbours=True, swap_dim=False))

        if plot_advanced_MC_inspection:
            final_size = np.subtract(self.opts_caiman.get('data', 'dims'),
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

            """
            This code block throws an error in both src and src2 on my mac when running the same data. It can't find any .npz files in /Users/nathan/caiman_data/temp'
            
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
                        plt.colorbar(mappable=mappable, ax=ax[3 * cnt + 3]) #FIXME colorbar() is NOT an attribute of ax. It is of plt though"
            """

    def _corr_PNR(self, inspect_corr_PNR, down_sample_for_corr_PNR):
        """Create the correlation and peak-noise-ratio (PNR) images and, if desired, inspect them with an interactive plot to determine min_corr and min_pnr."""
        print('Creating correlation and peak-noise-ratio images...')
        self.cn_filter, self.pnr = cm.summary_images.correlation_pnr(self.images[::down_sample_for_corr_PNR],
                                                                     gSig=self.opts_caiman.get('init', 'gSig')[0],
                                                                     swap_dim=False)
        if inspect_corr_PNR:
            cm.utils.visualization.inspect_correlation_pnr(self.cn_filter, self.pnr)
            
            
            
            
    def __convert_analysis_params_to_ints(self):
        for key, value in self.data_manager.analysis_params.items():
            if isinstance(value, float):
                try:
                    self.data_manager.analysis_params[key] = int(value)
                except:
                    continue
        
