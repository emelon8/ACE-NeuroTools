import os
import tempfile
from os import makedirs
from os import path as os_path
from pathlib import Path
from typing import Any

import pandas as pd


def is_box_installed() -> bool:
    """Check if the Box SDK is installed."""
    try:
        from box_sdk_gen import BoxClient, BoxDeveloperTokenAuth  # noqa: F401

        return True
    except ImportError:
        return False


def is_box_configured() -> bool:
    """Check if box_credentials.py exists and is not the blank template."""
    try:
        from aceneurotools.shared.box_credentials import auth  # noqa: F401

        return True
    except ImportError:
        return False


# A pending marker survives interrupted transfers so a partly populated folder
# cannot silently satisfy a later local-only availability check.
_INCOMPLETE_DOWNLOAD = ".ace-box-incomplete"
_RECORDING_SUFFIXES = {".avi", ".tif", ".tiff", ".ncs", ".nev", ".nse", ".ntt", ".dat", ".rhs", ".rhd"}


def _nonempty_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def verify_avi(miniscope_path: str, avi: str, base_file_path: str | Path | None = None) -> bool:
    """Check a nonempty movie in either a flat or nested Miniscope recording."""
    if base_file_path is None:
        raise ValueError("base_file_path is required.")
    directory = Path(base_file_path) / miniscope_path
    return any(_nonempty_file(path) for path in (directory / "Miniscope" / avi, directory / avi))


def verify_path(path: str, base_file_path: str | Path | None = None) -> bool:
    """Check for nonempty recording data and no unfinished Box transfer.

    This is a local availability check, not validation of a complete acquisition
    or its binary format. Metadata, temporary downloads and empty files do not
    establish recording availability.
    """
    if base_file_path is None:
        raise ValueError("base_file_path is required.")
    directory = Path(base_file_path) / path
    candidates = directory.rglob("*") if directory.is_dir() else [directory]
    found_recording = False
    for candidate in candidates:
        if candidate.name == _INCOMPLETE_DOWNLOAD:
            return False
        is_rhs_signal = candidate.suffix.lower() == ".raw" and candidate.name.startswith(
            ("rhs2116pair-ac_", "rhs2116pair-dc_")
        )
        if (candidate.suffix.lower() in _RECORDING_SUFFIXES or is_rhs_signal) and _nonempty_file(candidate):
            found_recording = True
    return found_recording


