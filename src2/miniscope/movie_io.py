import os
import caiman as cm




class MovieIO:
    @staticmethod
    def save_movie(movie: cm.movie, miniscope_dir_path, movie_file_name):        
        # create the saved_movies directory if it doesn't exist
        saved_movies_dir = os.path.join(miniscope_dir_path, 'saved_movies')
        os.makedirs(saved_movies_dir, exist_ok=True)

        # create the filename
        file_name = os.path.join(saved_movies_dir, movie_file_name) + '.avi'

        # save movie
        print(f"saving movie: {file_name}\n\n")
        movie.save(file_name, compress=0)
        
        # return the full file path
        return file_name
    
    @staticmethod
    def load_movie(miniscope_dir_path, movie_file_name):
        # Load the movie from the specified file path
        path = os.path.join(miniscope_dir_path, 'saved_movies', movie_file_name)
        return cm.load(path)
    