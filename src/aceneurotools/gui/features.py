"""GUI features served by ``ace-gui``.

Each entry is a module that defines ``FEATURE`` (see :mod:`aceneurotools.gui.routes`).
Add one line per feature; keep one feature per line so parallel branches merge cleanly.
Order matters only for browser scripts, which load in this order after the core scripts.
"""

ENABLED = (
    "aceneurotools.gui.run_plan_routes",
)
