from os import listdir, makedirs
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


def verify_avi(miniscope_path: str, avi: str, base_file_path: str | Path | None = None) -> bool:
    """Check if a specific AVI file exists in the Miniscope directory."""
    if base_file_path is None:
        raise ValueError("base_file_path is required.")
    return os_path.exists(f"{base_file_path}/{miniscope_path}/Miniscope/{avi}")


def verify_path(path: str, base_file_path: str | Path | None = None) -> bool:
    """Checks the path where the file should be.
    If a folder doesn't exist, returns False.
    """
    if base_file_path is None:
        raise ValueError("base_file_path is required.")
    base = base_file_path
    full_path = f"{base}/{path}"
    if os_path.exists(full_path):  # If we already have the folder, then we don't need to download anything
        if not listdir(full_path):
            return False  # If the folder is empty (i.e., the download connection failed), it will still return false so verify_file will download it.
        return True  # This will  return True even if the downloads are incomplete
    else:
        # Note: We don't makedirs here anymore; we let the download process or the user handle it.
        return False


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

    miniscope_id = df.at[line_num_str, "Box Calcium Folder ID"]
    miniscope_path = df.at[line_num_str, "calcium imaging directory"]
    ephys_id = df.at[line_num_str, "Box ephys folder ID"]
    ephys_path = df.at[line_num_str, "ephys directory"]

    # --- 1. Check Local Status ---
    has_miniscope = False
    if not pd.isnull(miniscope_path):
        folder_exists = verify_path(miniscope_path, base_file_path=base_file_path)
        missing_avis = [avi for avi in avi_list if not verify_avi(miniscope_path, avi, base_file_path=base_file_path)]
        has_miniscope = folder_exists and not missing_avis
    else:
        missing_avis = []  # No path, so we can't have missing avis

    has_ephys = False
    if not pd.isnull(ephys_path):
        has_ephys = verify_path(ephys_path, base_file_path=base_file_path)

    # Determine if we are already satisfied locally
    if do_type == "miniscope":
        if has_miniscope:
            return True
    elif do_type == "ephys":
        if has_ephys:
            return True
    elif do_type == "both":
        if has_miniscope and has_ephys:
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
                client, miniscope_path, int(miniscope_id), missing_avis, base_file_path=base_file_path
            )

        downloaded_ephys = True
        if box_ephys_needed:
            print(f"Syncing Ephys data from Box (ID: {ephys_id})...")
            if not os_path.exists(f"{base_file_path}/{ephys_path}"):
                makedirs(f"{base_file_path}/{ephys_path}")
            downloaded_ephys = download_file(client, ephys_path, int(ephys_id), base_file_path=base_file_path)

        return downloaded_miniscope and downloaded_ephys

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


def download_file(
    client: Any, path: str, ID: int, need_to_download: list[str] = [], base_file_path: str | Path | None = None
) -> bool:
    """Connects to the client and tries to download everything in the folder and
    child folders if they haven't already been downloaded.

    Args:
        client: BoxClient instance.
        path: Relative path within the data directory.
        ID: Box folder ID.
        need_to_download: Optional list of specific filenames to retrieve.
        base_file_path: Base path for data storage. Required.
    """
    if base_file_path is None:
        raise ValueError("base_file_path is required for downloading files.")
    try:
        for item in client.folders.get_folder_items(str(ID)).entries:  # Goes to the folder we want to download
            if item.type == "folder":  # Additional code to download any subfolders
                if not os_path.exists(f"{base_file_path}/{path}/{item.name}"):  # Checks if the subfolder already exists
                    makedirs(f"{base_file_path}/{path}/{item.name}")  # Makes new directory for sub folder
                if item.name == "Miniscope":  # Checks if the subfolder is miniscope
                    for sub_item in client.folders.get_folder_items(
                        item.id
                    ).entries:  # Look at each item in the miniscope folder
                        if (
                            sub_item.name in need_to_download or need_to_download == []
                        ) or "avi" not in sub_item.name:  # If we need to download it or we're downloading everyting
                            filepath = f"{base_file_path}/{path}/Miniscope/{sub_item.name}"
                            if not os_path.exists(
                                filepath
                            ):  # Will only download a file if it doesn't already exist (Only applies if we're downloading everything)
                                with open(filepath, "wb") as output_file:  # Creates a file to store the data
                                    client.downloads.download_file_to_output_stream(
                                        sub_item.id, output_stream=output_file
                                    )  # Downloads data to the file
                                    print(
                                        f"File '{sub_item.name}' downloaded successfully to '{filepath}'"
                                    )  # DEBUG: Prints that we've successfully downloaded a file. Line won't run if there's an error
                else:  # If for some reason we have a sub-folder that isn't the miniscope folder, we recursively call the function to download it.
                    download_file(
                        client, f"{path}/{item.name}", int(item.id), need_to_download, base_file_path=base_file_path
                    )

            else:
                filepath = f"{base_file_path}/{path}/{item.name}"
                if not os_path.exists(filepath):  # Will only download a file if it doesn't already exist.
                    with open(filepath, "wb") as output_file:  # Creates a file to store the data
                        client.downloads.download_file_to_output_stream(
                            item.id, output_stream=output_file
                        )  # Downloads data to the file
                        print(
                            f"File '{item.name}' downloaded successfully to '{filepath}'"
                        )  # DEBUG: Prints that we've successfully downloaded a file. Line won't run if there's an error

        return True  # Returns True once everthing is downloaded
    except Exception as e:  # Catches any error
        print(f"Download failed: {e}")
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
