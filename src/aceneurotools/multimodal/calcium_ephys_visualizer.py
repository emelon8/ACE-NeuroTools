import os
from typing import TYPE_CHECKING

import caiman as cm
import matplotlib.animation as animation
import matplotlib.pyplot as plt
import numpy as np

from aceneurotools.config.config_utils import get_coords_dict_from_analysis_params
from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor
from aceneurotools.multimodal.alignment import find_ca_movie_filenums
from aceneurotools.shared.path_finder import PathFinder

if TYPE_CHECKING:
    from aceneurotools.ephys.channel import Channel
    from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager


def create_ca_ephys_movie(
    miniscope_dm: "MiniscopeDataManager",
    ephys_idx_all_TTL_events: np.ndarray,
    channel_object: "Channel",
    time_range: list[float] | None = None,
    movie_num: int | None = None,
    crop: bool = False,
    crop_coords: list[int] | tuple[int, int, int, int] | None = None,
    plot_mean_fluorescence: bool = False,
    df_over_sqrt_f: bool = False,
    vmin: float | None = None,
    vmax: float | None = None,
    mark_start_systemic: bool = True,
    plot_ephys: bool = True,
    num_frames_of_traces: int = 10,
    time_stamps: bool = True,
    playback_interval: int = 33,
    play_movie: bool = True,
    save_movie: bool = False,
) -> None:
    """
    Accepts a list/integer for time_range or movie_num but only one parameter should have a value
    Display a calcium imaging movie that has a specific ephys signal overlayed. Which miniscope video is displayed depends on time_range or movie_num
    Which ephys channel signal is displayed depends on which channel object is passed in.

    channel_object expects you to have already prepared it for visualization before being passed in (applied filters etc)
    time_range: A time range of which movies you want displayed
    movie_num: An integer if you just want to dispay a specific movie (ie. pass in 0 if you want to see 'miniscope_dir/Miniscope/0.avi')
    save_movie: saves the movie to the 'saved_movies' folder in your miniscope directory
    """

    if miniscope_dm.metadata is None:
        print("Error: Miniscope metadata is missing. Cannot proceed.")
        return

    miniscope_dir_path = str(miniscope_dm.metadata["calcium imaging directory"])

    if not plot_ephys and not plot_mean_fluorescence:
        print("Note: you have chosen not to overlay an ephys signal nor the mean fluroescence.")
        return

    if type(time_range) is list:
        if movie_num is not None:
            print("Please only provide either a time range or a video number, not both! Proceeding with time range...")
        movie_filepaths_in_range, movie_frames = find_ca_movie_filenums(
            channel_object, ephys_idx_all_TTL_events, miniscope_dm, time_range
        )
        movie = cm.load_movie_chain(movie_filepaths_in_range)
    elif type(movie_num) is int:
        movie_filepaths = PathFinder.find(miniscope_dir_path, suffix=".avi", prefix=str(movie_num))
        if movie_filepaths is None or len(movie_filepaths) == 0:
            print(f"Error: Could not find movie {movie_num}.avi in {miniscope_dir_path}")
            return
        movie = cm.load(str(movie_filepaths[0]))
        movie_frames = np.zeros(2, dtype=int)
        movie_frames[0] = movie_num * int(miniscope_dm.metadata.get("framesPerFile", 1000))  # Start frame of movieNum
        movie_frames[1] = (movie_num + 1) * int(
            miniscope_dm.metadata.get("framesPerFile", 1000)
        ) - 1  # End frame of movieNum
    else:
        print("Please provide either a time range or a movie number!")
        return

    # Crop the movie if desired.
    if crop:
        if crop_coords is not None:
            coords_dict = {"x0": crop_coords[0], "y0": crop_coords[1], "x1": crop_coords[2], "y1": crop_coords[3]}
        else:
            coords_dict, _ = get_coords_dict_from_analysis_params(miniscope_dm)
        preprocessor = MiniscopePreprocessor(miniscope_dm)
        projections = preprocessor.compute_projections(movie)
        final_coords = preprocessor.get_crop_coordinates(coords_dict, projections, movie.shape[1], movie.shape[2])
        if final_coords is not None:
            movie, _ = preprocessor.crop_movie(movie, final_coords)

    # Adjust the movie frame numbers so that they are with respect to the imported movies, not the entire recording.
    adjusted_movie_frames = np.zeros(2, dtype=int)
    frames_per_file = int(miniscope_dm.metadata.get("framesPerFile", 1000))
    adjusted_movie_frames[0] = movie_frames[0] % frames_per_file
    adjusted_movie_frames[1] = adjusted_movie_frames[0] + np.diff(movie_frames)[0]
    movie = movie[adjusted_movie_frames[0] : adjusted_movie_frames[1] + 1]

    time_projection = movie.mean(axis=(1, 2))

    if plot_mean_fluorescence:
        time_projection -= np.mean(
            time_projection
        )  # Maybe not needed for the filtered signal, but this is applied to both filtered and non-filtered just in case the filter doesn't exclude the DC component (0 Hz).
    if df_over_sqrt_f:
        preprocessor = MiniscopePreprocessor(miniscope_dm)
        movie = preprocessor.compute_df_over_f(movie)
    if vmin is None:
        vmin = movie.mean() - movie.std() * 0
        print("vmin = " + str(vmin))
    if vmax is None:
        vmax = movie.mean() + movie.std() * 4
        print("vmax = " + str(vmax))
    if mark_start_systemic:
        sys_start_idx = np.where(np.char.find(channel_object.events["labels"], "start") == 0)[0][0]
        print(
            '''Found event labeled: "'''
            + channel_object.events["labels"][sys_start_idx]
            + """" at """
            + str(channel_object.events["timestamps"][sys_start_idx])
            + " s."
        )
        t_ephys_sys_start_idx = np.abs(
            channel_object.time_vector - channel_object.events["timestamps"][sys_start_idx]
        ).argmin()

    # Set up the plot
    fig, ax = plt.subplots(figsize=(5.4, 5.4))
    plt.subplots_adjust(0, 0, 1, 1)

    def update(frame):
        """Update function for animation - renders a single frame.

        Clears axes, draws movie frame, overlays ephys/fluorescence traces,
        and adds timestamps and event markers.

        Args:
            frame: Frame index to render.
        """
        # Initialize variables to avoid unbound name errors
        mean_fluorescence_segment: np.ndarray | None = None
        ephys_segment: np.ndarray | None = None

        # Clear the plot
        ax.clear()

        # Plot the frame
        ax.imshow(movie[frame], vmin=vmin, vmax=vmax, cmap="gray")

        if plot_mean_fluorescence:
            if frame >= num_frames_of_traces:
                mean_fluorescence_segment = time_projection[frame - num_frames_of_traces : frame]
            else:
                mean_fluorescence_segment = np.concatenate(
                    (np.ones(num_frames_of_traces - frame) * np.nan, time_projection[0:frame])
                )

        # Get the corresponding segment of the ephys recording
        frame += movie_frames[0]
        if plot_ephys:
            if frame >= num_frames_of_traces + movie_frames[0]:
                ephys_segment = channel_object.signal[
                    ephys_idx_all_TTL_events[frame - num_frames_of_traces] : ephys_idx_all_TTL_events[frame]
                ]
            else:
                # ephys_segment = self.ephys[channel_object][ephys_idx_all_TTL_events[frame]-num_frames_of_traces*round(self.samplingRate[channel_object]/self.experiment['frameRate']):ephys_idx_all_TTL_events[frame]] # This makes it so it plots the ephys from before the created movie started.
                frame_rate = float(miniscope_dm.metadata.get("frameRate", 30.0))
                ephys_segment = np.concatenate(
                    (
                        np.ones(
                            (num_frames_of_traces - frame + movie_frames[0])
                            * round(channel_object.sampling_rate / frame_rate)
                        )
                        * np.nan,
                        channel_object.signal[
                            ephys_idx_all_TTL_events[movie_frames[0]] : ephys_idx_all_TTL_events[frame]
                        ],
                    )
                )

        # Plot the segment on top of the frame
        if plot_mean_fluorescence and isinstance(mean_fluorescence_segment, np.ndarray):
            fluorescence_scaling = (movie.shape[1] / 3) / np.max(np.abs(time_projection))
            ax.plot(
                np.linspace(-0.5, movie.shape[2] - 0.5, len(mean_fluorescence_segment)),
                mean_fluorescence_segment * fluorescence_scaling + (movie.shape[1] / 6),
                color="blue",
                linewidth=2,
            )
        if plot_ephys and isinstance(ephys_segment, np.ndarray):
            ephys_scaling = movie.shape[1] / np.max(np.abs(channel_object.signal))
            ax.plot(
                np.linspace(-0.5, movie.shape[2] - 0.5, len(ephys_segment)),
                ephys_segment * ephys_scaling + (movie.shape[1] / 6),
                color="red",
                linewidth=2,
            )
        if time_stamps:
            time_stamp = (
                channel_object.time_vector[ephys_idx_all_TTL_events[frame]]
                - channel_object.time_vector[ephys_idx_all_TTL_events[movie_frames[0]]]
            )
            ax.text(
                0.9375 * movie.shape[2],
                10 * movie.shape[1] / 608,
                f"{time_stamp:.2f}" + " s",
                ha="right",
                color=[1, 1, 1],
            )  # Also could do color=[0.7,0.7,1]
        if mark_start_systemic:
            total_sys_time = miniscope_dm.metadata.get("total systemic time (min)", 0)
            sys_drug = miniscope_dm.metadata.get("systemic drug", "Drug")
            if (ephys_idx_all_TTL_events[frame] >= t_ephys_sys_start_idx) and (
                ephys_idx_all_TTL_events[frame]
                < t_ephys_sys_start_idx + int(float(total_sys_time) * 60 * channel_object.sampling_rate)
            ):
                ax.text(
                    0.0625 * movie.shape[2],
                    550 * movie.shape[1] / 608,
                    str(sys_drug) + " infusion",
                    ha="left",
                    color=[1, 0, 0],
                )
        ax.set_xlim(-0.5, movie.shape[2] - 0.5)
        ax.set_ylim(-0.5, movie.shape[1] - 0.5)
        ax.set_axis_off()
        return []

    # Create the animation
    ani = animation.FuncAnimation(fig, update, frames=len(movie), interval=playback_interval, repeat=False)

    # Display the animation
    if play_movie:
        plt.show()

    # Save the animation
    if save_movie:
        dir_str = os.path.join(miniscope_dir_path, "saved_movies")
        ani.save(os.path.join(dir_str, "miniscope_ephys_animation" + ".mp4"), dpi=300)