def verify_file_by_line(
    line_num: int | str,
    csv_path: str | Path,
    do_type: str = "both",
    avi_list: list[str] = [],
    base_file_path: str | Path | None = None,
) -> bool:
    """Checks if experimental data exists locally. If files are missing and Box IDs
    are provided in the CSV, attempts to download them from Box.

    This function implements an 'optional' Box integration:
    1. If local files are present, it returns True (no Box needed).
    2. If files are missing and Box IDs are in the CSV:
       - If Box is configured, it syncs/downloads missing files.
       - If Box is NOT configured, it prompts the user for setup.
    3. If Box IDs are missing, it simply returns whether local files exist.

    Args:
        line_num: The experiment line number.
        csv_path: Path to experiments.csv.
        do_type: 'both', 'miniscope', or 'ephys'.
        avi_list: Specific filenames to check/download.
        base_file_path: Base path for data storage. Required.

    Returns:
        True if all requested data is available locally (or was successfully downloaded).
        False if data is missing and cannot be retrieved.
    """
    if base_file_path is None:
        raise ValueError("base_file_path is required.")

    line_num_str = str(line_num)
    if do_type not in ["both", "miniscope", "ephys"]:
        raise ValueError("variable 'do_type' must be 'both', 'miniscope', or 'ephys'")

    try:
        df = pd.read_csv(csv_path, index_col="line number")
        df.index = df.index.astype(str)
    except (pd.errors.EmptyDataError, FileNotFoundError, pd.errors.ParserError):
        print(f"Error: Could not read CSV at {csv_path}")
        return False

    if line_num_str not in df.index:
        print(f"Error: Line {line_num_str} not found in {csv_path}")
        return False

    def _optional_cell(column: str) -> Any:
        if column not in df.columns:
            return None
        return df.at[line_num_str, column]

    miniscope_id = _optional_cell("Box Calcium Folder ID")
    miniscope_path = df.at[line_num_str, "calcium imaging directory"]
    ephys_id = _optional_cell("Box ephys folder ID")
    ephys_path = df.at[line_num_str, "ephys directory"]

    def local_status() -> tuple[bool, bool]:
        missing_avis = []
        has_miniscope = False
        if not pd.isnull(miniscope_path):
            missing_avis = [avi for avi in avi_list if not verify_avi(miniscope_path, avi, base_file_path)]
            has_miniscope = verify_path(miniscope_path, base_file_path) and not missing_avis
        has_ephys = not pd.isnull(ephys_path) and verify_path(ephys_path, base_file_path)
        return has_miniscope, has_ephys

    def satisfied(has_miniscope: bool, has_ephys: bool) -> bool:
        return (do_type == "ephys" or has_miniscope) and (do_type == "miniscope" or has_ephys)

    has_miniscope, has_ephys = local_status()
    if satisfied(has_miniscope, has_ephys):
        return True

    # --- 2. Box Sync (If needed and IDs are present) ---
    box_miniscope_needed = (do_type in ["both", "miniscope"]) and not has_miniscope and not pd.isnull(miniscope_id)
    box_ephys_needed = (do_type in ["both", "ephys"]) and not has_ephys and not pd.isnull(ephys_id)

    if box_miniscope_needed or box_ephys_needed:
        if not is_box_installed():
            print("\n[Box Integration] Box IDs found in metadata, but the Box SDK is not installed.")
            print("To enable automatic downloads, run: pip install aceneurotools[box]\n")
            return False

        if not is_box_configured():
            print("\n[Box Integration] Box IDs found in metadata, but authentication is not configured.")
            print("Please follow these steps to enable automatic downloads:")
            print("1. Locate 'src/aceneurotools/shared/BLANK_box_credentials.py'")
            print("2. Copy it to 'src/aceneurotools/shared/box_credentials.py'")
            print("3. Enter your Box API credentials in the new file.\n")
            return False

        # If we get here, we have IDs and Auth
        client = make_auth()
        if not client:
            return False

        downloaded_miniscope = True
        if box_miniscope_needed:
            print(f"Syncing Miniscope data from Box (ID: {miniscope_id})...")
            if not os_path.exists(f"{base_file_path}/{miniscope_path}"):
                makedirs(f"{base_file_path}/{miniscope_path}")
            downloaded_miniscope = download_file(
                client, miniscope_path, int(miniscope_id), avi_list, base_file_path=base_file_path
            )

        downloaded_ephys = True
        if box_ephys_needed:
            print(f"Syncing Ephys data from Box (ID: {ephys_id})...")
            if not os_path.exists(f"{base_file_path}/{ephys_path}"):
                makedirs(f"{base_file_path}/{ephys_path}")
            downloaded_ephys = download_file(client, ephys_path, int(ephys_id), base_file_path=base_file_path)

        if not (downloaded_miniscope and downloaded_ephys):
            return False
        has_miniscope, has_ephys = local_status()
        return satisfied(has_miniscope, has_ephys)

    # If we get here, either IDs were missing or we didn't need to download anything but were still unsatisfied
    # This usually means local files are missing and no Box ID was provided to fetch them.
    return False


def make_auth() -> Any | None:
    """Creates the box client object to connect to the box servers."""
    if not is_box_configured():
        return None

    try:
        from box_sdk_gen import BoxClient

        from aceneurotools.shared.box_credentials import auth, dev_token  # noqa: F401

        # Use developer token if uncommented in the credentials file (legacy support)
        # client = BoxClient(auth=BoxDeveloperTokenAuth(token=dev_token))

        client = BoxClient(auth=auth)
        print("Successfully connected to Box client")
        return client
    except Exception as e:
        print(f"Failed to connect to Box: {e}")
        return None


