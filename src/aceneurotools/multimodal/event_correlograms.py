"""Event-train correlograms for calcium events and LFP-detected events.

Operates on plain numpy timestamp arrays (seconds) and per-neuron event dicts
(``dict[int, np.ndarray]``) so it slots into the existing data model
(``ca_events_idx`` / TTL event lists).
"""

from __future__ import annotations

from itertools import combinations, product

import numpy as np
import pandas as pd


def _cross_correlogram(
    t1: np.ndarray,
    t2: np.ndarray,
    binsize: float,
    windowsize: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Discrete cross-correlogram of two timestamp arrays (seconds).

    Returns the rate of ``t2`` (in Hz) relative to each timestamp in ``t1``,
    averaged across ``t1`` references. Pure-numpy implementation.

    Parameters
    ----------
    t1, t2 : np.ndarray
        Reference and target timestamps, sorted, in seconds.
    binsize, windowsize : float
        Histogram bin size and half-window (seconds). The full window is
        symmetric: ``[-windowsize, +windowsize]``.

    Returns
    -------
    C : np.ndarray, shape (nbins,)
        Rate per bin (Hz). ``nbins`` is always odd so a bin is centred on 0.
    B : np.ndarray, shape (nbins,)
        Bin centres (seconds).
    """
    t1 = np.ascontiguousarray(t1, dtype=np.float64)
    t2 = np.ascontiguousarray(t2, dtype=np.float64)

    nbins = int((windowsize * 2) // binsize)
    if nbins % 2 == 0:
        nbins += 1

    w = (nbins / 2) * binsize
    C = np.zeros(nbins, dtype=np.float64)

    nt1 = t1.size
    nt2 = t2.size
    i2 = 0

    for i1 in range(nt1):
        lbound = t1[i1] - w
        while i2 < nt2 and t2[i2] < lbound:
            i2 += 1
        while i2 > 0 and t2[i2 - 1] > lbound:
            i2 -= 1

        rbound = lbound
        leftb = i2
        for j in range(nbins):
            k = 0
            rbound += binsize
            while leftb < nt2 and t2[leftb] < rbound:
                leftb += 1
                k += 1
            C[j] += k

    if nt1 > 0:
        C /= (nt1 * binsize)

    B = -w + binsize / 2 + np.arange(nbins) * binsize
    return C, B


def _restrict_to_window(times: np.ndarray, t_start: float | None, t_end: float | None) -> np.ndarray:
    if t_start is None and t_end is None:
        return np.ascontiguousarray(times, dtype=np.float64)
    lo = -np.inf if t_start is None else t_start
    hi = np.inf if t_end is None else t_end
    mask = (times >= lo) & (times <= hi)
    return np.ascontiguousarray(times[mask], dtype=np.float64)


def _rate(times: np.ndarray, t_start: float, t_end: float) -> float:
    duration = t_end - t_start
    if duration <= 0:
        return 0.0
    return float(times.size) / duration


def compute_autocorrelogram(
    group: dict[int, np.ndarray],
    binsize: float,
    windowsize: float,
    t_start: float | None = None,
    t_end: float | None = None,
    norm: bool = True,
) -> pd.DataFrame:
    """Pairwise autocorrelograms for each event train in ``group``.

    Parameters
    ----------
    group : dict[int, np.ndarray]
        Maps neuron/unit id → sorted event times (seconds). Matches ea's
        ``ca_events_idx`` after dividing by frame rate.
    binsize, windowsize : float
        Bin size and half-window (seconds).
    t_start, t_end : float, optional
        Restrict each train to the window ``[t_start, t_end]`` before
        computing. If both are None, no restriction is applied and ``norm``
        falls back to using the full span of each train.
    norm : bool, default True
        If True, divide by the mean rate (autocorrelogram is unitless,
        baseline = 1). If False, returns rate in Hz.

    Returns
    -------
    pd.DataFrame
        Rows are bin centres (s), columns are unit ids.
    """
    autocorrs: dict[int, pd.Series] = {}
    rates: dict[int, float] = {}
    bin_centres: np.ndarray | None = None
    for n, times in group.items():
        t = _restrict_to_window(np.asarray(times, dtype=np.float64), t_start, t_end)
        C, B = _cross_correlogram(t, t, binsize, windowsize)
        autocorrs[n] = pd.Series(index=np.round(B, 6), data=C, dtype="float")
        if t_start is not None and t_end is not None:
            rates[n] = _rate(t, t_start, t_end)
        elif t.size >= 2:
            rates[n] = _rate(t, float(t.min()), float(t.max()))
        else:
            rates[n] = 0.0
        bin_centres = B

    df = pd.DataFrame.from_dict(autocorrs)

    if norm:
        rate_series = pd.Series(rates)
        # Avoid divide-by-zero: leave zero-rate units as NaN
        rate_series = rate_series.replace(0.0, np.nan)
        df = df / rate_series

    if bin_centres is not None and 0.0 in df.index:
        df.loc[0.0] = 0.0

    return df.astype("float")


def compute_crosscorrelogram(
    group: dict[int, np.ndarray] | tuple[dict[int, np.ndarray], dict[int, np.ndarray]] | list[dict[int, np.ndarray]],
    binsize: float,
    windowsize: float,
    t_start: float | None = None,
    t_end: float | None = None,
    norm: bool = True,
    reverse: bool = False,
) -> pd.DataFrame:
    """Pairwise cross-correlograms.

    Two input modes:

    * Single ``dict`` — computes CCG for each ordered pair ``(i, j)`` from
      ``itertools.combinations`` (use ``reverse=True`` to flip pair order).
    * Tuple/list of two dicts ``(group1, group2)`` — computes CCG for every
      ``(i, j)`` with ``i`` from ``group1`` (reference) and ``j`` from
      ``group2`` (target).

    Parameters
    ----------
    group : dict or (dict, dict)
        Event trains keyed by unit id (seconds).
    binsize, windowsize, t_start, t_end : see :func:`compute_autocorrelogram`.
    norm : bool, default True
        Divide by the target unit's mean rate.
    reverse : bool, default False
        Only used in single-dict mode — reverses the (reference, target)
        order within each pair.

    Returns
    -------
    pd.DataFrame
        Rows are bin centres (s), columns are ``(i, j)`` pair tuples.
    """
    is_pair = isinstance(group, (tuple, list))
    if is_pair:
        if len(group) != 2:
            raise ValueError("`group` must be a single dict or exactly two dicts.")
        g1, g2 = group
    else:
        g1 = group
        g2 = group

    def _restrict_dict(g: dict[int, np.ndarray]) -> dict[int, np.ndarray]:
        return {k: _restrict_to_window(np.asarray(v, dtype=np.float64), t_start, t_end) for k, v in g.items()}

    g1r = _restrict_dict(g1)
    g2r = _restrict_dict(g2)

    if is_pair:
        pairs = list(product(g1r.keys(), g2r.keys()))
    else:
        pairs = list(combinations(g1r.keys(), 2))
        if reverse:
            pairs = [(j, i) for i, j in pairs]

    crosscorrs: dict[tuple[int, int], pd.Series] = {}
    for i, j in pairs:
        C, B = _cross_correlogram(g1r[i], g2r[j], binsize, windowsize)
        if norm:
            if t_start is not None and t_end is not None:
                r = _rate(g2r[j], t_start, t_end)
            elif g2r[j].size >= 2:
                r = _rate(g2r[j], float(g2r[j].min()), float(g2r[j].max()))
            else:
                r = 0.0
            if r > 0:
                C = C / r
            else:
                C = np.full_like(C, np.nan)
        crosscorrs[(i, j)] = pd.Series(index=np.round(B, 6), data=C, dtype="float")

    return pd.DataFrame.from_dict(crosscorrs).astype("float")


def compute_eventcorrelogram(
    group: dict[int, np.ndarray],
    event: np.ndarray,
    binsize: float,
    windowsize: float,
    t_start: float | None = None,
    t_end: float | None = None,
    norm: bool = True,
) -> pd.DataFrame:
    """Correlogram of each unit's events relative to a single event train.

    Typical use: align calcium events to LFP-detected events (slow waves,
    spindles, K-complexes) under anesthesia.

    Parameters
    ----------
    group : dict[int, np.ndarray]
        Per-unit event times (seconds).
    event : np.ndarray
        Reference event timestamps (seconds), e.g. detected slow-wave times.
    binsize, windowsize, t_start, t_end, norm : see other correlogram functions.

    Returns
    -------
    pd.DataFrame
        Rows are bin centres (s), columns are unit ids. Each column shows the
        rate of that unit's events relative to ``event`` times.
    """
    ref = _restrict_to_window(np.asarray(event, dtype=np.float64), t_start, t_end)
    crosscorrs: dict[int, pd.Series] = {}
    rates: dict[int, float] = {}
    for n, times in group.items():
        t = _restrict_to_window(np.asarray(times, dtype=np.float64), t_start, t_end)
        C, B = _cross_correlogram(ref, t, binsize, windowsize)
        crosscorrs[n] = pd.Series(index=np.round(B, 6), data=C, dtype="float")
        if t_start is not None and t_end is not None:
            rates[n] = _rate(t, t_start, t_end)
        elif t.size >= 2:
            rates[n] = _rate(t, float(t.min()), float(t.max()))
        else:
            rates[n] = 0.0

    df = pd.DataFrame.from_dict(crosscorrs)
    if norm:
        rate_series = pd.Series(rates).replace(0.0, np.nan)
        df = df / rate_series
    return df.astype("float")


def compute_isi_distribution(
    data: np.ndarray | dict[int, np.ndarray],
    bins: int | list[float] | np.ndarray = 10,
    log_scale: bool = False,
    t_start: float | None = None,
    t_end: float | None = None,
) -> pd.DataFrame:
    """Inter-spike-interval distribution.

    Useful for characterising burstiness of calcium event trains under
    different drug states.

    Parameters
    ----------
    data : np.ndarray or dict[int, np.ndarray]
        Single event train or a dict of per-unit trains (seconds).
    bins : int or 1D array, default 10
        If int, number of equal-width bins spanning the global ISI range.
        If a 1D array, treated as monotonically increasing bin edges.
    log_scale : bool, default False
        If True, ISIs are log-transformed before binning.
    t_start, t_end : float, optional
        Restrict event trains before computing ISIs.

    Returns
    -------
    pd.DataFrame
        Rows are bin centres (in same units as ISIs, or log-ISIs).
        Columns are unit ids (single column ``0`` for ndarray input).
    """
    if isinstance(data, np.ndarray):
        trains = {0: data}
    elif isinstance(data, dict):
        trains = data
    else:
        raise TypeError("data must be np.ndarray or dict[int, np.ndarray].")

    if not isinstance(log_scale, bool):
        raise TypeError("log_scale must be bool.")

    isis: dict[int, np.ndarray] = {}
    for k, times in trains.items():
        t = _restrict_to_window(np.asarray(times, dtype=np.float64), t_start, t_end)
        if t.size < 2:
            isis[k] = np.array([], dtype=np.float64)
            continue
        d = np.diff(np.sort(t))
        if log_scale:
            d = np.log(d[d > 0])
        isis[k] = d

    if np.ndim(bins) == 0:
        if int(bins) < 1:
            raise ValueError("bins must be positive when an integer.")
        all_isis = np.concatenate([v for v in isis.values() if v.size > 0]) if any(v.size for v in isis.values()) else np.array([0.0, 1.0])
        bin_edges = np.linspace(all_isis.min(), all_isis.max(), int(bins) + 1)
    else:
        bin_edges = np.asarray(bins, dtype=np.float64)
        if bin_edges.ndim != 1:
            raise ValueError("bins array must be 1D.")
        if np.any(bin_edges[:-1] > bin_edges[1:]):
            raise ValueError("bins must increase monotonically.")

    centres = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    counts = {k: np.histogram(v, bin_edges)[0] for k, v in isis.items()}
    return pd.DataFrame(index=centres, data=counts)
