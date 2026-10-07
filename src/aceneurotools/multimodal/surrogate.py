"""Surrogate event-train generators for null-distribution testing.

All functions operate on sorted event-time arrays (seconds) with an explicit
``(t_start, t_end)`` time support. Pass a :class:`numpy.random.Generator` for
reproducible runs.

Typical use:

    >>> rng = np.random.default_rng(0)
    >>> null = jitter_event_times(event_times, max_jitter=0.1, rng=rng)

Combine with :func:`apply_to_group` to operate on per-unit event dicts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np


def _rng(rng: np.random.Generator | None) -> np.random.Generator:
    return rng if rng is not None else np.random.default_rng()


@dataclass
class PermutationTestResult:
    """Result of a Monte-Carlo permutation test.

    Attributes
    ----------
    observed : float
        The statistic computed on the real data.
    null_distribution : np.ndarray
        The ``n_surrogates`` statistics computed on surrogate data.
    p_value : float
        Monte-Carlo p-value with the standard ``(1 + count) / (1 + n)``
        correction (never exactly zero).
    n_surrogates : int
        Number of surrogate draws.
    alternative : str
        ``'two-sided'``, ``'greater'``, or ``'less'``.
    """

    observed: float
    null_distribution: np.ndarray
    p_value: float
    n_surrogates: int
    alternative: str


def permutation_test(
    observed_statistic: float,
    surrogate_statistic_fn: Callable[[np.random.Generator], float],
    n_surrogates: int = 1000,
    alternative: str = "two-sided",
    rng: np.random.Generator | None = None,
    n_jobs: int = 1,
) -> PermutationTestResult:
    """Monte-Carlo permutation test against a surrogate null distribution.

    This is the missing driver that ties the surrogate generators above to a
    p-value. It is deliberately statistic-agnostic: the caller supplies a
    closure that, given a random generator, produces **one** surrogate
    statistic (e.g. shuffle the events with :func:`shuffle_event_intervals`,
    recompute coherence/correlation, return the scalar). The expensive base
    transform of any fixed signal can therefore be precomputed once inside the
    closure rather than per draw.

    Parameters
    ----------
    observed_statistic : float
        Statistic computed on the real data.
    surrogate_statistic_fn : callable
        ``fn(child_rng) -> float``; computes one surrogate statistic using the
        supplied :class:`numpy.random.Generator` (guarantees reproducibility
        even under parallelism).
    n_surrogates : int, default 1000
        Number of surrogate draws.
    alternative : ``'two-sided'``, ``'greater'``, or ``'less'``
        Tail(s) for the p-value.
    rng : np.random.Generator, optional
        Seeds the independent per-surrogate child generators.
    n_jobs : int, default 1
        Parallel workers (joblib). Draws are independent, so this scales
        linearly. Results are identical to ``n_jobs=1`` because each draw uses a
        deterministically-spawned child generator.

    Returns
    -------
    PermutationTestResult
    """
    if alternative not in ("two-sided", "greater", "less"):
        raise ValueError("alternative must be 'two-sided', 'greater', or 'less'.")
    if n_surrogates < 1:
        raise ValueError("n_surrogates must be >= 1.")

    child_rngs = _rng(rng).spawn(n_surrogates)

    if n_jobs == 1:
        null = np.array([float(surrogate_statistic_fn(cr)) for cr in child_rngs], dtype=np.float64)
    else:
        from joblib import Parallel, delayed

        null = np.asarray(
            Parallel(n_jobs=n_jobs)(delayed(surrogate_statistic_fn)(cr) for cr in child_rngs),
            dtype=np.float64,
        )

    obs = float(observed_statistic)
    if alternative == "two-sided":
        count = int(np.sum(np.abs(null) >= abs(obs)))
    elif alternative == "greater":
        count = int(np.sum(null >= obs))
    else:  # less
        count = int(np.sum(null <= obs))

    p_value = (1.0 + count) / (1.0 + n_surrogates)
    return PermutationTestResult(obs, null, p_value, n_surrogates, alternative)


def _validate_support(t_start: float, t_end: float) -> None:
    if t_end <= t_start:
        raise ValueError(f"t_end ({t_end}) must be > t_start ({t_start}).")


def jitter_event_times(
    event_times: np.ndarray,
    max_jitter: float,
    t_start: float | None = None,
    t_end: float | None = None,
    clip_to_support: bool = False,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Independently jitter each event time by U(-max_jitter, +max_jitter).

    Parameters
    ----------
    event_times : np.ndarray
        Sorted event times (seconds).
    max_jitter : float
        Maximum absolute jitter (seconds).
    t_start, t_end : float, optional
        Time support. Only consulted when ``clip_to_support=True``.
    clip_to_support : bool, default False
        If True, drop jittered events that fall outside ``[t_start, t_end]``.
        If False, all events are retained (count preserved).
    rng : np.random.Generator, optional
        Reproducible random source.

    Returns
    -------
    np.ndarray
        Sorted jittered event times.
    """
    if max_jitter <= 0:
        raise ValueError("max_jitter must be > 0.")
    g = _rng(rng)
    e = np.asarray(event_times, dtype=np.float64)
    out = e + g.uniform(-max_jitter, max_jitter, size=e.size)
    out = np.sort(out)
    if clip_to_support:
        if t_start is None or t_end is None:
            raise ValueError("clip_to_support=True requires t_start and t_end.")
        _validate_support(t_start, t_end)
        out = out[(out >= t_start) & (out <= t_end)]
    return out


