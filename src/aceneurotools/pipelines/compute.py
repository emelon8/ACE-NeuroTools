"""Generates meanFluorescence_<line_num>.npz files from raw miniscope .avi recordings."""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from aceneurotools.multimodal.lab_config import LabConfig


class ComputePipeline:
    """Generates mean-fluorescence .npz files from raw miniscope recordings.

    Heavy imports (caiman, MiniscopeDataManager) are deferred to method bodies
    so the class can be imported without the full scientific stack.
    """

    def run(
        self,
        project_path: str | Path,
        lab_config: LabConfig,
        calcium_signal_dir: str | Path,
        data_path: str | Path | None = None,
        line_nums: list[int] | None = None,
        headless: bool = False,
        verbose: bool = False,
    ) -> dict[int, Path]:
        """Process a set of subjects and return {line_num: npz_path} for successful ones."""
        project_path = Path(project_path)
        output_dir = Path(calcium_signal_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        subjects = line_nums if line_nums else lab_config.all_line_nums()
        completed: dict[int, Path] = {}

        print(f"  Subjects to process ({len(subjects)}): {subjects}")
        print(f"  Output directory: {output_dir}\n")

        for line_num in subjects:
            print(f"  [compute] line {line_num}")
            try:
                result = self._process_subject(
                    line_num=line_num,
                    project_path=project_path,
                    data_path=Path(data_path) if data_path is not None else None,
                    output_dir=output_dir,
                    headless=headless,
                    verbose=verbose,
                )
                if result is not None:
                    completed[line_num] = result
                    print(f"  [compute] line {line_num} — saved to: {result.name}")
            except Exception as exc:
                print(f"  [compute] line {line_num} SKIPPED — {type(exc).__name__}: {exc}")
                if verbose:
                    traceback.print_exc()

        n_ok = len(completed)
        n_skip = len(subjects) - n_ok
        print(f"\n  Compute complete: {n_ok} subject(s) saved, {n_skip} skipped.")
        return completed

    def _process_subject(
        self,
        line_num: int,
        project_path: Path,
        data_path: Path | None,
        output_dir: Path,
        headless: bool,
        verbose: bool,
    ) -> Path | None:
        # Skip if output already exists
        save_path = output_dir / f"meanFluorescence_{line_num}.npz"
        if save_path.exists():
            print(f"    meanFluorescence_{line_num}.npz already exists — skipping.")
            return save_path

        import caiman as cm

        from aceneurotools.miniscope.miniscope_data_manager import MiniscopeDataManager
        from aceneurotools.miniscope.miniscope_preprocessor import MiniscopePreprocessor
        from aceneurotools.shared import file_downloader
        from aceneurotools.shared.experiment_data_manager import ExperimentDataManager
        from aceneurotools.shared.misc_functions import get_coords_dict_from_analysis_params
        from aceneurotools.shared.path_finder import PathFinder

        # Ensure data is downloaded if Box IDs are present
        file_downloader.verify_file_by_line(
            line_num,
            project_path / "experiments.csv",
            "miniscope",
            base_file_path=data_path if data_path else project_path
        )

        meta_dm = ExperimentDataManager(
            line_num,
            project_path=project_path,
            data_path=data_path,
            auto_import_metadata=True,
            auto_import_analysis_params=False,
        )
        if meta_dm.metadata is None:
            raise ValueError(f"No metadata found for line {line_num} in experiments.csv")

        movie_directory = meta_dm.get_miniscope_directory()
        if movie_directory is None:
            raise ValueError(
                f"No 'calcium imaging directory' set in experiments.csv for line {line_num}"
            )

        raw_paths = PathFinder.find(str(movie_directory), suffix=".avi")
        if not raw_paths:
            raise FileNotFoundError(f"No .avi files found in {movie_directory}")

        try:
            sorted_filepaths = sorted(
                [Path(str(p)) for p in raw_paths],
                key=lambda p: int(p.stem),
            )
        except ValueError:
            sorted_filepaths = sorted(
                [Path(str(p)) for p in raw_paths],
                key=lambda p: p.stem,
            )

        n_files = len(sorted_filepaths)
        if verbose:
            print(f"    Found {n_files} .avi file(s) in {movie_directory}")

        # use middle 10 files for crop preview, not the start/end of the recording
        mid_start = max(0, n_files // 2 - 5)
        mid_end = min(n_files, mid_start + 10)
        sample_basenames = [p.name for p in sorted_filepaths[mid_start:mid_end]]

        sample_dm = MiniscopeDataManager.create(
            line_num,
            project_path=project_path,
            data_path=data_path,
            filenames=sample_basenames,
        )

        coords_dict, _ = get_coords_dict_from_analysis_params(sample_dm)
        preprocessor = MiniscopePreprocessor(sample_dm)
        final_coords = None

        if coords_dict is not None:
            # Saved coordinates — use directly, no GUI or projection needed.
            final_coords = coords_dict
            x0, x1 = coords_dict.get("x0", "?"), coords_dict.get("x1", "?")
            y0, y1 = coords_dict.get("y0", "?"), coords_dict.get("y1", "?")
            print(
                f"    Crop coordinates loaded from analysis_parameters.csv: "
                f"x=[{x0}, {x1}]  y=[{y0}, {y1}]"
            )
        elif headless:
            print(
                "    No saved crop coordinates found and running headless.\n"
                "    Processing full frame — mean fluorescence computed over all pixels.\n"
                "    To add cropping: re-run without --headless to use the interactive crop GUI."
            )
        else:
            # Interactive: show GUI so researcher can draw crop boundary
            projections = preprocessor.compute_projections(sample_dm.movie)
            print(
                "    No saved crop coordinates found.\n"
                "    Opening crop GUI... (close the window to accept or skip cropping)"
            )
            final_coords = preprocessor.get_crop_coordinates(
                coords_dict,
                projections,
                sample_dm.movie.shape[1],
                sample_dm.movie.shape[2],
            )
            if final_coords is not None:
                print("    Crop coordinates saved and will be applied.")
            else:
                print(
                    "    No crop coordinates were provided.\n"
                    "    Processing full frame — mean fluorescence computed over all pixels."
                )

        mean_fluorescence = np.array([])
        for fp in sorted_filepaths:
            if verbose:
                print(f"    processing: {fp.name}")
            movie = cm.load(str(fp))
            if final_coords is not None:
                movie, _ = preprocessor.crop_movie(movie, final_coords)
            time_projection = movie.mean(axis=(1, 2))
            mean_fluorescence = np.concatenate((mean_fluorescence, time_projection))

        save_path = output_dir / f"meanFluorescence_{line_num}.npz"
        np.savez_compressed(str(save_path), meanFluorescence=mean_fluorescence)
        return save_path


# CLI

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="python -m aceneurotools.pipelines.compute",
        description=(
            "Generate meanFluorescence_<line_num>.npz files from raw "
            "miniscope .avi recordings."
        ),
    )
    parser.add_argument(
        "--project-path",
        required=True,
        metavar="PATH",
        help="Directory containing experiments.csv.",
    )
    parser.add_argument(
        "--lab-config",
        required=True,
        metavar="PATH",
        help="Path to lab_config.json.",
    )
    parser.add_argument(
        "--calcium-signal-dir",
        required=True,
        metavar="PATH",
        help="Output directory for meanFluorescence_<line_num>.npz files.",
    )
    parser.add_argument(
        "--data-path",
        metavar="PATH",
        help="Base directory for raw data.  Uses experiments.csv value when omitted.",
    )
    parser.add_argument(
        "--line-nums",
        nargs="+",
        type=int,
        metavar="N",
        help="Subjects to process.  Defaults to all subjects in lab_config.json.",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Skip crop GUI; use saved coordinates or full-frame mean.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-file progress.",
    )

    _args = parser.parse_args()

    from aceneurotools.multimodal.lab_config import LabConfig
    from aceneurotools.shared.exceptions import ConfigurationError, print_cli_error

    try:
        _lab_config = LabConfig.from_json(_args.lab_config)
    except ConfigurationError as _exc:
        print_cli_error(_exc)
        sys.exit(1)

    _pipeline = ComputePipeline()
    _pipeline.run(
        project_path=_args.project_path,
        data_path=_args.data_path,
        lab_config=_lab_config,
        calcium_signal_dir=_args.calcium_signal_dir,
        line_nums=_args.line_nums,
        headless=_args.headless,
        verbose=_args.verbose,
    )
