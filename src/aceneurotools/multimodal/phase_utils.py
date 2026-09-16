from typing import TYPE_CHECKING, Any, cast

import numpy as np

from aceneurotools.shared.plotting import prep_axes

if TYPE_CHECKING:
    from aceneurotools.ephys.channel import Channel


def ephys_phase_ca_events(
    ephys_idx_ca_events: dict[int, np.ndarray],
    channel_object: 'Channel',
    neurons: str | list[int] = 'all'
) -> dict[int, np.ndarray]:
    """Compare calcium events to the phase extracted from a specified ephys channel.
    channel_object: channel object containing channel_name, signal, time_vector, smapling_rate, and the phases of the signal
    neurons: the neuron number (i.e., the integer row number in self.estimates.C, starting with 0) of the neuron you want to compare. If you want to compare all of the neurons in the recording, pass 'all' as the argument."""
    print('Comparing the calcium events to the corresponding phase of ' + channel_object.name + '...')
    if neurons == 'all':
        neurons_list = list(ephys_idx_ca_events.keys())
    elif not isinstance(neurons, list):
        neurons_list = [int(neurons)]
    else:
        neurons_list = [int(n) for n in neurons]

    if channel_object.phases is None:
        raise ValueError(f"Phases for channel {channel_object.name} have not been calculated.")

    ca_events_phases_ephys: dict[int, np.ndarray] = {}
    for k in neurons_list:
        phases_list = []
        for j in range(len(ephys_idx_ca_events[k])):
            phases_list.append(channel_object.phases[ephys_idx_ca_events[k][j]])
        ca_events_phases_ephys[k] = np.array(phases_list)

    return ca_events_phases_ephys


def miniscope_phase_ca_events(
    ca_events_idx: dict[int, np.ndarray],
    miniscope_phases: np.ndarray,
    neurons: str | list[int] | int = 'all'
) -> dict[int, np.ndarray]:
    """Compare calcium events to the phase extracted from the mean fluorescence of the (cropped) miniscope recording.
    miniscope_phases: the phase calculatied from the movie that is given to MiniscopePostprocessor
    neurons: the neuron number (i.e., the integer row number in self.estimates.C, starting with 0) of the neuron you want to compare. If you want to compare all of the neurons in the recording, pass 'all' as the argument."""
    print('Comparing the calcium events to the corresponding phase of the mean fluorescence of the (cropped) miniscope recording...')
    if neurons == 'all':
        neurons_list = list(ca_events_idx.keys())
    elif not isinstance(neurons, list):
        neurons_list = [int(neurons)]
    else:
        neurons_list = [int(n) for n in neurons]

    ca_events_phases_miniscope: dict[int, np.ndarray] = {}
    for k in neurons_list:
        phases_list = []
        for j in range(len(ca_events_idx[k])):
            phases_list.append(miniscope_phases[ca_events_idx[k][j]])
        ca_events_phases_miniscope[k] = np.array(phases_list)

    return ca_events_phases_miniscope



