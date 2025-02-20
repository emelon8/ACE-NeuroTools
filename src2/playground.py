
def convert_ca_movies(self, filenames=None, new_file_type='.tif',
join_movies=False, metadata_convert=True):
    """"
    Parameters:
  filenames: Optional list (or single) of filenames to convert. If None,
      try to load filenames from self.find_movie_file_paths() (using the
      'calcium imaging directory' in self.experiment).
  new_file_type: The file extension/type to which to convert (supported by CaImAn).
  join_movies: If True, all movie files will be joined and converted into one file.
  metadata_convert: If True, the metaData will be converted/combined
      using the _meta_data_converter() method.

    The new filename is based on the first filename with the new extension appended.
    """

    print('Converting movies...')

    # Preserve any passed filenames value for later checks.
    original_filenames = filenames
    failed_videos = []

    # If no filenames are provided, load them from the experiment directory.
    if filenames is None:
        if hasattr(self, 'movie'):
            print("self.movie exists, but no filenames were provided; "
                "loading movie file paths from the experiment directory.")
        self.find_movie_file_paths()
        filenames = self.movieFilePaths

    # Ensure we have a list.
    if not isinstance(filenames, list):
        filenames = [filenames]

    # If a "movie" attribute exists and no filenames were explicitly provided,
    # use self.movie and save directly.
    if hasattr(self, 'movie') and original_filenames is None:
        new_filename = os.path.splitext(filenames) + new_file_type
        self.movie.save(new_filename)
    else:
        if join_movies:
            try:
                # load_movie_chain joins all movies into one
                movies = cm.load_movie_chain(filenames)
                new_filename = os.path.splitext(filenames) + new_file_type
                movies.save(new_filename)
            except Exception as e:
                print(f"Error joining and saving movies: {e}")
                failed_videos.extend(filenames)
        else:
            for fname in filenames:
                # If the file does not exist, try prepending the known directory.
                if not os.path.isfile(fname):
                    fname = os.path.join(self.experiment['calcium imaging directory'],
                                        'Miniscope', fname)
                try:
                    movie = cm.load(fname)
                    new_filename = os.path.splitext(fname) + new_file_type
                    movie.save(new_filename)
                except Exception as e:
                    print(f"Error processing {fname}: {e}")
                    failed_videos.append(fname)

    if metadata_convert:
        self._meta_data_converter()

    if failed_videos:
        print('Errors occurred with the following videos:')
        for failed in failed_videos:
            print(f"  {failed}")
        print('Consider investigating these issues.')
