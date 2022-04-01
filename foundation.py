import glob, pickle, re, sys, time
import os
from importlib.metadata import metadata
from functools import total_ordering

from ytmusicapi import YTMusic
import spotipy
from spotipy.oauth2 import SpotifyOAuth

"""
Global variables and init scripts
"""

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
SONG_DB_FILE = 'songs.pps'

# Check Python version on init
MIN_PYTHON = (3, 6)
if sys.version_info < MIN_PYTHON:
    sys.exit("Python %s.%s or later is required.\n" % MIN_PYTHON)

YTM = YTMusic('headers_auth.json')
SP = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="CLIENT_ID",
                                               client_secret="CLIENT_SECRET",
                                               redirect_uri="http://www.example.com/",
                                               scope="user-library-read"))

LAST_OP_TIME = time.time()
def pace_ops():
    """Verifies when last query was sent and waits until it's safe to send another"""
    global LAST_OP_TIME
    remaining_time = (LAST_OP_TIME + 1) - time.time()
    if remaining_time > 0:
        time.sleep(remaining_time)
    LAST_OP_TIME = time.time()

"""
Global classes
"""

class Playlist:
    name = None
    songs_ids = [] # YouTube ID strings
    yt_id = None

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

"""
Global funtions
"""

def get_user_bool(message):
    """Prompts the user to input 'y' or 'n' with a message"""
    user_input = ""
    while user_input != 'y' and user_input != 'n':
        user_input = input(message + "(y/n)")
    return user_input == 'y'

def download_metadata(id):
    """Takes a YouTube song ID and gets basic metadata."""
    song_data = YTM.get_song(id)['videoDetails']
    local_song = Song
    local_song.yt_id = id
    local_song.artist = song_data['author']
    local_song.name = song_data['title']
    local_song.duration_s = int(song_data['lengthSeconds'])
    local_song.yt_id = song_data['videoId']
    if id != local_song.yt_id:
        print("Song \"" + local_song.name + "\" returned a different id (" + local_song.yt_id + ") than the one used to look it up (" + id + ").  Ignoring the returned id.  ")
    return local_song