def phase_ca_events_histogram(
    ca_events_phases: dict[int, np.ndarray],
    neurons: str | list[int] | int = 'all',
    bins: int = 18,
    hist_range: tuple[float, float] = (-np.pi, np.pi),
    density: bool = False,
    mean_density: bool = False,
    combined: bool = True,
    plot_histogram: bool = True
) -> tuple[np.ndarray, np.ndarray] | tuple[np.ndarray, np.ndarray, float, float] | tuple[dict[int, np.ndarray], dict[int, np.ndarray]]:
    """Compute the histogram of calcium events/probability density vs phase.
    Leave the parameters in their default values if you want to plot a combined histogram of phase counts of all neurons

    neuron: a list of the neuron indexes to compare. All neurons can be selected with 'all'.
    bins: the number of bins to sort the data into.
    hist_range: a tuple of the range that the bins should cover.
    density: determines whether the data will be bins will represent a probability density or a count.
    mean_density: provides the mean of the density histograms of all specified neurons.
    plot_histogram: chooses whether or not to plot the computed histogram.
    combined: a boolean that determines whether to combine the data from all of the specified neurons or whether to create histograms for each of the specified neurons.
    
    """

    if neurons != 'all' and not isinstance(neurons, list):
        neurons_list_hist: list[int] = [int(neurons)]
    elif isinstance(neurons, list):
        neurons_list_hist = [int(n) for n in neurons]
    else:
        neurons_list_hist = list(ca_events_phases.keys())

    if not plot_histogram:
            #calculates histograms but does not plot them
            hist, bin_edges = _calculate_histograms_without_plotting(ca_events_phases, neurons_list_hist, bins, hist_range, density, combined)
            return cast(Any, (hist, bin_edges))

    if mean_density and neurons == 'all':
        #plot the mean of the density histogram of phases of all neurons
        hist_tuple = _mean_density_histogram(ca_events_phases, neurons, bins, hist_range)
        return cast(Any, hist_tuple)

    if combined:
        if neurons == 'all':
            if density:
                #plot the probability density of phases of all neurons
                hist_ret, bin_edges_ret = cast(Any, _density_histogram(ca_events_phases, neurons, bins, hist_range))
            else:
                #plot the counts of each phase of all neurons
                hist_ret, bin_edges_ret = _counts_histogram(ca_events_phases, neurons, bins, hist_range)

        else: # neurons != 'all'
            if density:
                #plot probability density of phases of your selected neurons WARNING THIS FUNCTION MAY NOT WORK AS INTENDED
                hist_ret, bin_edges_ret = _neuron_subset_density_histogram(ca_events_phases, neurons_list_hist, bins, hist_range)
            else:
                #plot the counts of each phase of your selected neurons
                hist_ret, bin_edges_ret = _neuron_subset_counts_histogram(ca_events_phases, neurons_list_hist, bins, hist_range)

    else: # not combined
        # Plot each of the neurons as separate histograms either all together or a subset of the neurons
        if neurons == 'all':
            hist_ret, bin_edges_ret = _individual_neuron_histograms(ca_events_phases, bins, hist_range, density)
        else:
            hist_ret, bin_edges_ret = _neuron_subset_individual_neuron_histograms(ca_events_phases, neurons_list_hist, bins, hist_range, density)

    return cast(Any, (hist_ret, bin_edges_ret))


