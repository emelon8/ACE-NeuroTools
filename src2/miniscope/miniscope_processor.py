from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
import src2.shared.misc_functions as misc_functions
import caiman as cm
import numpy as np
import matplotlib.pyplot as plt
import os

class MiniscopeProcessor():
    
    def __init__(self, data_manager: MiniscopeDataManager, file_path):
        self.data_manager = data_manager
        self.__convert_analysis_params_to_ints()
        self.data_manager.analysis_params['fnames'] = file_path
        self.movie = cm.load(file_path)
        self.data_manager.analysis_params['dims'] = self.movie.shape[1:]
        self.data_manager.analysis_params['frame rate'] = self.data_manager.metadata['frameRate']
        self.opts_caiman = cm.source_extraction.cnmf.params.CNMFParams(params_dict=self.data_manager.analysis_params)
        
    
    def process_calcium_movie(self, parallel=True, n_processes=12, apply_motion_correction=True, 
                               inspect_motion_correction=False, inspect_corr_PNR=False, downsample_for_corr_PNR=1, run_CNMFE=True, 
                               save_CNMFE_estimates_filename='estimates.hdf5', deconvolve=False):
        
        """Method for organizing how the calcium movie will be processed"""
        opts_caiman = self.opts_caiman
        
        
        
        if parallel:
            print('Setting up cluster for caiman parallel processing on your computer')
            c, dview, n_processes = cm.cluster.setup_cluster(backend='local', n_processes=n_processes, single_thread=False)
        else:
            dview = None
            n_processes = 1
            
            
            
        if apply_motion_correction:
            motion_correction_object, opts_caiman = self.apply_motion_correction(opts_caiman, dview)
            opts_caiman = self.create_temporary_mmap(motion_correction_object.mmap_file, opts_caiman, opts_caiman.get('patch', 'border_pix'))
            
            if inspect_motion_correction:
                self.inspect_motion_correction(motion_correction_object, opts_caiman, self.movie, self.data_manager.metadata['frameRate'])
                
        else:
            opts_caiman = self.create_temporary_mmap(opts_caiman.get('data', 'fnames'), opts_caiman, opts_caiman.get('patch', 'border_pix'), dview)
            
            
        
        Yr, dims_new, T = cm.load_memmap(self.opts_caiman.get('data', 'fnames')[0])
        opts_caiman.change_params({'dims': dims_new})
        self.images = Yr.T.reshape((T,) + dims_new, order='F')
        print(opts_caiman.get('patch', 'rf'))
        print(opts_caiman.get('patch', 'stride'))
        
        
        
        
        if inspect_corr_PNR:
            self.corr_PNR(inspect_corr_PNR, downsample_for_corr_PNR, opts_caiman, self.images)
        
            
            
        if run_CNMFE:
            CNMFE_object = self.run_CNMFE(n_processes, opts_caiman, self.images, dview=dview)
            estimates = CNMFE_object.estimates
                    
            if deconvolve:
                estimates.deconvolve(opts_caiman, dview=dview)
            
            if save_CNMFE_estimates_filename:
                CNMFE_filepath = os.path.join(self.data_manager.metadata['calcium imaging directory'],"saved_movies", save_CNMFE_estimates_filename)
                print('Saving CNMF-E estimates in ' + CNMFE_filepath)
                estimates_filepath = CNMFE_object.save(CNMFE_filepath) #saves the estimates from CNMFE to a file
        
        
        
        try:
            cm.stop_server(dview=dview)
        except:
            raise RuntimeError("Error, couldn't stop CaImAn processing")
        
        try:
            return estimates_filepath, opts_caiman
        except:
            return opts_caiman
        
        
        
        
        
        
        
        


    def apply_motion_correction(self, opts_caiman, dview=None):
        """Motion corrects using a passed in caiman parameters object opts_caiman and calculates bord_px"""
        mc = cm.motion_correction.MotionCorrect(opts_caiman.get('data', 'fnames'), dview=dview, **opts_caiman.get_group('motion'))
        print('Motion correcting...')
        #save_movie=True below saves the a .npz file for the motion corrected movie to the same folder as self.file_path
        mc.motion_correct(save_movie=True)
        if opts_caiman.get('motion', 'pw_rigid'):
            bord_px = np.ceil(np.maximum(np.max(np.abs(mc.x_shifts_els)), np.max(np.abs(mc.y_shifts_els)))).astype(int)
        else:
            bord_px = np.ceil(np.max(np.abs(mc.shifts_rig))).astype(int)
        bord_px = 0 if opts_caiman.get('motion', 'border_nan') == 'copy' else bord_px
        opts_caiman.change_params({'border_pix': bord_px})
        return mc, opts_caiman
    
    
    def create_temporary_mmap(self, filepath, opts_caiman, bord_px, dview=None):
        motion_corrected_mmap_filepath = cm.save_memmap(filepath, base_name="", order='C', border_to_0=bord_px, dview=dview)
        opts_caiman.change_params({'fnames': motion_corrected_mmap_filepath})
        return opts_caiman


    def run_CNMFE(self, n_processes, opts_caiman, images, dview):
        """Segments neurons, demixes spatially overlapping neurons, and denoises the calcium activity from calcium movies.
        See paper describing the method: https://www.cell.com/neuron/fulltext/S0896-6273(15)01084-3"""
        print('Setting up CNMF-E object...')
        cnm = cm.source_extraction.cnmf.CNMF(n_processes=n_processes, dview=dview, Ain=None, params=opts_caiman)
        print('Running CNMF-E...')
        cnm.fit(images)
        return cnm


    def inspect_motion_correction(self, mc, opts_caiman, caiman_movie, frame_rate, plot_rigid_motion_correction=True, plot_shifts=True, play_concatenated_movies=True,
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
            if opts_caiman.get('motion', 'pw_rigid'):
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
                cm.concatenate([caiman_movie.resize(1, 1, down_sample_ratio) - mc.min_mov * mc.nonneg_movie,
                                mcMovie.resize(1, 1, down_sample_ratio)], axis=2).play(fr=frame_rate,
                                                                                     q_max=99.5, magnification=2,
                                                                                     bord_px=opts_caiman.get(
                                                                                         'patch', 'border_pix'))
            if plot_correlation:
                h, ax = misc_functions._prepAxes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
                ax[0].imshow(caiman_movie.local_correlations(eight_neighbours=True, swap_dim=False))
                ax[1].imshow(mcMovie.local_correlations(eight_neighbours=True, swap_dim=False))

        if plot_advanced_MC_inspection:
            final_size = np.subtract(opts_caiman.get('data', 'dims'),
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

            # plot the results of Residual Optical Flow, This code block below didn't work in old miniscope on Nathan's mac. It will run now, but I still don't think it works
            fls = [os.path.splitext(mc.fname[0])[0] + '_metrics.npz', os.path.splitext(mc.mmap_file[0])[0] + '_metrics.npz']

            h, ax = misc_functions._prepAxes(title=['Mean', 'Corr Image', 'Mean Optical Flow', '', '', ''],
                                             xLabel=['Original', '', '', 'Motion Corrected', '', ''], yLabel=['', '', '', '', '', ''],
                                             subPlots=[2, 3])
            
            
            for cnt, fl in zip(range(len(fls)), fls):
                print(f"loading file into numpy: {fl}")
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


    def corr_PNR(self, inspect_corr_PNR, down_sample_for_corr_PNR, opts_caiman, images):
        """Create the correlation and peak-noise-ratio (PNR) images and, if desired, inspect them with an interactive plot to determine min_corr and min_pnr."""
        print('Creating correlation and peak-noise-ratio images...')
        cn_filter, pnr = cm.summary_images.correlation_pnr(images[::down_sample_for_corr_PNR], gSig=opts_caiman.get('init', 'gSig')[0], swap_dim=False)
        if inspect_corr_PNR:
            cm.utils.visualization.inspect_correlation_pnr(cn_filter, pnr)
        return cn_filter, pnr
            
            
            
            
            
    def __convert_analysis_params_to_ints(self):
        for key, value in self.data_manager.analysis_params.items():
            if isinstance(value, float):
                try:
                    self.data_manager.analysis_params[key] = int(value)
                except:
                    continue
                