def _folder_items(client: Any, folder_id: str):
    """Consume Box's marker-based pages, including pages inside child folders."""
    marker = None
    seen_markers = set()
    while True:
        page = client.folders.get_folder_items(
            folder_id,
            usemarker=True,
            marker=marker,
            fields=["id", "type", "name", "size"],
        )
        yield from page.entries or []
        marker = getattr(page, "next_marker", None)
        if not marker:
            return
        if marker in seen_markers:
            raise ValueError("Box folder listing repeated its pagination marker")
        seen_markers.add(marker)


def _download_item(client: Any, item: Any, destination: Path) -> None:
    """Publish a file only after the complete response has been written."""
    expected_size = getattr(item, "size", None)
    if destination.is_file():
        size = destination.stat().st_size
        if (expected_size is None and size > 0) or size == expected_size:
            return
    staged = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".part",
            delete=False,
        ) as output:
            staged = Path(output.name)
            client.downloads.download_file_to_output_stream(item.id, output_stream=output)
            output.flush()
            os.fsync(output.fileno())
        if expected_size is not None and staged.stat().st_size != expected_size:
            raise OSError(f"Incomplete Box response for {destination.name}")
        os.replace(staged, destination)
        print(f"File '{item.name}' downloaded successfully to '{destination}'")
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


def download_file(
    client: Any,
    path: str,
    ID: int,
    need_to_download: list[str] = [],
    base_file_path: str | Path | None = None,
) -> bool:
    """Download all pages of a Box folder, propagating child-folder failures.

    Requested filenames limit AVI downloads; ancillary metadata and other file
    types remain included. Existing files are reused when their size agrees with
    Box (or no size was supplied). New files are installed atomically, and known
    size mismatches are retried. An interrupted folder keeps its pending marker
    until a successful retry, so partial data is not mistaken for a completed sync.
    """
    if base_file_path is None:
        raise ValueError("base_file_path is required for downloading files.")
    destination = Path(base_file_path) / path
    try:
        destination.mkdir(parents=True, exist_ok=True)
        pending = destination / _INCOMPLETE_DOWNLOAD
        pending.write_text(str(ID))
        for item in _folder_items(client, str(ID)):
            if item.type not in {"file", "folder"}:
                continue
            name = item.name
            if not name or name in {".", "..", _INCOMPLETE_DOWNLOAD} or "/" in name or "\\" in name:
                raise ValueError("Box returned an invalid file or folder name")
            if item.type == "folder":
                if not download_file(client, str(Path(path) / name), item.id, need_to_download, base_file_path):
                    return False
            elif need_to_download and name.lower().endswith(".avi") and name not in need_to_download:
                continue
            else:
                _download_item(client, item, destination / name)
        pending.unlink(missing_ok=True)
        return True
    except Exception as error:
        print(f"Download failed: {error}")
        return False


if __name__ == "__main__":  # Runs when we run the file.
    import argparse

    parser = argparse.ArgumentParser(description="Download experiment data from Box")
    parser.add_argument(
        "--project-path", type=str, required=True, help="Path to project directory (containing experiments.csv)"
    )
    parser.add_argument("--data-path", type=str, required=True, help="Base path for raw experimental data storage")
    parser.add_argument("--line-num", type=int, default=96, help="Experiment line number")
    parser.add_argument("--do-type", type=str, default="miniscope", choices=["both", "miniscope", "ephys"])
    args = parser.parse_args()

    experiments_csv = Path(args.project_path) / "experiments.csv"
    verify_file_by_line(
        line_num=args.line_num,
        csv_path=experiments_csv,
        do_type=args.do_type,
        avi_list=["0.avi"],
        base_file_path=args.data_path,
    )