def shift_event_times(
    event_times: np.ndarray,
    t_start: float,
    t_end: float,
    min_shift: float = 0.0,
    max_shift: float | None = None,
    mode: str = "drop",
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Apply a single random shift to every event time.

    Parameters
    ----------
    event_times : np.ndarray
        Sorted event times (seconds).
    t_start, t_end : float
        Time support bounds (seconds).
    min_shift, max_shift : float, optional
        Bounds on the random shift. If ``max_shift`` is None, it defaults to
        the duration ``t_end - t_start``.
    mode : ``'drop'`` or ``'wrap'``, default ``'drop'``
        How to handle events that fall outside the support after shifting:

        * ``'drop'`` — discard out-of-support events
        * ``'wrap'`` — wrap circularly within ``[t_start, t_end]``
    rng : np.random.Generator, optional
        Reproducible random source.

    Returns
    -------
    np.ndarray
        Sorted shifted event times.
    """
    _validate_support(t_start, t_end)
    if mode not in ("drop", "wrap"):
        raise ValueError("mode must be 'drop' or 'wrap'.")
    g = _rng(rng)
    if max_shift is None:
        max_shift = t_end - t_start
    if max_shift < min_shift:
        raise ValueError("max_shift must be >= min_shift.")

    shift = g.uniform(min_shift, max_shift)
    e = np.asarray(event_times, dtype=np.float64)
    shifted = e + shift

    if mode == "wrap":
        period = t_end - t_start
        shifted = t_start + ((shifted - t_start) % period)
    else:
        shifted = shifted[(shifted >= t_start) & (shifted <= t_end)]

    return np.sort(shifted)


def shuffle_event_intervals(
    event_times: np.ndarray,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Randomise event times by shuffling the inter-event intervals.

    Preserves the marginal ISI distribution while destroying temporal order.
    Useful as a tight null for correlation/coherence tests.

    Parameters
    ----------
    event_times : np.ndarray
        Sorted event times (seconds). Length must be >= 2.
    rng : np.random.Generator, optional
        Reproducible random source.

    Returns
    -------
    np.ndarray
        Sorted shuffled event times, starting at ``event_times[0]``.
    """
    g = _rng(rng)
    e = np.asarray(event_times, dtype=np.float64)
    if e.size < 2:
        return np.sort(e.copy())
    intervals = np.diff(np.sort(e))
    g.shuffle(intervals)
    return np.concatenate(([e.min()], e.min() + np.cumsum(intervals)))


def resample_event_times(
    event_times: np.ndarray,
    t_start: float,
    t_end: float,
    n: int | None = None,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Resample event times uniformly on ``[t_start, t_end]``.

    Equivalent to drawing from a homogeneous Poisson process of matched count.

    Parameters
    ----------
    event_times : np.ndarray
        Used only to infer the number of events when ``n`` is None.
    t_start, t_end : float
        Support bounds (seconds).
    n : int, optional
        Number of events to draw. Defaults to ``len(event_times)``.
    rng : np.random.Generator, optional
        Reproducible random source.

    Returns
    -------
    np.ndarray
        Sorted resampled event times.
    """
    _validate_support(t_start, t_end)
    g = _rng(rng)
    e = np.asarray(event_times, dtype=np.float64)
    count = int(e.size) if n is None else int(n)
    if count == 0:
        return np.array([], dtype=np.float64)
    return np.sort(g.uniform(t_start, t_end, size=count))


def apply_to_group(
    fn: Callable[..., np.ndarray],
    group: dict[int, np.ndarray],
    **kwargs,
) -> dict[int, np.ndarray]:
    """Apply a surrogate function to every train in a per-unit dict.

    Parameters
    ----------
    fn : callable
        One of :func:`jitter_event_times`, :func:`shift_event_times`,
        :func:`shuffle_event_intervals`, :func:`resample_event_times`.
    group : dict[int, np.ndarray]
        Per-unit event trains (seconds).
    **kwargs
        Forwarded to ``fn``. Pass a shared ``rng`` to keep draws
        reproducible across units.

    Returns
    -------
    dict[int, np.ndarray]
        Surrogate per-unit event trains.
    """
    return {k: fn(v, **kwargs) for k, v in group.items()}
