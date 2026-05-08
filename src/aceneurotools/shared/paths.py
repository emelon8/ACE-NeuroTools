"""
Path configuration for the experiment_analysis package.

All data paths (project_path, data_path) must be provided explicitly by the
user — either as arguments to Pipeline/DataManager constructors, or as CLI
flags (--project-path, --data-path).

There is no hidden state: no .env files, no environment variable lookups.
"""

import os
from pathlib import Path

# When installed via pip, we don't want to look relative to the source code file.
# Instead, we look at where the user is currently running the script from,
# or we let them define an environment variable.
if "ACE_NEURO_DATA" in os.environ:
    PROJECT_ROOT: Path = Path(os.environ["ACE_NEURO_DATA"]).resolve()
else:
    PROJECT_ROOT: Path = Path.cwd()

# Legacy alias kept for Box credentials and internal data directory
DATA_DIR: Path = PROJECT_ROOT / "data"