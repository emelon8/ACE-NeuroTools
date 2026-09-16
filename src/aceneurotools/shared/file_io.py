"""Safe loading of scientific data files (.npz / .hdf5)."""

from pathlib import Path
from typing import Any

import numpy as np


def load_obj(filename: str | Path) -> Any:
    """Load a scientific data object from a ``.npz`` or ``.hdf5`` / ``.h5`` file.

    .. warning::
        **Pickle files are not accepted.**  ``pickle.load`` on untrusted files is
        a remote code execution vector.  This function only accepts NumPy archive
        (``.npz``) and HDF5 (``.hdf5`` / ``.h5``) formats, which do not execute
        arbitrary code during loading.

    Args:
        filename: Path to a ``.npz``, ``.hdf5``, or ``.h5`` file.

    Returns:
        * For ``.npz``: a :class:`numpy.lib.npyio.NpzFile` mapping of array names
          to :class:`numpy.ndarray` objects.  Access individual arrays with
          ``result['key']``.
        * For ``.hdf5`` / ``.h5``: an open read-only :class:`h5py.File` handle.
          The caller is responsible for closing it (use as a context manager).

    Raises:
        ValueError: If *filename* has an unsupported extension.
        FileNotFoundError: If *filename* does not exist.

    Examples::

        # NumPy archive
        data = load_obj("signal.npz")
        arr = data["meanFluorescence"]

        # HDF5 — use as context manager to ensure the file is closed
        with load_obj("estimates.hdf5") as f:
            arr = f["estimates/C"][:]
    """
    path = Path(filename)
    suffix = path.suffix.lower()

    if suffix == ".npz":
        return np.load(path, allow_pickle=False)

    if suffix in (".hdf5", ".h5"):
        import h5py  # optional dependency — only imported when needed

        return h5py.File(path, "r")

    raise ValueError(
        f"load_obj: unsupported file extension {suffix!r} for {filename!r}.\n"
        "Supported extensions: '.npz' (NumPy archive), '.hdf5' / '.h5' (HDF5).\n"
        "Pickle files (.pkl, .pickle) are not accepted for security reasons."
    )
