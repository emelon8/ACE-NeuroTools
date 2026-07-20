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
