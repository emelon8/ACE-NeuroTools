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
        self.file_path = file_path
        self.jobID = jobID
        
    
    def process_calcium_movies(self, parallel=True, n_processes=12, apply_motion_correction=True, save_motion_correction=True, 
                               inspect_motion_correction=False, inspect_corr_PNR=False, downsample_for_corr_PNR=1, run_CNMFE=True, 
                               save_CNMFE_estimates_filepath='estimates.hdf5', deconvolve=False):
        
        """Method for organizing how the calcium movie will be processed"""
        steps_applied = []
        self.data_manager.analysis_params['fnames'] = self.file_path
        self.movie = cm.load(self.file_path)
        self.data_manager.analysis_params['dims'] = self.movie.shape[1:]
        self.data_manager.analysis_params['frame rate'] = self.data_manager.metadata['frameRate']
        self.opts_caiman = cm.source_extraction.cnmf.params.CNMFParams(params_dict=self.data_manager.analysis_params)
        
        if parallel:
            print('Setting up cluster for caiman parallel processing on your computer')
            c, dview, n_processes = cm.cluster.setup_cluster(backend='local', n_processes=n_processes, single_thread=False)
        else:
            dview = None
            n_processes = 1
            
        if apply_motion_correction:
            motion_correction_object, bord_px = self._motion_correction(dview, save_motion_correction)
            if save_motion_correction:
                print('Saving motion corrected movies...')
                motion_corrected_mmap_filepath = cm.save_memmap(motion_correction_object.mmap_file, base_name=self.file_path + "motioncorrectedMMAP", order='C', border_to_0=bord_px) #caiman doesn't like underscores in their file naming logic, Figure out how to save the mmap to our saved file folder
                self.opts_caiman.change_params({'fnames': motion_corrected_mmap_filepath})
            if inspect_motion_correction:
                self._inspect_motion_correction(motion_correction_object)
        else:
            #if no motion correction, create a memory map of our original file
            #currently saves the mmap file to wherever self.filepath is with MMAP appended
            mmap_filepath = cm.save_memmap(self.opts_caiman.get('data', 'fnames'), base_name=self.file_path + "MMAP", order='C',
                                       border_to_0=0,
                                       dview=dview)
            self.opts_caiman.change_params({'fnames': mmap_filepath})
            
        Yr, dims_new, T = cm.load_memmap(self.opts_caiman.get('data', 'fnames')[0])
        self.opts_caiman.change_params({'dims': dims_new})
        self.images = Yr.T.reshape((T,) + dims_new, order='F')
        
        if inspect_corr_PNR:
            self._corr_PNR(inspect_corr_PNR, downsample_for_corr_PNR)
            
        if run_CNMFE:
            CNMFE_object = self._CNMFE(n_processes, dview=dview)
            self.estimates = CNMFE_object.estimates
                    
        if deconvolve:
            self._deconvolve()
            
        
        if save_CNMFE_estimates_filepath:
            self.CNMFE_filepath = os.path.join(self.data_manager.metadata['calcium imaging directory'], self.jobID + save_CNMFE_estimates_filepath) #figure out how to save this to our saved file folder, MovieIO currently is not robust enough
            print('Saving CNMF-E estimates in ' + self.CNMFE_filepath)
            filepath = CNMFE_object.save(self.CNMFE_file) #saves the estimates from CNMFE to a file
        
        try:
            cm.stop_server(dview=dview)
        except:
            raise("Error, could't stop caiman processing")
        return filepath, self.opts_caiman
            
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        


    def _motion_correction(self, dview=None, save_movie=False):
        """Use motion correction to correct for movement during the calcium movies."""
        print('Setting up motion correction object...')
        mc = cm.motion_correction.MotionCorrect(self.opts_caiman.get('data', 'fnames'), dview=dview,
                                                **self.opts_caiman.get_group('motion'))
        print('Motion correcting...')
        mc.motion_correct(save_movie=save_movie)
        if self.opts_caiman.get('motion', 'pw_rigid'):
            bord_px = np.ceil(np.maximum(np.max(np.abs(mc.x_shifts_els)), np.max(np.abs(mc.y_shifts_els)))).astype(int)
        else:
            bord_px = np.ceil(np.max(np.abs(mc.shifts_rig))).astype(int)
        bord_px = 0 if self.opts_caiman.get('motion', 'border_nan') == 'copy' else bord_px
        self.opts_caiman.change_params({'border_pix': bord_px})
        return mc, bord_px


    def _CNMFE(self, nProcesses, dview):
        """Segments neurons, demixes spatially overlapping neurons, and denoises the calcium activity from calcium movies.
        See paper describing the method: https://www.cell.com/neuron/fulltext/S0896-6273(15)01084-3"""
        print('Setting up CNMF-E object...')
        cnm = cm.source_extraction.cnmf.CNMF(n_processes=nProcesses, dview=dview, Ain=None, params=self.opts_caiman)
        print('Running CNMF-E...')
        cnm.fit(self.images)
        return cnm


    def _deconvolve(self, p=None, method_deconvolution=None, bas_nonneg=None,
                    noise_method=None, optimize_g=0, s_min=None, **kwargs):
        """Performs deconvolution on already extracted traces using
        constrained foopsi.
        """
        print('Setting up for deconvolution...')
        p = (self.opts_caiman.get('preprocess', 'p')
             if p is None else p)
        method_deconvolution = (self.opts_caiman.get('temporal', 'method_deconvolution')
                                if method_deconvolution is None else method_deconvolution)
        bas_nonneg = (self.opts_caiman.get('temporal', 'bas_nonneg')
                      if bas_nonneg is None else bas_nonneg)
        noise_method = (self.opts_caiman.get('temporal', 'noise_method')
                        if noise_method is None else noise_method)
        s_min = self.opts_caiman.get('temporal', 's_min') if s_min is None else s_min

        F = self.estimates.C + self.estimates.YrA
        args = dict()
        args['p'] = p
        args['method_deconvolution'] = method_deconvolution
        args['bas_nonneg'] = bas_nonneg
        args['noise_method'] = noise_method
        args['s_min'] = s_min
        args['optimize_g'] = optimize_g
        args['noise_range'] = self.opts_caiman.get('temporal', 'noise_range')
        args['fudge_factor'] = self.opts_caiman.get('temporal', 'fudge_factor')

        args_in = [(F[jj], None, jj, None, None, None, None,
                    args) for jj in range(F.shape[0])]

        print('Deconvolving...')
        if 'multiprocessing' in str(type(self.dview)):
            fluor = self.opts_caiman
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

    def _inspectMotionCorrection(self, mc, plot_rigid_motion_correction=True, plot_shifts=True, play_concatenated_movies=True,
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

    def _corr_PNR(self, inspect_corr_PNR, down_sample_for_corr_PNR):
        """Create the correlation and peak-noise-ratio (PNR) images and, if desired, inspect them with an interactive plot to determine min_corr and min_pnr."""
        print('Creating correlation and peak-noise-ratio images...')
        self.cn_filter, self.pnr = cm.summary_images.correlation_pnr(self.images[::down_sample_for_corr_PNR],
                                                                     gSig=self.opts_caiman.get('init', 'gSig')[0],
                                                                     swap_dim=False)
        if inspect_corr_PNR:
            cm.utils.visualization.inspect_correlation_pnr(self.cn_filter, self.pnr)
