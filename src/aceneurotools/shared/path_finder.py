from pathlib import Path


class PathFinder:
    """Utility class for finding files by extension and prefix using pathlib."""

    @staticmethod
    def find(
        directory: str | Path | None = None,
        suffix: str | list[str] | tuple[str, ...] | None = None,
        prefix: str | list[str] | tuple[str, ...] | None = None,
        file_and_directory: bool = False,
        exclude_dirs: tuple[str, ...] | None = ('saved_movies',),
    ) -> list[Path] | tuple[list[Path], list[Path]] | None:
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
        ext_tuple: tuple[str, ...] | None = None
        if suffix is not None:
            if isinstance(suffix, str):
                ext_tuple = (suffix,)
            elif isinstance(suffix, list):
                ext_tuple = tuple(suffix)
            else:
                ext_tuple = suffix

        start_tuple: tuple[str, ...] | None = None
        if prefix is not None:
            if isinstance(prefix, str):
                start_tuple = (prefix,)
            elif isinstance(prefix, list):
                start_tuple = tuple(prefix)
            else:
                start_tuple = prefix

        matches: list[Path] = []
        for path in dir_path.rglob('*'):
            if not path.is_file():
                continue

            if exclude_dirs and any(part in path.parts for part in exclude_dirs):
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
        sorted_paths: list[Path] = sorted(matches, key=lambda p: p.stat().st_mtime)

        if file_and_directory:
            dirs: list[Path] = sorted(list({p.parent for p in sorted_paths}), key=lambda p: p.stat().st_mtime)
            return sorted_paths, dirs

        return sorted_paths