def gather_song_metadata(song: Song):
    """Takes a Song with basic metadata and uses Spotify Track Features API to fill in extended musical metadata"""

    # Make an initial search term
    initial_query_string = ""
    if song.name is None or song.artist is None:
        print("Not sure how to search Spotify for song \"" + str(song.name) "\" (YouTube ID " + str(song.yt_id) + ").")
        user_search_string = input('Search Spotify for: ')
    else:
        initial_query_string = query_string = song.name + " " + song.artist

    # Allow retrying search until results found (or search options are exhausted)
    strict_time_matching = True
    target_song = None
    while True:
        pace_ops()
        search_results = SP.search(query_string, type='track')

        # Results were returned, check them
        if search_results and len(search_results['tracks']['items']) > 0:
            # Check that the Spotify song is about the same duration as the YTM version
            if strict_time_matching:
                for candidate_song in search_results['tracks']['items']:
                    time_difference_s = candidate_song['duration_ms']/1000 - song.duration_s
                    if abs(time_difference_s) <= 3:
                        target_song = candidate_song
                        song.metadata_needs_review = False
                        break
            # User has disabled duration checking, just take the first song and notify them
            else:
                candidate_song = search_results['tracks']['items'][0]
                time_difference_s = candidate_song['duration_ms']/1000 - song.duration_s
                print("Choosing first search result, which is " + str(abs(time_difference_s)) + " seconds " + ("longer" if time_difference_s > 0 else "shorter") + ".")
                target_song = search_results['tracks']['items'][0]
                song.metadata_needs_review = True
                break

        # No song found even with loose time matching, abort
        elif not strict_time_matching:
            break

        # Target song found, break out of loop
        if target_song:
            break

        # If the initial search didn't match, try search without "feat." in the middle
        if strict_time_matching and query_string == initial_query_string:
            query_string = re.sub('( \(\s*feat.+\))', '', query_string, flags=re.IGNORECASE)
            # There was a "feat" to reove in the search string, so we'll retry the search
            if query_string != initial_query_string:
                continue

        # Song not found, prompt user to modify search query
        print("No suitable Spotify results found for search \"" + query_string + "\".  Type a new search query, or enter nothing to do a loose search and give up if there are still no matches.")
        user_search_string = input('Search Spotify for: ')
        # User had blank input; disable duration matching
        if len(user_search_string) < 1:
            strict_time_matching = False
        else:
            query_string = user_search_string

    # No song was found, can't look up data.  Warn user and flag song.  
    if target_song is None:
        print("Could not get Spotify info for " + initial_query_string + ".  The rater-application will prompt you for info.")
        song.metadata_needs_review = True

    # Song was found.  Look up its "features" and process them before saving song to playlist.
    else:
        song.spotify_id = target_song['id']
        pace_ops()
        features = SP.audio_features(tracks=[song.spotify_id])[0]

        song.bpm = features['tempo']

        # Validate and convert Spotify pitch class numbers mapped to camelot wheel numbers 
        # Camelot position numbers are in tuple of (position for major, position for minor)
        camelot_lookup = {
            0: (8, 5),
            1: (3, 12),
            2: (10, 7),
            3: (5, 2),
            4: (12, 9),
            5: (7, 4), 
            6: (2, 11),
            7: (9, 6),
            8: (4, 1),
            9: (11, 8),
            10: (6, 3),
            11: (1, 10)
        }
        if features['key'] == -1:
            print("Spotify does not know the key of " + initial_query_string)
            song.metadata_needs_review = True
        else:
            if features['mode'] == 1:
                song.camelot_position, _ = camelot_lookup[features['key']]
                song.camelot_is_minor = False
            else:
                _, song.camelot_position = camelot_lookup[features['key']]
                song.camelot_is_minor = True
            if song.metadata_needs_review is None:
                song.metadata_needs_review = False

    return song

def load_local_playlists(path = '.'):
    """Loads local playlist files into a dict (keyed by YT id) and returns it.  
    Also returns dict of songs by YT id.  Takes optional path argument or just seaches current directory."""

    print("Loading songs database and playlist files from " + path + ".  You may be prompted to correct errors.  ")

    # Load songs db, checking for backup in case save was interrupted
    all_songs = {}
    if os.path.exists(SONG_DB_FILE + '.bak'):
        if get_user_bool("Songs database backup detected; last save may have failed.  Replace the primary copy with the backup?  "):
            os.rename(SONG_DB_FILE + '.bak', SONG_DB_FILE)
        else:
            os.remove(SONG_DB_FILE + '.bak')
        songs_file = open(SONG_DB_FILE, "rb")
        all_songs = pickle.load(songs_file)
        songs_file.close()

    # Load playlist files
    playlist_files = glob.glob(PLAYLIST_FILE_PREFIX + '*' + PLAYLIST_FILE_EXTENSION, dir_fd=glob.glob(path))
    saved_playlists = {}
    for playlist_file_name in playlist_files:
        playlist_file = open(playlist_file_name, "rb")
        playlist = pickle.load(playlist_file)
        playlist_file.close()
        saved_playlists[playlist.yt_id] = playlist

        # Check if any songs are not in database and download them
        missing_metadata_count = 0
        for song_id in playlist.songs_ids:
            if song_id not in all_songs:
                missing_metadata_count = missing_metadata_count + 1
                if missing_metadata_count % 10 == 0:
                    print("Correcting metadata for " + str(missing_metadata_count) + "th song.  ")
                missing_song = download_metadata(song_id)
                gather_song_metadata(missing_song)
                all_songs[song_id] = missing_song
        if missing_metadata_count > 0:
            print("Downloaded " + str(missing_metadata_count) + " songs that had no data while loading playlist \"" + playlist.name + "\".  ")

    return saved_playlists, all_songs
