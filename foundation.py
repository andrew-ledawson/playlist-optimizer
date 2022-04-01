import glob, pickle
from importlib.metadata import metadata
from functools import total_ordering

class Playlist:
    name = ""
    songs = {}
    yt_id = ""

@total_ordering
class Song:
    album = None
    artist = None
    name = None
    duration_s = None # integer

    yt_id = None
    spotify_id = None
    # None if not downloaded, false if all downloaded, true if downloaded with error
    metadata_needs_review = None

    camelot_position = None
    camelot_is_minor = None
    bpm = None

    # A dict of user ratings (dict values) (+2 to -2) for each custom trait (dict keys)
    # TODO: Create a rating module that uses youtube-dl/yt-dlp and external player like ffmpeg to play portion/offset
    # Partial download: https://www.reddit.com/r/youtubedl/wiki/downloadingytsegments
    # Partial download: https://www.reddit.com/r/youtubedl/wiki/howdoidownloadpartsofavideo
    # YouTube DASH stream formats: https://gist.github.com/AgentOak/34d47c65b1d28829bb17c24c04a0096f
    user_ratings = {}
    owning_playlists = []

    def __lt__(self, other) -> bool:
        # Ensure other object is a Song
        if not isinstance(other, Song):
            return False

        # Priority one: YT ID known
        if self.yt_id is None and other.yt_id is not None:
            return True

        # Priority two: Metadata doesn't need review
        # or we at least know if it needs review (i.e. is set)
        if self.metadata_needs_review == True and other.metadata_needs_review == False or\
           self.metadata_needs_review is None and other.metadata_needs_review is not None:
            return True

        # Priority three: Basic metadata known (including Spotify ID)
        def get_missing_metadata_count(target_song_obj, field_names):
            missing_field_count = 0
            for field_name in field_names:
                if getattr(target_song_obj, field_name) is None:
                    missing_field_count = missing_field_count + 1
            return missing_field_count

        basic_fields = ['album', 'artist', 'name', 'duration_s', 'spotify_id']
        if get_missing_metadata_count(self, basic_fields) > get_missing_metadata_count(other, basic_fields):
            return True

        # Priority four: Advanced "feature" metadata known
        advanced_fields = ['camelot_position', 'camelot_is_minor', 'bpm']
        if get_missing_metadata_count(self, advanced_fields) > get_missing_metadata_count(other, advanced_fields):
            return True

        # Priority five: Rated with as many current keys as possible
        def get_ratings_count(target_ratings_dict):
            ratings_count = 0
            for rating_name in USER_RATINGS.keys:
                if rating_name in target_ratings_dict and target_ratings_dict[rating_name] is not None:
                    ratings_count = ratings_count + 1
            return ratings_count
        return get_ratings_count(self.user_ratings) < get_ratings_count(other.user_ratings)

    def __eq__(self, other) -> bool:
        # Ensure other object is a Song
        if not isinstance(other, Song):
            return False

        # Check all basic fields (i.e. all fields with a few exceptions)
        basic_fields = dir(Song)
        basic_fields.remove('user_ratings')
        basic_fields.remove('owning_playlists')
        for member_name in basic_fields:
            if getattr(self, member_name) != getattr(other, member_name):
                return False
    
        # Check user ratings, ignoring deprecated ratings
        for rating_name in USER_RATINGS.keys:
            if (rating_name in self.user_ratings != rating_name in other.user_ratings) or (self.user_ratings[rating_name] != other.user_ratings[rating_name]):
                return False

        # Ignore owning playlists since that just relates to 
        return True

    # Owning playlists is an instance-dependent variable that should not be pickled
    def __getstate__(self):
        state = self.__dict__.copy()
        state['owning_playlists'] = []
        return state

# A dictionary of user-ratable traits for each song, where each key is the name of a category
# and each value is its explanation.  Capitalize correctly for UI display.  
# Can be updated by adding new rating fields and/or moving out deprecated fields.  
USER_RATINGS = {'Positivity' : 'Hopeful and optimistic, or regretful and pessimistic.',
                'Drive' : 'Driving and forceful, or unhurried and gentle.',
                'Presence' : 'Captivating and focused, or detached and distant.',
                'Complexity' : 'Crowded and busy, or simple and manageable.'}

# Deprecated ratings can be moved here so program will prompt users to re-rate accordingly
DEPRECATED_RATINGS = {}

PLAYLIST_FILE_PREFIX = 'playlist_'
PLAYLIST_FILE_EXTENSION = '.pp1'

# Loads local playlist files into a dict (keyed by YT id) and returns it.  Takes optional path argument.
# Also returns dict of songs by YT id
def load_local_playlists(path = '.'):
    playlist_files = glob.glob(PLAYLIST_FILE_PREFIX + '*' + PLAYLIST_FILE_EXTENSION, dir_fd=glob.glob(path))
    saved_playlists = {}
    for playlist_file_name in playlist_files:
        playlist_file = open(playlist_file_name, "rb")
        playlist = pickle.load(playlist_file)
        playlist_file.close()
        saved_playlists[playlist.yt_id] = playlist

    all_seen_songs = {}
    for saved_playlist in saved_playlists.values:
        for song in saved_playlist.songs:
            if song.yt_id in all_seen_songs:
                all_seen_songs[song.yt_id].owning_playlists.append(saved_playlist.yt_id)
                if song != all_seen_songs[song.yt_id]:
                    print("Warning: song \"" + song.name + "\" by \"" + song.artist + "\" has a duplicate that differs.  Please fix this in the rater program.  ")

    return saved_playlists, all_seen_songs
