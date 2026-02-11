from src2.miniscope.miniscope_data_manager import MiniscopeDataManager
from src2.shared.exceptions import ProcessingError
import src2.shared.misc_functions as misc_functions
import caiman as cm
import numpy as np
import matplotlib.pyplot as plt
import os
from copy import deepcopy
from src2.miniscope.movie_io import MovieIO
import matplotlib.widgets
import tkinter
import matplotlib


class MiniscopeProcessor:
    """Main processor for calcium imaging movie analysis using CaImAn.
    
    Orchestrates the complete analysis pipeline including motion correction,
    CNMF-E source extraction, and result saving. Works with MiniscopeDataManager
    to track all processing state and outputs.
    
    Attributes:
        data_manager: MiniscopeDataManager containing movie and parameters.
        preprocessed_movie: Copy of original movie before processing.
    """
    
    def __init__(self, data_manager: MiniscopeDataManager):
        """"
        Ensure that data_manager.movie contains the proper movie that you want to process before intializing this class
        
        This class has five main steps:
            1. Set up what processing type you would like to do the next steps with (parellel, how many cores, etc.)
            2. Motion correct (or don't) what is stored in data_manager.movie and save the result as a memory map
            3. Prepare/visualize different things to help you find optimal paramters for running CNMFE (an algorithm that decomposes a movie into multiple matrices)
            4. Run CNMFE using our memory map using the parameters stored in opts_caiman, which draws from analysis_parameters.csv
            5. Save any results
            
        """
        
        self.data_manager = data_manager
        self.preprocessed_movie = deepcopy(data_manager.movie)
        self._prepare_opts_caiman()
        
    
    def process_calcium_movie(self, parallel=True, n_processes=12, apply_motion_correction=True, 
                               inspect_motion_correction=False, plot_params=False, run_CNMFE=True,
                               save_estimates=True, save_CNMFE_estimates_filename='estimates.hdf5', save_CNMFE_params=False):
        """Run the complete calcium movie processing pipeline.
        
        Executes motion correction, CNMF-E source extraction, and saves results.
        This is the main entry point for processing miniscope recordings.
        
        Args:
            parallel: If True, use multiprocessing for CaImAn operations.
            n_processes: Number of parallel processes to use.
            apply_motion_correction: If True, perform motion correction.
            inspect_motion_correction: If True, show motion correction diagnostics.
            plot_params: If True, display CNMF-E parameter tuning plots.
            run_CNMFE: If True, run CNMF-E source extraction algorithm.
            save_estimates: If True, save CNMF-E results to disk.
            save_CNMFE_estimates_filename: Filename for saved estimates.
            save_CNMFE_params: If True, save CaImAn parameters to JSON.
            
        Returns:
            Updated MiniscopeDataManager with processing results.
        """

        #set up processing type
        dview = None
        if parallel:
            print('Setting up cluster for caiman parallel processing on your computer')
            c, dview, n_processes = cm.cluster.setup_cluster(backend='multiprocessing', n_processes=n_processes, single_thread=False)
            
        #Apply motion correction, then saves a memory map to opts_caiman to prepare for CNMFE.
        self.data_manager = self.motion_correction_manager(self.data_manager, dview, apply_motion_correction, inspect_motion_correction)
        
        #Prepare additional analysis parameters for CNMFE
        self.data_manager, images = self.cnmfe_parameter_handler(self.data_manager, plot_params=plot_params)
        
        #intialize CNMFE object
        self.data_manager.CNMFE_obj = cm.source_extraction.cnmf.CNMF(n_processes=n_processes, dview=dview, Ain=None, params=self.data_manager.opts_caiman)
        
        #reupdate data_manager.movie with motion-corrected movie, otherwise the movie returned below is the same if you did not motion correct
        self.data_manager.movie = cm.movie(images, fr=self.data_manager.fr)
            
        #run CNMFE. Do not run unless you have optimal parameters or the neuron estimates will be junk
        if run_CNMFE:
            print('Running CNMFE...')
            try:
                self.data_manager.CNMFE_obj.fit(images)
            except (ValueError, MemoryError, RuntimeError) as e:
                print('CNMFE failed to run. Please check the parameters and try again.')
                print('No estimates were saved to disk. Do not continue to post-processing or multimodal analysis')
                raise ProcessingError(f"CNMFE failed: {e}") from e
            
        #save results 'estimates' to disk and update data_manager with their filepaths
        self.data_manager = self._save_processed_data(self.data_manager, save_estimates, save_CNMFE_estimates_filename, save_CNMFE_params)
        
        try:
            cm.stop_server(dview=dview)
        except (OSError, AttributeError) as e:
            print(f"Warning: could not stop CaImAn processing server: {e}")
        
        return self.data_manager
        
        
        
        
        
    def motion_correction_manager(self, data_manager, dview, apply_motion_correction, inspect_motion_correction):
        """Manage the motion correction workflow.
        
        Applies motion correction if requested, creates memory-mapped files,
        and optionally displays diagnostic visualizations.
        
        Args:
            data_manager: MiniscopeDataManager with movie data.
            dview: CaImAn distributed view object for parallel processing.
            apply_motion_correction: If True, perform motion correction.
            inspect_motion_correction: If True, show before/after comparisons.
            
        Returns:
            Updated data_manager with motion-corrected memory map.
        """
        if apply_motion_correction:
            #apply motion correction
            motion_correction_object, data_manager.opts_caiman = self._apply_motion_correction(data_manager.opts_caiman, dview)
            #save the mmap file to disk and add that filepath to opts_caiman
            data_manager.opts_caiman = self._add_temp_mmap_to_opts_caiman(motion_correction_object.mmap_file, data_manager.opts_caiman, data_manager.opts_caiman.get('patch', 'border_pix'))
            #save the mmap file stored in motion_correction_object to data_manager
        else:
            #add our non-motion-corrected movie to opts_caiman to prepare for CNMFE
            data_manager.opts_caiman = self._add_temp_mmap_to_opts_caiman(data_manager.opts_caiman.get('data', 'fnames'), data_manager.opts_caiman, data_manager.opts_caiman.get('patch', 'border_pix'), dview)
        
        if inspect_motion_correction and apply_motion_correction:
            self.inspect_motion_correction(motion_correction_object, data_manager.opts_caiman, self.preprocessed_movie, self.data_manager.fr)
        
        return data_manager
    
    
    def cnmfe_parameter_handler(self, dm, plot_params=False):
        """
        -This is an important step before CNMFE. It handles the most important CNMFE parameters.
        
        -It uses the 'gsig_tmp' below to make the first plot. Adjust this value until the plot shown does not merge any neurons, 
        then update 'gsig' in analysis_parameters.csv with the best 'gsig_tmp' value
        
        -First, this function calculates correlation and peak to noise ratios and plots them. Use the sliders to adjust 'vmax' until neurons are most visible, 
        then adjust 'min_corr' and 'min_pnr' in analysis_parameters.csv to values slightly below those vmax values
        Example: If neurons are most clear at vmax=0.9, set min_corr=0.8 or 0.85 (slightly below to capture most neurons)

        -Second, it plots your 'rf' and 'stride' values which form patches around your movie. We want to select rf and stride parameters so that 
        at least 3-4 neuron diameters can fit into each patch, and at least one neuron fits in the overlap region between patches.
        If patches and overlaps seem a bit large that is ok: our main concern is that they not be too small.
        """
        
        # Close any existing Tkinter root to avoid conflicts
        if tkinter._default_root:
            tkinter._default_root.destroy()
        # Set Matplotlib backend to Qt5Agg for interactive plotting
        try:
            matplotlib.use('Qt5Agg')
            print("Matplotlib backend set to Qt5Agg")
        except Exception as e:
            print(f"Error setting Qt5Agg backend: {e}")
            matplotlib.use('Agg')  # Fallback to non-interactive backend
            
        #load memory map and recompute movie from it
        Yr, dims, T = cm.load_memmap(dm.opts_caiman.get('data', 'fnames')[0])
        dm.opts_caiman.change_params({'data': {'dims': dims}})
        images = Yr.T.reshape((T,) + dims, order='F')
        
        
        if plot_params:
            #calculate min correlation/min pnr and plot them
            gsig_tmp = (3,3)
            correlation_image, peak_to_noise_ratio = cm.summary_images.correlation_pnr(images[::max(T//1000, 1)], gSig=gsig_tmp[0], swap_dim=False)
            cm.utils.visualization.inspect_correlation_pnr(correlation_image, peak_to_noise_ratio)
            plt.show(block=True)
            
            #Calculate stride/overlap and plot them
            cnmfe_patch_width = dm.opts_caiman.get('patch', 'rf') * 2 + 1
            cnmfe_patch_overlap = dm.opts_caiman.get('patch', 'stride') + 1
            cnmfe_patch_stride = cnmfe_patch_width - cnmfe_patch_overlap
            print(f'Patch width: {cnmfe_patch_width} , Stride: {cnmfe_patch_stride}, Overlap: {cnmfe_patch_overlap}')
            patch_ax = cm.utils.visualization.view_quilt(correlation_image, cnmfe_patch_stride, cnmfe_patch_overlap, vmin=np.percentile(np.ravel(correlation_image), 50), 
                                                         vmax=np.percentile(np.ravel(correlation_image), 99.5), color='yellow', figsize=(4,4))
            patch_ax.set_title(f'CNMFE Patch Width {cnmfe_patch_width}, Overlap {cnmfe_patch_overlap}')
            plt.show(block=True)
            
            #REMEMBER! Change analysis_parameter.csv so that these paramters are optimal BEFORE running CNMFE, then skip this step when they are optimal
        return dm, images


    def inspect_motion_correction(self, mc, opts_caiman, original_movie, frame_rate, plot_rigid_motion_correction=True, plot_shifts=True, 
                                  play_concatenated_movies=True, down_sample_ratio=0.2, plot_correlation=True, plot_advanced_MC_inspection=True):
        """This function is a mess and needs a lot of work. It does not work well at all.
        mc: the motion correction object obtained from apply_motion_correction()
        opts_caiman: a caiman parameters object obtained from cm.CNMFParams()
        original_movie: your movie jsut before motion_correction
        plot_rigid_motion_correction: a boolean that determines whether rigid motion correction is plotted.
        play_concatenated_movies: a boolean that determines whether the original and motion-corrected movies are plotted side-by-side.
        down_sample_ratio: a float that determines the factor by which to shrink the duration of the playback (helpful for making the motion more obvious).
        plot_shifts: a boolean that determines whether to plot the x and y pixel shifts over time.
        plot_correlation: a boolean that determines whether to plot the correlation images for the original and motion-corrected movies side-by-side.
        """
        print('Inspecting motion correction...')
        if plot_rigid_motion_correction:
            h, ax = misc_functions._prep_axes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
            ax[0].imshow(mc.total_template_rig)  # % plot template
            ax[1].plot(mc.shifts_rig)  # % plot rigid shifts
            ax[1].legend(['X Shifts', 'Y Shifts'])

        if plot_shifts:
            if opts_caiman.get('motion', 'pw_rigid'):
                h, ax = misc_functions._prep_axes(xLabel='Frames', yLabel='Pixels')
                ax.plot(mc.shifts_rig)
                ax.legend(['X Shifts', 'Y Shifts'])
            else:
                h, ax = misc_functions._prep_axes(xLabel=['', 'Frames'],
                                                 yLabel=['X Shifts (Pixels)', 'Y Shifts (Pixels)'], subPlots=[2, 1])
                ax[0].plot(mc.x_shifts_els)
                ax[1].plot(mc.y_shifts_els)

        if play_concatenated_movies or plot_correlation:
            mc_movie = cm.load(mc.mmap_file)
            if play_concatenated_movies:
                print("WARNING! The concatenated clips being shown are different in brightness but still represent your movie before and after motion correction.")
                print("The old movie is the one that is not displaying properly, as it needed to be edited temporarily to fit the concatenation process")
                # Get dimensions of motion-corrected movie
                mc_height = mc_movie.shape[1]  # Height (dimension 1)
                mc_width = mc_movie.shape[2]   # Width (dimension 2)
                
                # Crop original movie to match mc_movie dimensions
                before_movie = original_movie[:, 0:mc_height, 0:mc_width]
                
                # Resize movies
                m1 = before_movie.resize(1, 1, down_sample_ratio)
                m2 = mc_movie.resize(1, 1, down_sample_ratio)
                
                # Handle NaN and inf values
                if np.any(np.isnan(m1)) or np.any(np.isinf(m1)):
                    print('Found NaN or inf values in the original movie...')
                    m1[np.isnan(m1) | np.isinf(m1)] = np.nanmean(m1[np.isfinite(m1)])
                if np.any(np.isnan(m2)) or np.any(np.isinf(m2)):
                    print('Found NaN or inf values in the motion-corrected movie...')
                    m2[np.isnan(m2) | np.isinf(m2)] = np.nanmean(m2[np.isfinite(m2)])
                
                # Clip negative values
                m1 = np.clip(m1, 0, None)
                m2 = np.clip(m2, 0, None)
                
                # Independent normalization
                m1 = (m1 - np.min(m1)) / (np.max(m1) - np.min(m1) + 1e-10)
                m2 = (m2 - np.nanmin(m2)) / (np.nanmax(m2) - np.nanmin(m2) + 1e-10)
                
                # Boost m1 brightness
                m1 = np.clip(m1 * 3, 0, 1)  # Adjust multiplier (e.g., 1.2 to 2.0) as needed
            
                # Concatenate and play
                cm.concatenate([m1, m2], axis=2).play(fr=15, gain=1.0, magnification=2)
                
            if plot_correlation:
                h, ax = misc_functions._prep_axes(xLabel=['', 'Frames'], yLabel=['', 'Pixels'], subPlots=[1, 2])
                ax[0].imshow(original_movie.local_correlations(eight_neighbours=True, swap_dim=False))
                ax[1].imshow(mc_movie.local_correlations(eight_neighbours=True, swap_dim=False))

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

            h, ax = misc_functions._prep_axes(xLabel=['Frame', 'Original'], yLabel=['Correlation', 'Motion Corrected'],
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

            h, ax = misc_functions._prep_axes(title=['Mean', 'Corr Image', 'Mean Optical Flow', '', '', ''],
                                             xLabel=['Original', '', '', 'Motion Corrected', '', ''], yLabel=['', '', '', '', '', ''],
                                             subPlots=[2, 3])

            # plot the results of Residual Optical Flow, This code block below didn't work in old miniscope on Nathan's mac. It will run now, but I still don't think it works
            fls = [os.path.splitext(mc.fname[0])[0] + '_metrics.npz', os.path.splitext(mc.mmap_file[0])[0] + '_metrics.npz']

            h, ax = misc_functions._prep_axes(title=['Mean', 'Corr Image', 'Mean Optical Flow', '', '', ''],
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

    
    def _apply_motion_correction(self, opts_caiman, dview=None):
        """Motion corrects using a passed in caiman parameters object opts_caiman and calculates bord_px"""
        mc = cm.motion_correction.MotionCorrect(self.data_manager.preprocessed_movie_filepath, dview=dview, **opts_caiman.get_group('motion'))
        print(f"Motion correcting with these parameters: {opts_caiman.get_group('motion')}")
        
        #save_movie=True below saves a .npz file for the motion corrected movie to the same folder as self.movie_filepath, and allows us to save it as a mmap using method below this one
        mc.motion_correct(save_movie=True)
        if opts_caiman.get('motion', 'pw_rigid'):
            bord_px = np.ceil(np.maximum(np.max(np.abs(mc.x_shifts_els)), np.max(np.abs(mc.y_shifts_els)))).astype(int)
        else:
            bord_px = np.ceil(np.max(np.abs(mc.shifts_rig))).astype(int)
        bord_px = 0 if opts_caiman.get('motion', 'border_nan') == 'copy' else bord_px
        opts_caiman.change_params({'patch': {'border_pix': bord_px}})
        print(f'Updating border_pix with: {bord_px}')
        return mc, opts_caiman
    
    
    def _add_temp_mmap_to_opts_caiman(self, filepath, opts_caiman, bord_px, dview=None):
        """Save movie to memory-mapped file and update CaImAn options.
        
        Creates a C-order memory-mapped file with border pixels set to zero,
        then updates opts_caiman to reference this file.
        
        Args:
            filepath: Path to movie file or existing mmap.
            opts_caiman: CaImAn parameters object to update.
            bord_px: Number of border pixels to set to zero.
            dview: Optional distributed view for parallel saving.
            
        Returns:
            Updated opts_caiman with new mmap filepath.
        """
        motion_corrected_mmap_filepath = cm.save_memmap(filepath, base_name="", order='C', border_to_0=bord_px, dview=dview)
        opts_caiman.change_params({'data': {'fnames': motion_corrected_mmap_filepath}})
        return opts_caiman
    
    
    def _save_processed_data(self, dm, save_estimates, save_CNMFE_estimates_filename, save_CNMFE_params):
        """Save CNMF-E results and parameters to disk.
        
        Saves estimates to HDF5 and optionally saves CaImAn parameters to JSON.
        Updates data_manager with filepaths to saved files.
        
        Args:
            dm: MiniscopeDataManager with processing results.
            save_estimates: If True, save CNMF-E estimates.
            save_CNMFE_estimates_filename: Filename for estimates file.
            save_CNMFE_params: If True, save parameters to JSON.
            
        Returns:
            Updated data_manager with saved file paths.
        """
        if save_estimates and dm.CNMFE_obj is not None:
            save_dir = os.path.join(dm.metadata['calcium imaging directory'], "saved_movies")
            os.makedirs(save_dir, exist_ok=True)
            CNMFE_obj_filepath = os.path.join(save_dir, save_CNMFE_estimates_filename)
            print('Saving CNMF-E estimates in ' + CNMFE_obj_filepath)
            dm.CNMFE_obj.save(CNMFE_obj_filepath) #saves the estimates from CNMFE to a file
            dm.estimates_filepath = CNMFE_obj_filepath
        
        if save_CNMFE_params:
            opts_caiman_json_filepath = os.path.join(dm.metadata['calcium imaging directory'], "saved_movies", "opts_caiman.json")
            dm.opts_caiman.to_jsonfile(targfn=opts_caiman_json_filepath)
            dm.opts_caiman_filepath = opts_caiman_json_filepath
        
        return dm
            
            
    def _prepare_opts_caiman(self):
        """Prepare CaImAn parameters from analysis_params.
        
        Cleans and structures the flat analysis_params dictionary into
        the grouped format expected by CaImAn's CNMFParams. Removes
        experiment-specific keys and maps each parameter to its correct
        parameter group (data, patch, init, spatial, temporal, etc.).
        
        Returns:
            CaImAn CNMFParams object configured for CNMF-E.
        """
        #convert any analysis_params ending in .0 to integers, adds any needed params
        for key, value in self.data_manager.analysis_params.items():
            if isinstance(value, float) and value.is_integer():
                self.data_manager.analysis_params[key] = int(value)
        
        print(f'updated dimensions in bottom with {self.data_manager.movie.shape[1:]}')
        self.data_manager.analysis_params['fnames'] = self.data_manager.preprocessed_movie_filepath
        self.data_manager.analysis_params['dims'] = self.data_manager.movie.shape[1:]
        self.data_manager.analysis_params['fr'] = self.data_manager.fr
        
        # Create a clean dictionary for CaImAn
        caiman_params = self.data_manager.analysis_params.copy()
        keys_to_remove = [
            'line number', 'id', 'date (YYMMDD)', 'Box calcium folder ID', 
            'calcium imaging directory', 'Box ephys folder ID', 'ephys directory', 
            'indices of TTL events to delete', 'zero time (s)', 'baseline period (min)', 
            'crop', 'periods of high slow wave power (s)', 'control periods (s)', 
            'ca_ephys_baseline_video_num', 'ca_ephys_slow_wave_video_num', 
            'ca_ephys_burst_suppression_video_num', 'comments'
        ]
        
        for key in keys_to_remove:
            caiman_params.pop(key, None)

        # Define parameter groups to map flat parameters to their respective groups
        # This prevents the "non-pathed parameters" deprecation warning in CaImAn
        structured_params = {}
        
        # Based on CaImAn CNMFParams groups
        param_groups = {
            'data': ['fnames', 'dims', 'fr', 'decay_time', 'dxy', 'var_name_hdf5', 'caiman_version', 'last_commit'],
            'patch': ['border_pix', 'del_duplicates', 'in_memory', 'low_rank_background', 'memory_fact', 'n_processes', 'nb_patch', 'only_init', 'p_patch', 'remove_very_bad_comps', 'rf', 'skip_refinement', 'p_ssub', 'stride', 'p_tsub'],
            'preprocess': ['check_nan', 'compute_g', 'include_noise', 'lags', 'max_num_samples_fft', 'n_pixels_per_process', 'noise_method', 'noise_range', 'p', 'pixels', 'sn'],
            'init': ['K', 'SC_kernel', 'SC_sigma', 'SC_thr', 'SC_normalize', 'SC_use_NN', 'SC_nnn', 'alpha_snmf', 'center_psf', 'gSig', 'gSiz', 'greedyroi_nmf_init_method', 'greedyroi_nmf_max_iter', 'init_iter', 'kernel', 'lambda_gnmf', 'snmf_l1_ratio', 'maxIter', 'max_iter_snmf', 'method_init', 'min_corr', 'min_pnr', 'nIter', 'nb', 'normalize_init', 'options_local_NMF', 'perc_baseline_snmf', 'ring_size_factor', 'rolling_length', 'rolling_sum', 'seed_method', 'sigma_smooth_snmf', 'ssub', 'ssub_B', 'tsub'],
            'spatial': ['dist', 'expandCore', 'extract_cc', 'maxthr', 'medw', 'method_exp', 'method_ls', 'n_pixels_per_process', 'normalize_yyt_one', 'nrgthr', 'num_blocks_per_run_spat', 'se', 'ss', 'thr_method', 'update_background_components'],
            'temporal': ['ITER', 'bas_nonneg', 'block_size_temp', 'fudge_factor', 'lags', 'optimize_g', 'method_deconvolution', 'noise_method', 'noise_range', 'num_blocks_per_run_temp', 'p', 's_min', 'solvers', 'verbosity'],
            'merging': ['do_merge', 'merge_thr', 'merge_parallel'],
            'quality': ['SNR_lowest', 'cnn_lowest', 'gSig_range', 'min_SNR', 'min_cnn_thr', 'rval_lowest', 'rval_thr', 'use_cnn', 'use_ecc', 'max_ecc'],
            'online': ['N_samples_exceptionality', 'batch_update_suff_stat', 'dist_shape_update', 'ds_factor', 'epochs', 'expected_comps', 'full_XXt', 'init_batch', 'init_method', 'iters_shape', 'max_comp_update_shape', 'max_num_added', 'max_shifts_online', 'min_SNR', 'min_num_trial', 'minibatch_shape', 'minibatch_suff_stat', 'motion_correct', 'movie_name_online', 'normalize', 'n_refit', 'num_times_comp_updated', 'opencv_codec', 'path_to_model', 'ring_CNN', 'rval_thr', 'save_online_movie', 'show_movie', 'simultaneously', 'sniper_mode', 'stop_detection', 'test_both', 'thresh_CNN_noisy', 'thresh_fitness_delta', 'thresh_fitness_raw', 'thresh_overlap', 'update_freq', 'update_num_comps', 'use_corr_img', 'use_dense', 'use_peak_max', 'W_update_factor'],
            'motion': ['border_nan', 'gSig_filt', 'is3D', 'max_deviation_rigid', 'max_shifts', 'min_mov', 'niter_rig', 'nonneg_movie', 'num_frames_split', 'num_splits_to_process_els', 'num_splits_to_process_rig', 'overlaps', 'pw_rigid', 'shifts_interpolate', 'shifts_opencv', 'splits_els', 'splits_rig', 'strides', 'upsample_factor_grid', 'use_cuda', 'indices'],
            'ring_CNN': ['n_channels', 'use_bias', 'use_add', 'pct', 'patience', 'max_epochs', 'width', 'loss_fn', 'lr', 'lr_scheduler', 'path_to_model', 'remove_activity', 'reuse_model']
        }

        # Reverse mapping for easy lookup
        key_to_groups = {}
        for group, keys in param_groups.items():
            for key in keys:
                if key not in key_to_groups:
                    key_to_groups[key] = []
                key_to_groups[key].append(group)
        
        for key, value in caiman_params.items():
            if key in key_to_groups:
                for group in key_to_groups[key]:
                    if group not in structured_params:
                        structured_params[group] = {}
                    structured_params[group][key] = value
            else:
                 # If parameter is not known, we can attempt to put it in 'data' or log a warning
                 print(f"Warning: Parameter '{key}' is not recognized in the standard CaImAn groups. It will be ignored.")

        self.data_manager.opts_caiman = cm.source_extraction.cnmf.params.CNMFParams(params_dict=structured_params) #intialize caiman CNMFParams object
                