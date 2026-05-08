import os
import caiman as cm




class MovieIO:
    """Static utility class for saving and loading CaImAn movies.
    
    Provides standardized methods for movie I/O to the saved_movies directory.
    """
    
    @staticmethod
    def save_movie(dm, movie_file_name, movie=None): 
        """Save a movie to disk in the saved_movies directory.
        
        Args:
            dm: MiniscopeDataManager with metadata for directory path.
            movie_file_name: Base filename (without extension).
            movie: Optional movie to save; uses dm.movie if None.
            
        Returns:
            Full path to the saved .avi file.
        """
        
        # create the saved_movies directory if it doesn't exist
        miniscope_dir_path = dm.metadata['calcium imaging directory']
        
        saved_movies_dir = os.path.join(miniscope_dir_path, 'saved_movies')
        os.makedirs(saved_movies_dir, exist_ok=True)

        # create the filename
        file_name = os.path.join(saved_movies_dir, movie_file_name) + '.avi'

        # save movie
        print(f"saving movie: {file_name}\n\n")
        #uses caiman movie method .save() to save what is stored in data_manager.movie
        if movie is not None:
            movie.save(file_name, compress=0)
        else:
            dm.movie.save(file_name, compress=0)
        
        # return the full file path
        return file_name
    
    @staticmethod
    def load_movie(miniscope_dir_path, movie_file_name):
        """Load a movie from the saved_movies directory.
        
        Args:
            miniscope_dir_path: Path to the miniscope data directory.
            movie_file_name: Filename of the movie to load.
            
        Returns:
            CaImAn movie object.
        """
        # Load the movie from the specified file path
        path = os.path.join(miniscope_dir_path, 'saved_movies', movie_file_name)
        return cm.load(path)
    