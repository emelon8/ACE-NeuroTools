"""Centralised matplotlib backend management for ACE-NeuroTools.

**Rule**: call :func:`set_backend` exactly once, at the top of each CLI entry
function (before any ``import matplotlib.pyplot`` occurs).  Do NOT call
``matplotlib.use(...)`` anywhere else in library code.

Rationale
---------
``matplotlib.use(...)`` raises a warning (or silently fails) if called after
pyplot has already been imported.  Because multiple pipeline modules used to
call ``matplotlib.use(...)`` independently, the "first caller wins" behaviour
was opaque and could conflict with a user's pre-configured backend.

Centralising the call here means:

* The rule is documented in one place.
* Library code (data managers, analysis engines) never touches the backend.
* CLI entry points call ``set_backend(headless=...)`` once and move on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import matplotlib.pyplot as plt


def set_backend(headless: bool) -> None:
    """Set the matplotlib backend.

    Must be called **before** any ``import matplotlib.pyplot`` statement
    or before any code that triggers pyplot's lazy initialisation.

    In headless mode (``headless=True``) the non-interactive ``'Agg'`` backend
    is selected so that figures can be saved to disk without a display.

    In interactive mode (``headless=False``) this function attempts to switch
    to ``'Qt5Agg'``.  If Qt5 is not available the call silently falls through,
    leaving whatever backend matplotlib selected by default (usually
    ``'TkAgg'`` or the OS platform default).

    Args:
        headless: When ``True``, force the ``'Agg'`` non-interactive backend.
            When ``False``, attempt ``'Qt5Agg'`` and fall through on failure.
    """
    import matplotlib

    if headless:
        matplotlib.use("Agg")
    else:
        try:
            matplotlib.use("Qt5Agg")
        except Exception:
            # Qt5 not installed or display unavailable — use platform default.
            pass

    # Embed text as text (not paths) in exported SVGs. Set here, at the plotting
    # entry point, rather than as an import-time side effect of a utility module.
    matplotlib.rcParams["svg.fonttype"] = "none"


def prep_axes(
    title: str | list[str] = "",
    xLabel: str | list[str] = "",
    yLabel: str | list[str] = "",
    subPlots: list[int] | None = None,
) -> tuple[plt.Figure, plt.Axes | list[plt.Axes]]:
    """
    Prepare figure and axis/axes for plotting. Returns the figure handle and either the axis handle or a list of axes handles.
    TITLE is the title of the axis or list of titles (in order) for the axes.
    XLABEL is the xlabel of the axis or list of xlabels (in order) for the axes.
    YLABEL is the ylabel of the axis or list of ylabels (in order) for the axes.
    SUBPLOTS is a list to prepare the subplot axes: [number of rows, number of columns].
    The elements in TITLE, XLABEL, and YLABEL label the plots first from left to right, then from top to bottom.
    """
    import matplotlib.pyplot as plt  # local import — see module docstring (backend rule)

    if isinstance(xLabel, list) and isinstance(yLabel, list):
        if len(xLabel) > len(yLabel):
            while len(xLabel) != len(yLabel):
                yLabel.append("")
        if len(yLabel) > len(xLabel):
            while len(xLabel) != len(yLabel):
                xLabel.append("")
    elif isinstance(xLabel, list) and isinstance(yLabel, str):
        yLabel_list: list[str] = [yLabel]
        while len(xLabel) != len(yLabel_list):
            yLabel_list.append("")
        yLabel = yLabel_list
    elif isinstance(xLabel, str) and isinstance(yLabel, list):
        xLabel_list: list[str] = [xLabel]
        while len(xLabel_list) != len(yLabel):
            xLabel_list.append("")
        xLabel = xLabel_list

    h: plt.Figure = plt.figure()
    # h.set_layout_engine('constrained')
    if subPlots is None:
        ax: plt.Axes = h.add_subplot()
        ax.set_title(str(title))
        ax.set_xlabel(str(xLabel))
        ax.set_ylabel(str(yLabel))
    else:
        axes_list: list[plt.Axes] = []
        num_subplots: int = subPlots[0] * subPlots[1]

        final_titles: list[str] = [title] * num_subplots if isinstance(title, str) else title
        final_xlabels: list[str] = [xLabel] * num_subplots if isinstance(xLabel, str) else xLabel
        final_ylabels: list[str] = [yLabel] * num_subplots if isinstance(yLabel, str) else yLabel

        for k in range(num_subplots):
            axes_list.append(h.add_subplot(subPlots[0], subPlots[1], k + 1))
            if k < len(final_titles):
                axes_list[k].set_title(final_titles[k])
            if k < len(final_xlabels):
                axes_list[k].set_xlabel(final_xlabels[k])
            if k < len(final_ylabels):
                axes_list[k].set_ylabel(final_ylabels[k])
        h.tight_layout()  # incompatible with the 'constrained' layout engine
        return h, axes_list
    h.tight_layout()
    return h, ax


def plot_spectrogram(
    tVec: np.ndarray,
    freqVec: np.ndarray,
    specData: np.ndarray,
    cBarPercentLims: list[float] = [5.0, 95.0],
    xLabel: str = "Time (s)",
    yLabel: str = "Frequency (Hz)",
    cLabel: str = "Power (dB)",
) -> tuple[plt.Figure, plt.Axes]:
    """
    Plots a spectrogram that has already been computed.
    TVEC is a vector of the x-axis time points or a time vector consisting of just [min, max].
    FREQVEC is a vector of the y-axis frequency points, or a frequency vector consisting of just [min, max].
    SPECDATA is the matrix of spectral power.
    CBARPERCENTLIMS sets the bounds on the color bar by finding the specified percentages of the power in specData.
    """
    h, ax = prep_axes(xLabel=xLabel, yLabel=yLabel)
    if isinstance(ax, list):
        ax = ax[0]

    cBarMin = np.percentile(specData, cBarPercentLims[0])
    cBarMax = np.percentile(specData, cBarPercentLims[1])
    spectrogramPlot = ax.imshow(
        specData,
        interpolation="none",
        extent=(tVec[0], tVec[-1], freqVec[0], freqVec[-1]),
        aspect="auto",
        vmin=cBarMin,
        vmax=cBarMax,
        origin="lower",
    )
    cbar = h.colorbar(spectrogramPlot, ax=ax)
    cbar.set_label(cLabel)
    return h, ax


def mark_events(axisHandle: plt.Axes, eventTimes: float | list[float] | np.ndarray) -> None:
    """Draw vertical event markers on a plot at specified times.

    Args:
        axisHandle: Matplotlib axis to draw on.
        eventTimes: Single time or list of times to mark.
    """
    # Mark Neuralynx events on a given plot
    yLimits = axisHandle.get_ylim()
    xLimits = axisHandle.get_xlim()
    lineLength = np.diff(yLimits)
    lineOffset = yLimits[0] + (lineLength / 2)
    if not isinstance(eventTimes, (list, np.ndarray)):
        eventPoints = [eventTimes]
    else:
        eventPoints = eventTimes

    axisHandle.eventplot(eventPoints, lineoffsets=float(lineOffset), linelengths=float(lineLength), colors="k")
    axisHandle.axis((xLimits[0], xLimits[1], yLimits[0], yLimits[1]))
