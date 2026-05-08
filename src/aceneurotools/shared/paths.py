"""Path configuration for the ``aceneurotools`` package.

Path resolution policy
----------------------
``project_path`` and ``data_path`` should be provided explicitly by the
caller — either as arguments to :class:`~aceneurotools.shared.experiment_data_manager.ExperimentDataManager`
and pipeline constructors, or as CLI flags (``--project-path``, ``--data-path``).

The ``ACE_NEUROTOOLS_DATA`` environment variable is honored as a last-resort
default for HPC submit scripts and other contexts where threading paths
through a shell command line is awkward. When it is unset, :data:`PROJECT_ROOT`
falls back to the current working directory.

Note:
    The legacy ``ACE_NEURO_DATA`` environment variable is no longer read.
    Update any shell profiles, Slurm submit scripts, or CI configuration
    that previously exported ``ACE_NEURO_DATA`` to set ``ACE_NEUROTOOLS_DATA``
    instead.
"""

import os
from pathlib import Path

if "ACE_NEUROTOOLS_DATA" in os.environ:
    PROJECT_ROOT: Path = Path(os.environ["ACE_NEUROTOOLS_DATA"]).resolve()
else:
    PROJECT_ROOT: Path = Path.cwd()

DATA_DIR: Path = PROJECT_ROOT / "data"
