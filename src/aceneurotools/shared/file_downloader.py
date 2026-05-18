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
    if os_path.exists(full_path): # If we already have the folder, then we don't need to download anything
        if not listdir(full_path):
            return False #If the folder is empty (i.e., the download connection failed), it will still return false so verify_file will download it.
        return True # This will  return True even if the downloads are incomplete
    else:
        # Note: In recursive mode, the downloader handles makedirs
        return False

def verify_file_by_line(
    line_num: int | str,
    csv_path: str | Path,
    do_type: str = "both",
    avi_list: list[str] = [],
    base_file_path: str | Path | None = None
) -> bool:
    """Checks if experimental data exists locally. If files are missing and Box IDs
    are provided in the CSV, attempts to download them from Box.
    
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

    # Implementation logic matches user-provided script but preserves decoupling
    if is_box_configured():
        line_num_str = str(line_num)
        if do_type not in ["both", "miniscope", "ephys"]:
            raise ValueError("variable 'do_type' must be 'both', 'miniscope', or 'ephys'")

        try:
            df = pd.read_csv(csv_path)
            df.columns = df.columns.str.strip()
            if "line number" not in df.columns:
                print(f"Error: 'line number' column missing in {csv_path}")
                return False
            df.set_index("line number", inplace=True)
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

        downloaded_miniscope, downloaded_ephys = False, False
        need_to_download = [avi for avi in avi_list if not verify_avi(miniscope_path, avi, base_file_path=base_file_path)]

        client = None

        if do_type in ["both", "miniscope"]:
            if pd.isnull(miniscope_path) or pd.isnull(miniscope_id):
                print("The miniscope path or ID do not exist in the CSV file, cannot download")
            else:
                # Trigger sync if path missing, or if specific files requested, or if avi_list is empty (sync all)
                if not verify_path(miniscope_path, base_file_path=base_file_path) or need_to_download or not avi_list:
                    if not client:
                        client = make_auth()
                        if not client: return False
                    print(f"Syncing Miniscope data from Box (ID: {miniscope_id})...")
                    downloaded_miniscope = download_file(client, miniscope_path, int(miniscope_id), need_to_download, base_file_path=base_file_path)
                else:
                    downloaded_miniscope = True

        if do_type in ["both", "ephys"]:
            if pd.isnull(ephys_path) or pd.isnull(ephys_id):
                print("The ephys path or ID do not exist in the CSV file, cannot download")
            elif not verify_path(ephys_path, base_file_path=base_file_path):
                if not client:
                    client = make_auth()
                    if not client: return False
                print(f"Syncing Ephys data from Box (ID: {ephys_id})...")
                downloaded_ephys = download_file(client, ephys_path, int(ephys_id), base_file_path=base_file_path)
            else:
                downloaded_ephys = True

        if do_type == "both":
            return downloaded_miniscope and downloaded_ephys
        elif do_type == "miniscope":
            return downloaded_miniscope
        elif do_type == "ephys":
            return downloaded_ephys
    else:
        # If Box is not configured, we check if IDs were intended
        try:
            df = pd.read_csv(csv_path)
            df.columns = df.columns.str.strip()
            if "line number" in df.columns:
                df.set_index("line number", inplace=True)
                line_num_str = str(line_num)
                if line_num_str in df.index:
                    m_id = df.at[line_num_str, "Box Calcium Folder ID"]
                    e_id = df.at[line_num_str, "Box ephys folder ID"]
                    if not pd.isnull(m_id) or not pd.isnull(e_id):
                        print("\n[Box Sync skipped]")
                        print("Box IDs found in metadata, but credentials (box_credentials.py) are not configured.")
                        print("To enable automatic downloads, follow setup instructions in:")
                        print("  docs/guides/data_management.md#optional-box-cloud-integration\n")
        except Exception:
            pass
        return None

def make_auth() -> Any | None:
    """Creates the box client object to connect to the box servers."""
    if not is_box_configured():
        return None
    
    try:
        from box_sdk_gen import BoxClient
        from aceneurotools.shared.box_credentials import auth, dev_token # noqa: F401
        
        client = BoxClient(auth=auth)
        print("Successfully connected to Box client")
        return client
    except Exception as e:
        print(f"Failed to connect to Box: {e}")
        return None

def get_all_folder_items(client: Any, folder_id: int | str) -> list[Any]:
    """Retrieve all items from a Box folder, handling pagination."""
    all_items = []
    offset = 0
    limit = 1000
    while True:
        page = client.folders.get_folder_items(str(folder_id), offset=offset, limit=limit)
        all_items.extend(page.entries)
        if len(page.entries) < limit:
            break
        offset += limit
    return all_items

def download_file(
    client: Any,
    path: str,
    ID: int,
    need_to_download: list[str] = [],
    base_file_path: str | Path | None = None
) -> bool:
    """Recursively download files from a Box folder."""
    if base_file_path is None:
        raise ValueError("base_file_path is required for downloading files.")
    
    try:
        items = get_all_folder_items(client, ID)
        for item in items:
            if item.type == 'folder':
                sub_path = f"{base_file_path}/{path}/{item.name}"
                if not os_path.exists(sub_path):
                    makedirs(sub_path)
                
                if item.name == "Miniscope":
                    # Special logic for Miniscope folder: filter by need_to_download if provided
                    for sub_item in get_all_folder_items(client, item.id):
                        is_requested = (sub_item.name in need_to_download) or (not need_to_download)
                        is_not_avi = "avi" not in sub_item.name
                        
                        if is_requested or is_not_avi:
                            filepath = f"{sub_path}/{sub_item.name}"
                            if not os_path.exists(filepath):
                                with open(filepath, "wb") as output_file:
                                    client.downloads.download_file_to_output_stream(sub_item.id, output_stream=output_file)
                                    print(f"File '{sub_item.name}' downloaded successfully to '{filepath}'")
                else:
                    # Recursive download for other folders
                    download_file(client, f"{path}/{item.name}", int(item.id), need_to_download, base_file_path=base_file_path)
            else:
                filepath = f"{base_file_path}/{path}/{item.name}"
                if not os_path.exists(filepath):
                    with open(filepath, "wb") as output_file:
                        client.downloads.download_file_to_output_stream(item.id, output_stream=output_file)
                        print(f"File '{item.name}' downloaded successfully to '{filepath}'")
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

if __name__ == '__main__':
    import argparse
    import sys
    from aceneurotools.multimodal.lab_config import LabConfig

    parser = argparse.ArgumentParser(description="Download experiment data from Box")
    parser.add_argument('--project-path', type=str, required=True,
                        help="Path to project directory (containing experiments.csv)")
    parser.add_argument('--config', type=str,
                        help="Path to lab_config.json (to resolve data-path automatically)")
    parser.add_argument('--data-path', type=str,
                        help="Base path for raw experimental data storage")
    parser.add_argument('--line-num', type=int, default=96,
                        help="Experiment line number")
    parser.add_argument('--filenames', nargs='*', default=[],
                        help="Specific filenames to download (default: all)")
    parser.add_argument('--do-type', type=str, default="miniscope",
                        choices=["both", "miniscope", "ephys"])
    args = parser.parse_args()

    # Resolve data_path
    data_path = args.data_path
    if not data_path and args.config:
        try:
            config = LabConfig.from_json(Path(args.config))
            if config.paths:
                data_path = config.paths.data_path
        except Exception as e:
            print(f"Warning: Could not load data_path from config: {e}")

    if not data_path:
        print("Error: --data-path or --config (with data_path set) is required.")
        sys.exit(1)

    experiments_csv = Path(args.project_path) / "experiments.csv"
    verify_file_by_line(
        line_num=args.line_num,
        csv_path=experiments_csv,
        do_type=args.do_type,
        avi_list=args.filenames,
        base_file_path=data_path
    )
