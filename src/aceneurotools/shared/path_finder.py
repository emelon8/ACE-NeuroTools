from typing import List, Optional, Tuple, Union
from pathlib import Path

class PathFinder:
    """Utility class for finding files by extension and prefix using pathlib."""
    
    @staticmethod
    def find(
        directory: Optional[Union[str, Path]] = None,
        suffix: Optional[Union[str, List[str], Tuple[str, ...]]] = None, 
        prefix: Optional[Union[str, List[str], Tuple[str, ...]]] = None, 
        file_and_directory: bool = False
    ) -> Optional[Union[List[Path], Tuple[List[Path], List[Path]]]]:
        """
        Modernized file finder using pathlib.
        Returns a sorted list of matching Path objects.
        """
        if directory is None:
             raise ValueError("Directory must be provided to PathFinder.find()")

        dir_path: Path = Path(directory)
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        # Normalize input parameters for suffix and prefix:
        ext_tuple: Optional[Tuple[str, ...]] = None
        if suffix is not None:
            if isinstance(suffix, str):
                ext_tuple = (suffix,)
            elif isinstance(suffix, list):
                ext_tuple = tuple(suffix)
            else:
                ext_tuple = suffix

        start_tuple: Optional[Tuple[str, ...]] = None
        if prefix is not None:
            if isinstance(prefix, str):
                start_tuple = (prefix,)
            elif isinstance(prefix, list):
                start_tuple = tuple(prefix)
            else:
                start_tuple = prefix

        matches: List[Path] = []
        for path in dir_path.rglob('*'):
            if not path.is_file():
                continue
            
            if 'saved_movies' in path.parts:
                    continue

            # Check file extension if provided.
            if ext_tuple and path.suffix not in ext_tuple:
                continue

            # Check filename prefix if provided.
            if start_tuple and not path.name.startswith(start_tuple):
                continue

            matches.append(path)

        if not matches:
            print(f"No files found matching criteria in {dir_path}. Returning None...")
            return None

        # Sort by modification time.
        sorted_paths: List[Path] = sorted(matches, key=lambda p: p.stat().st_mtime)

        if file_and_directory:
            dirs: List[Path] = sorted(list({p.parent for p in sorted_paths}), key=lambda p: p.stat().st_mtime)
            return sorted_paths, dirs

        return sorted_paths