#The following helper methods are all intended to compute histograms using the parameters of the above function
#This method directly below, in addition to computing and plotting a histogram, also computes mean vectors
def _mean_density_histogram(
    ca_events_phases: dict[int, np.ndarray],
    neurons: str | list[int] | int,
    bins: int,
    hist_range: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Compute mean density histogram with mean phase vectors.
    
    Args:
        ca_events_phases: Dict of neuron_id -> phase array.
        neurons: Neuron selection ('all' or list).
        bins: Number of histogram bins.
        hist_range: (min, max) phase range.
        
    Returns:
        Tuple of (hist, bin_edges, mean_theta, mean_radius).
    """
    # Mean density histogram across neurons
    ca_events_phases_hist = np.empty((0, bins))
    mean_ca_events_vectors = np.empty((0, 2))
    mean_ca_events_vector_theta = []
    mean_ca_events_vector_radius = []
    for i, k in enumerate(list(ca_events_phases.keys())):
        hist, bin_edges = np.histogram(ca_events_phases[k], bins=bins, range=hist_range, density=True)
        ca_events_phases_hist = np.concatenate((ca_events_phases_hist, hist.reshape((1,-1))), axis=0)
        # Find the mean vector for each neuron's calcium events
        ca_events_vectors = np.concatenate((np.cos(ca_events_phases[k]).reshape((-1,1)), np.sin(ca_events_phases[k]).reshape((-1,1))), axis=1)
        mean_ca_events_vectors = np.concatenate((mean_ca_events_vectors, np.mean(ca_events_vectors ,axis=0).reshape((1,2))), axis=0)
        mean_ca_events_vector_theta.append(np.arctan2(mean_ca_events_vectors[i,1], mean_ca_events_vectors[i,0]))
        mean_ca_events_vector_radius.append(np.sqrt(mean_ca_events_vectors[i,0]**2 + mean_ca_events_vectors[i,1]**2))
    hist = np.mean(ca_events_phases_hist, axis=0) # Take the mean across the neurons at each bin.
    hist_error = np.std(ca_events_phases_hist, axis=0) / np.sqrt(np.shape(ca_events_phases_hist)[0]) # Take the standard error of the mean at each bin.
    h, ax = prep_axes(xLabel='Phase (rad)', yLabel='Mean Event Probability', title='Neuron(s): ' + str(neurons))
    if isinstance(ax, (list, np.ndarray)):
        ax_plot = ax[0]
    else:
        ax_plot = ax

    ax_plot.hist(cast(Any, bin_edges[:-1]), bins=cast(Any, bin_edges), weights=cast(Any, hist))
    ax_plot.set_xlabel('Phase (rad)')
    ax_plot.set_ylabel('Events')
    bin_midpoints = (bin_edges[1:] + bin_edges[:-1]) / 2
    ax_plot.errorbar(bin_midpoints, hist, yerr=hist_error, fmt='none', capsize=3)
    # Find the mean vector of all of the neurons
    mean_neuron_vector = np.mean(mean_ca_events_vectors, axis=0)
    mean_neuron_vector_theta = np.arctan2(mean_neuron_vector[1], mean_neuron_vector[0])
    mean_neuron_vector_radius = np.sqrt(mean_neuron_vector[0]**2 + mean_neuron_vector[1]**2)

    return hist, bin_edges, mean_neuron_vector_theta, mean_neuron_vector_radius


def _density_histogram(
    ca_events_phases: dict[int, np.ndarray],
    neurons: str | list[int] | int,
    bins: int,
    hist_range: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """Compute stacked density histogram across neurons."""
    # Barstacked density histogram across neurons
    ca_events_phases_hist_list = list(ca_events_phases.values())
    h, ax = prep_axes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): ' + str(neurons))
    if isinstance(ax, (list, np.ndarray)):
        ax_plot = ax[0]
    else:
        ax_plot = ax

    hist, bin_edges, _ = ax_plot.hist(ca_events_phases_hist_list, bins=bins, range=hist_range, density=True, histtype='barstacked')
    return cast(Any, (hist, bin_edges))


def _counts_histogram(
    ca_events_phases: dict[int, np.ndarray],
    neurons: str | list[int] | int,
    bins: int,
    hist_range: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """Compute event counts histogram pooled across all neurons."""
    all_ca_events_phases = np.array([])
    for k in list(ca_events_phases.keys()):
        all_ca_events_phases = np.concatenate((all_ca_events_phases, ca_events_phases[k]))
    h, ax = prep_axes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): ' + str(neurons))
    if isinstance(ax, (list, np.ndarray)):
        ax_plot = ax[0]
    else:
        ax_plot = ax

    hist, bin_edges, _ = ax_plot.hist(all_ca_events_phases, bins=bins, range=hist_range)
    return cast(Any, (hist, bin_edges))


def _neuron_subset_density_histogram(
    ca_events_phases: dict[int, np.ndarray],
    neurons: list[int],
    bins: int,
    hist_range: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """Compute density histogram for a subset of neurons."""
    ca_events_phases_hist = {}
    for k in neurons:
        ca_events_phases_hist[k] = ca_events_phases[k]
    h, ax = prep_axes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): ' + str(neurons))
    if isinstance(ax, (list, np.ndarray)):
        ax_plot = ax[0]
    else:
        ax_plot = ax

    hist, bin_edges, _ = ax_plot.hist(list(ca_events_phases_hist.values()), bins=bins, range=hist_range, density=True, histtype='barstacked')
    return cast(Any, (hist, bin_edges))


def _neuron_subset_counts_histogram(
    ca_events_phases: dict[int, np.ndarray],
    neurons: list[int],
    bins: int,
    hist_range: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """Compute counts histogram for a subset of neurons."""
    all_ca_events_phases = np.array([])
    for k in neurons:
        all_ca_events_phases = np.concatenate((all_ca_events_phases, ca_events_phases[k]))
    h, ax = prep_axes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): ' + str(neurons))
    if isinstance(ax, (list, np.ndarray)):
        ax_plot = ax[0]
    else:
        ax_plot = ax

    hist, bin_edges, _ = ax_plot.hist(all_ca_events_phases, bins=bins, range=hist_range)
    return cast(Any, (hist, bin_edges))


def _individual_neuron_histograms(
    ca_events_phases: dict[int, np.ndarray],
    bins: int,
    hist_range: tuple[float, float],
    density: bool
) -> tuple[dict[int, np.ndarray], dict[int, np.ndarray]]:
    """Create individual histograms for each neuron."""
    ax = []
    hist = {}
    bin_edges = {}
    for i, k in enumerate(list(ca_events_phases.keys())):
        if density:
            new_h, new_ax = prep_axes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): ' + str(k))
        else:
            new_h, new_ax = prep_axes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): ' + str(k))
        ax.append(new_ax)
        if hasattr(ax[i], '__getitem__'):
             cast(Any, ax[i])[0].hist(ca_events_phases[k], bins=bins, range=hist_range, density=density)
        else:
             hist[k], bin_edges[k], _ = cast(Any, ax[i]).hist(ca_events_phases[k], bins=bins, range=hist_range, density=density)
    return cast(Any, (hist, bin_edges))


def _neuron_subset_individual_neuron_histograms(
    ca_events_phases: dict[int, np.ndarray],
    neurons: list[int],
    bins: int,
    hist_range: tuple[float, float],
    density: bool
) -> tuple[dict[int, np.ndarray], dict[int, np.ndarray]]:
    """Create individual histograms for a subset of neurons."""
    ax = []
    hist = {}
    bin_edges = {}
    for i, k in enumerate(neurons):
        if density:
            new_h, new_ax = prep_axes(xLabel='Phase (rad)', yLabel='Event Probability', title='Neuron(s): ' + str(k))
        else:
            new_h, new_ax = prep_axes(xLabel='Phase (rad)', yLabel='Event Count', title='Neuron(s): ' + str(k))
        ax.append(new_ax)
        hist[k], bin_edges[k], _ = cast(Any, ax[i]).hist(ca_events_phases[k], bins=bins, range=hist_range, density=density)
    return hist, bin_edges


def _calculate_histograms_without_plotting(
    ca_events_phases: dict[int, np.ndarray],
    neurons: str | list[int] | int,
    bins: int,
    hist_range: tuple[float, float],
    density: bool,
    combined: bool
) -> tuple[np.ndarray | dict[int, np.ndarray], np.ndarray | dict[int, np.ndarray]]:
    """Compute phase histograms without generating plots.
    
    Args:
        ca_events_phases: Dict of neuron_id -> phase array.
        neurons: 'all' or list of neuron IDs.
        bins: Number of histogram bins.
        hist_range: (min, max) phase range.
        density: If True, normalize to probability density.
        combined: If True, pool events across neurons; else separate histograms.
        
    Returns:
        Tuple of (hist, bin_edges) - arrays if combined, dicts if not.
    """
    hist_dict: dict[int, np.ndarray] = {}
    bin_edges_dict: dict[int, np.ndarray] = {}

    if neurons == 'all':
        neurons_list = list(ca_events_phases.keys())
    elif not isinstance(neurons, list):
        neurons_list = [int(neurons)]
    else:
        neurons_list = [int(n) for n in neurons]

    if combined:
        all_ca_events_phases = np.array([])
        for k in neurons_list:
            all_ca_events_phases = np.concatenate((all_ca_events_phases, ca_events_phases[k]))
        hist_arr, bin_edges_arr = np.histogram(all_ca_events_phases, bins=bins, range=hist_range, density=density)
        return hist_arr, bin_edges_arr
    else:
        for k in neurons_list:
            h, b = np.histogram(ca_events_phases[k], bins=bins, range=hist_range, density=density)
            hist_dict[k] = h
            bin_edges_dict[k] = b
        return hist_dict, bin_edges_dict



