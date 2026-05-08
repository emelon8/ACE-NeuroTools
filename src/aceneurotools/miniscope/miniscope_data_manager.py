import csv
import json
import os
import caiman as cm
from caiman.base.movies import movie
import numpy as np
from aceneurotools.shared.path_finder import PathFinder
from aceneurotools.shared.experiment_data_manager import ExperimentDataManager
import aceneurotools.shared.file_downloader as file_downloader
from abc import ABC, abstractmethod
from aceneurotools.shared.exceptions import DataImportError
from typing import List, Tuple, Optional, Union, Dict, cast, Any, Tuple, Type, TypeVar, cast
from pathlib import Path

T = TypeVar("T", bound="MiniscopeDataManager")

class MiniscopeDataManager(ExperimentDataManager, ABC):
    """Manages raw Miniscope data import and storage.
    
    Abstract Base Class for Miniscope data managers.
    
    Attributes:
        line_num: Experiment line number in experiments.csv.
        time_stamps: Array of frame timestamps in seconds.
        frame_numbers: List of frame indices.
        all_movie_filepaths: All discovered .avi movie files.
        chosen_movie_filepaths: Subset selected by filenames parameter.
        movie: Loaded CaImAn movie object.
        fr: Frame rate from metadata.
    """
    
    _registry: List[Type['MiniscopeDataManager']] = []
    line_num: int
    time_stamps: Optional[np.ndarray]
    frame_numbers: Optional[np.ndarray]
    all_movie_filepaths: List[Union[Path, str]]
    chosen_movie_filepaths: Optional[List[Union[str, Path]]]
    movie: movie
    fr: float
    projections: Any
    preprocessed_movie_filepath: Optional[str]
    coords: Optional[Dict[str, int]]
    motion_corrected_movie_filepath: Optional[str]
    CNMFE_obj: Any
    estimates_filepath: Optional[str]
    opts_caiman_filepath: Optional[str]
    analysis_params: Optional[Dict[str, Any]]
    dview: Any
    opts_caiman: Any
    ca_events_idx: Any
    PSD_spect: Any
    t_spect: Any
    freqs_spect: Any
    p_spect: Any
    miniscope_phases: Any
    filter_object: Any
    miniscope_events: Any
    Cn: Optional[np.ndarray]
    filenames: Optional[List[str]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls not in cls._registry:
            cls._registry.append(cls)

    @classmethod
    def create(
        cls: Type[T], 
        line_num: int, 
        project_path: Optional[Union[str, Path]] = None,
        data_path: Optional[Union[str, Path]] = None,
        **kwargs: Any
    ) -> T:
        """Factory method to select the correct subclass for the directory.
        
        Args:
            line_num: Experiment line number.
            project_path: Optional explicit project repository path.
            data_path: Optional explicit data storage path.
            **kwargs: Additional arguments for subclass initialization.
        """
        temp_edm = ExperimentDataManager(
            line_num, 
            project_path=project_path, 
            data_path=data_path,
            auto_import_metadata=True, 
            auto_import_analysis_params=False
        )
        directory = temp_edm.get_miniscope_directory()
        
        if directory is None:
             raise ValueError(f"No miniscope directory set in metadata for line {line_num}")
             
        for subclass in cls._registry:
            if subclass.can_handle(directory):
                return cast(T, subclass(
                    line_num=line_num, 
                    project_path=project_path,
                    data_path=data_path,
                    **kwargs
                ))
                
        raise ValueError(f"No MiniscopeDataManager subclass found that can handle directory: {directory}")

    @classmethod
    @abstractmethod
    def can_handle(cls, directory: Union[str, Path]) -> bool:
        """Return True if this class can handle the format in the given directory."""
        pass

    def __init__(
        self, 
        line_num: int, 
        project_path: Optional[Union[str, Path]] = None,
        data_path: Optional[Union[str, Path]] = None,
        filenames: List[str] = [], 
        auto_import_data: bool = True
    ) -> None:
        """Initialize data manager and optionally load movie data.
        
        Args:
            line_num: Row number in experiments.csv to load.
            project_path: Optional explicit project repository path.
            data_path: Optional explicit data storage path.
            filenames: Optional list of specific movie filenames to load.
            auto_import_data: If True, automatically load movie and metadata.
        """
        super().__init__(line_num, project_path=project_path, data_path=data_path)
        self.line_num = line_num
        self.time_stamps = None
        self.frame_numbers = None
        
        experiments_csv = self.project_path / "experiments.csv"
        file_downloader.verify_file_by_line(
            line_num, 
            experiments_csv, 
            "miniscope", 
            filenames,
            base_file_path=self.data_path
        )
        self.all_movie_filepaths = cast(List[Union[Path, str]], self._find_movie_file_paths())
        self.chosen_movie_filepaths = self._get_specific_filepaths(filenames)
        
        if (auto_import_data):
            self.load_attributes(self.chosen_movie_filepaths if self.chosen_movie_filepaths else self.all_movie_filepaths)
            
        #Attributes below are filled in automatically during the miniscope_pipeline pipeline: preprocessing->processing->postprocessing
        
        self.projections = None
        self.preprocessed_movie_filepath = None #Your preprocessed movie must be saved to disk and its filepath stored here before processing
        self.coords = None #contains the coordinates/shape of your cropped movie
        self.motion_corrected_movie_filepath = None
        self.CNMFE_obj = None
        self.estimates_filepath = None
        self.dview = None
        self.opts_caiman = None
        self.ca_events_idx = None
        self.PSD_spect = None
        self.t_spect = None
        self.freqs_spect = None
        self.p_spect = None
        self.miniscope_phases = None
        self.filter_object = None
            

    def load_attributes(self, filepaths: List[Union[str, Path]]) -> None:
        """Load movie data and metadata from disk.
        
        Populates metadata, timestamps, movie array, events, and frame rate.
        
        Args:
            filepaths: List of movie file paths to load.
        """
        if self.metadata is None:
            self.metadata = {}
        self.metadata.update(self._get_miniscope_metadata()) # add miniscope metadata to overall metadata
        ts, fn = self._get_timestamps()
        self.time_stamps = np.array(ts) if ts is not None else None
        self.frame_numbers = np.array(fn) if fn is not None else None
        self.movie = self._get_movies(filepaths)  # import calcium imaging data
        self.miniscope_events = self._get_miniscope_events()
        self.fr = float(self.metadata['frameRate']) if self.metadata else 30.0

    @abstractmethod
    def sync_timestamps(
        self, 
        ephys_dm: Optional[Any] = None, 
        channel_name: Optional[str] = None, 
        **kwargs: Any
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Synchronize miniscope frame timestamps to ephys time.
        
        Args:
            ephys_dm: Optional EphysDataManager to sync against.
            channel_name: Optional channel name for the ephys_dm.
            
        Returns:
            Tuple containing:
            - tCaIm (np.ndarray): The aligned miniscope frame timestamps in ephys time.
            - low_confidence_periods (np.ndarray): Array of [start, end] indices where gap interpolation occurred.
        """
        pass

    def convert_ca_movies(
        self, 
        filenames: Optional[List[str]] = None, 
        new_file_type: str = '.tif', 
        join_movies: bool = False, 
        metadata_convert: bool = True
    ) -> None:
        """
        Convert calcium movies from one type to another. File types must be supported by CaImAn.
        
        The new filename(s) is based on the first filename in 'filenames', with new_file_type appended.
        'join_movies' determines whether all movie files in 'filenames' are combined into a single movie,
        or whether each file is converted separately.
        
        If 'filenames' is None, the method will attempt to load filenames from self.movieFilePaths.
        """
        print("Converting movies...")
        original_filenames = filenames  # Preserve the original argument
        error_videos = []

        # If no filenames provided, try to load from self.movieFilePaths
        if filenames is None:
            filenames_list: List[str] = [str(p) for p in self.all_movie_filepaths]
        elif not isinstance(filenames, list):
            filenames_list = [filenames]
        else:
            filenames_list = filenames

        # Use the first filename as a basis for the new filename.
        base_new_filename = os.path.splitext(filenames_list[0])[0]

        # If self.movie exists and no filenames were explicitly provided, use the existing movie.
        if hasattr(self, 'movie') and original_filenames is None:
            new_filename = f"{base_new_filename}{new_file_type}"
            self.movie.save(new_filename, compress=0)
        else:
            if join_movies:
                # Join movies: load the movie chain and save as a single new movie.
                try:
                    movies = cm.load_movie_chain(filenames)
                    new_filename = f"{base_new_filename}{new_file_type}"
                    movies.save(new_filename)
                except Exception as e:
                    print(f"Error converting joined movies: {e}")
                    error_videos.extend(filenames_list)
            else:
                # Convert each movie separately.
                for filename in filenames_list:
                    try:
                        # If the file doesn't exist, assume it might be in a default Miniscope directory.
                        if not os.path.isfile(filename):
                            default_dir = os.path.join(self.metadata.get('calcium imaging directory', ''), 'Miniscope') if self.metadata else ''
                            filename = os.path.join(default_dir, str(filename))
                        movie = cm.load(filename)
                        new_filename = f"{os.path.splitext(filename)[0]}{new_file_type}"
                        movie.save(new_filename, compress=0)
                    except (OSError, ValueError, MemoryError) as e:
                        print(f"Error converting movie '{filename}': {e}")
                        error_videos.append(filename)

        if metadata_convert:
            self._meta_data_converter()

        if error_videos:
            print(f"ERRORS with: {error_videos}")
            print("Consider investigating")


    def _meta_data_converter(self) -> None:
        """Convert and merge metadata from multiple JSON files.
        
        Creates a unified metaDataTif.json file combining animal ID, frame rate,
        date, and original metadata from multiple source files.
        """
        fileExts = self._find_metadata_paths()
        for fileExt in fileExts:
            with open(fileExt) as f:
                data = json.loads(f.read())
                if 'animalID' in data:
                    ext = fileExt.replace('\\metaData.json', '\\Miniscope\\metaData.json')
                    animalID = data['animalID']
                    timeStamp = data['recordingStartTime']
                    year = str(timeStamp['year'])
                    month = str('%02d' % timeStamp['month'])
                    day = str('%02d' % timeStamp['day'])
                    second = str('%02d' % timeStamp['second'])
                    minute = str('%02d' % timeStamp['minute'])
                    hour = str('%02d' % timeStamp['hr'])
                    date = year + month + day + '_' + hour + minute + second
                    with open(ext) as d:
                        data2 = json.loads(d.read())
                        if 'frameRate' in data2:
                            try:
                                frameRate = float(data2['frameRate'])
                            except (ValueError, KeyError):
                                frameRate = 30.0
                        else:
                            frameRate = 30.0
                        jdict = {'origin': animalID, 'fps': frameRate, 'date': date,
                                    'orig_meta': [data, data2]}
                        jsonFile = json.dumps(jdict, indent=4)
                        newFileName = ext.replace('\\metaData.json', '\\metaDataTif.json')
                        n = open(newFileName, 'w')
                        n.write(jsonFile)
                        n.close()


    @abstractmethod
    def _get_miniscope_metadata(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def _get_timestamps(self) -> Tuple[Any, Any]:
        pass

    def _get_movies(self, filenames: Optional[Union[str, Path, List[Union[str, Path]]]] = None) -> movie:
        """Import calcium imaging data. Not necessary if using processCaMovies().
        FILENAMES can be a single movie file or a list of movie files (in the order that you want them). 
        If FILENAMES doesn't point to a file (either absolute or relative path from the PWD), 
        it will append the path to the calcium imaging directory to the front of the filename."""
        
        print(f"Converting these filepaths into caiman movies: {filenames}")
        if filenames is None:
            filenames = self.all_movie_filepaths

        # Convert PosixPath objects to strings if necessary.
        if isinstance(filenames, list):
            f_names: List[str] = [str(f) for f in filenames]
            print(f_names)
            m: movie = cm.load_movie_chain(f_names)
        else:
            f_name: str = str(filenames)
            m = cm.load(f_name)

        return m
    
    def _get_specific_filepaths(self, filenames: List[str]) -> Optional[List[Union[str, Path]]]:
        """Filter movie paths to only those matching provided filenames.
        
        Args:
            filenames: List of basenames to match (e.g., ['0.avi', '1.avi']).
            
        Returns:
            List of full paths matching the specified filenames, or None.
        """
        if filenames is None or not isinstance(filenames, list) or len(filenames) == 0:
            return None
        
        matched_paths: List[Union[str, Path]] = []

        for path in self.all_movie_filepaths:
            basename = os.path.basename(str(path))  # Extract basename (e.g., '0.avi' from '/path/to/0.avi')
            if basename in filenames:
                matched_paths.append(path)
        return matched_paths


    @abstractmethod
    def _get_miniscope_events(self) -> Any:
        pass

    @property
    def _calcium_imaging_directory(self) -> str:
        """Returns the directory where calcium imaging data is stored."""
        return str(self.metadata['calcium imaging directory']) if self.metadata else ""

    def _find_file_paths(self, suffix: str, prefix: str = "") -> Union[str, List[str]]:
        """Generalized helper to find files with the given suffix and prefix."""
        filepaths = PathFinder.find(directory=self._calcium_imaging_directory, suffix=suffix, prefix=prefix)
        
        #handle the case where filepaths is a list with only one item
        if isinstance(filepaths, list) and len(filepaths) == 1:
            return str(filepaths[0])
        elif isinstance(filepaths, list):
            return [str(f) for f in filepaths]
        return str(filepaths)

    def _find_metadata_paths(self) -> List[str]:
        """Finds and returns the metadata JSON file path."""
        res = self._find_file_paths(suffix=".json", prefix="metaData")
        return [res] if isinstance(res, str) else res

    def _find_timestamps_path(self) -> str:
        """Finds and returns the timestamps CSV file path."""
        res = self._find_file_paths(suffix=".csv", prefix="timeStamps")
        return res[0] if isinstance(res, list) and res else str(res)

    def _find_movie_file_paths(self) -> List[str]:
        """Finds and returns the list of movie file paths (.avi)."""
        res = self._find_file_paths(suffix=".avi")
        return [res] if isinstance(res, str) else res
        
    def _extract_numeric_suffix(self, filename: str) -> str:
        """
        Extracts and returns the substring of filename starting from the first digit.
        If no digit is found, returns the original filename.
        """
        for i, char in enumerate(filename):
            if char.isdigit():
                return filename[i:]
        return filename
        