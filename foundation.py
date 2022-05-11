# Basic Python imports
import glob, pickle, os, re, sys, time
from functools import total_ordering
from typing import Callable

# Library imports for API access
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic

"""
Global variables and init functions
"""

# A dictionary of user-ratable traits for each song, where each key is a trait/category
# and each value is an explanation.  Capitalize strings correctly for UI display.  
# Can be updated by adding new rating fields and/or moving out deprecated fields.  
# Ratings are presumed to go from +2 (strongly matches category) to -2 (extreme opposite of category)
USER_RATINGS = {'Positivity' : 'Hopeful and optimistic, or regretful and pessimistic.',
                'Drive' : 'Driving and forceful, or unhurried and gentle.',
                'Presence' : 'Captivating and focused, or detached and distant.',
                'Complexity' : 'Crowded and busy, or simple and manageable.'}

# Deprecated ratings can be moved here so program will prompt users to re-rate accordingly
DEPRECATED_RATINGS = {}

# Maximum different in time between YouTube Music and Spotify.
# Keep in mind that YouTube music durations are in seconds and Spotify is accurate to milliseconds.  
MAX_SONG_TIME_DIFFERENCE = 2

# File names and extensions
PLAYLIST_FILE_PREFIX = 'playlist_'
PLAYLIST_FILE_EXTENSION = '.ytp'
SONG_DB_FILE = 'songs.yts'

# Constants for logic
CAMELOT_POSITIONS = 12

# Check Python version on init because this uses ordered dicts
MIN_PYTHON = (3, 6)
if sys.version_info < MIN_PYTHON:
    sys.exit("Python %s.%s or later is required.\n" % MIN_PYTHON)

print("Starting playlist optimizer libraries and foundation functions.")

# Init YouTube Music and Spotify API libraries
YTM = YTMusic('headers_auth.json')
SP = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="CLIENT_ID",
                                               client_secret="CLIENT_SECRET",
                                               redirect_uri="http://www.example.com/",
                                               scope="user-library-read"))

# Variables and function to ensure API calls avoid rate limiting
LAST_OP_TIME = time.time()
TIME_BETWEEN_OPS = DEFAULT_TIME_BETWEEN_OPS = 1
OPS_SINCE_BACKOFF = 0
OPS_TO_RESTORE_BACKOFF = 20
MAX_TIME_MULTIPLIER = 32
def run_API_request(operation : Callable, description="an unknown web request"):
    """Runs a lamba (presumably containing an API call) and returns its result.
       Keeps a rate limit and backs off upon exceptions."""
    global LAST_OP_TIME, TIME_BETWEEN_OPS, OPS_SINCE_BACKOFF, DEFAULT_TIME_BETWEEN_OPS, OPS_TO_RESTORE_BACKOFF, MAX_TIME_MULTIPLIER

    # Check if it's safe to try faster requests
    if TIME_BETWEEN_OPS != DEFAULT_TIME_BETWEEN_OPS and OPS_SINCE_BACKOFF > OPS_TO_RESTORE_BACKOFF:
        TIME_BETWEEN_OPS = TIME_BETWEEN_OPS / 2
        OPS_SINCE_BACKOFF = 0

    # Run the operation, retrying on exceptions
    result = None
    while result is None:
        try:
            remaining_time = (LAST_OP_TIME + TIME_BETWEEN_OPS) - time.time()
            if remaining_time > 0:
                time.sleep(remaining_time)
            result = operation()
            OPS_SINCE_BACKOFF = OPS_SINCE_BACKOFF + 1
        except:
            if TIME_BETWEEN_OPS == DEFAULT_TIME_BETWEEN_OPS * MAX_TIME_MULTIPLIER:
                break
            OPS_SINCE_BACKOFF = 0
            print("Error found while attempting " + description + ". Temporarily spacing out requests by " + str(TIME_BETWEEN_OPS) + " seconds... ")
    if result is None:
        print("Exceeded retries. Continuing... ")
    LAST_OP_TIME = time.time()
    return result

"""
Global classes
"""

class Playlist:
    """A YouTube Music playlist containing songs"""
    name = None
    song_ids = None # list of strs
    yt_id = None

@total_ordering
class Song:
    """A song (presumably shared between YouTube Music and Spotify)"""
    # Members are referenced by strings in dict metadata_fields in download_song_features()
    # so update that when changing member names
    album = None
    artist = None
    name = None
    duration_s = None # integer

    yt_id = None
    spotify_id = None
    spotify_preview_url = None
    # None if not downloaded, false if all downloaded, true if downloaded with error
    metadata_needs_review = None
    is_private = None

    camelot_position = None
    camelot_is_minor = None
    bpm = None

    user_ratings = dict()

    def has_latest_ratings(self):
        global USER_RATINGS
        for trait in USER_RATINGS:
            if trait not in self.user_ratings or self.user_ratings[trait] == None:
                return False
        return True

    def set_bpm(self, bpm : float):
        if bpm is not None:
            assert bpm is None or bpm > 0, "BPM must be a positive value"
            # Keep BPM consistent between 90 and 180
            while bpm < 90:
                bpm = bpm * 2
            while bpm >= 180:
                bpm = bpm / 2
        self.bpm = bpm

    def set_camelot_position(self, camelot_position : int):
        assert camelot_position is None or 1 <= camelot_position <= CAMELOT_POSITIONS, "Camelot wheel position is invalid"
        self.camelot_position = camelot_position

    def set_user_rating(self, rating_name : str, rating_number : int):
        assert rating_number is None or -2 <= rating_number <= 2, "Rating is not between -2 and +2"
        self.user_ratings[rating_name] = rating_number

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
            for rating_name in USER_RATINGS:
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
        #basic_fields.remove('owning_playlists')
        for member_name in basic_fields:
            if getattr(self, member_name) != getattr(other, member_name):
                return False
    
        # Check user ratings, ignoring deprecated ratings
        for rating_name in USER_RATINGS:
            if (rating_name in self.user_ratings != rating_name in other.user_ratings) or (self.user_ratings[rating_name] != other.user_ratings[rating_name]):
                return False

        # Ignore owning playlists since that just relates to 
        return True

"""
Global funtions
"""

def prompt_user_for_bool(message:str, allow_no_response = False) -> bool:
    """Prompts the user to respond to a message with 'y' or 'n', or optionally no response"""
    user_input = None
    input_options_string = "[y]es/[n]o/[empty]" if allow_no_response else "[y]es/[n]o"
    while user_input != 'y' and user_input != 'n' and not (allow_no_response and user_input == ""):
        user_input = input(message + "(" + input_options_string + "): ")
    return user_input == 'y'

def download_metadata_from_YT_id(id:str) -> Song:
    """Takes a YouTube song ID and gets basic metadata (using a direct lookup endpoint). 
       This endpoint returns different data than the playlist songs endpoint."""
    song_data = run_API_request(lambda : YTM.get_song(id)['videoDetails'], "to look up metadata for YouTube song " + id)
    local_song = Song()
    local_song.yt_id = id
    local_song.artist = song_data['author']
    local_song.name = song_data['title']
    local_song.duration_s = int(song_data['lengthSeconds'])
    local_song.is_private = song_data['isPrivate']
    if id != song_data['videoId']:
        print("Song \"" + local_song.name + "\" returned a different id (" + local_song.yt_id + ") than the one used to look it up (" + id + "). Ignoring the returned id. ")
    return local_song

# TODO later: Break into multiple functions
def process_song_metadata(song:Song, search_spotify:bool, edit_metadata:bool, get_features:bool) -> Song:
    """Takes a Song and expands its metadata with Spotify song search, Spotify Track Features API, and/or manual user input."""
    # A Spotify song ID is necessary for their features API
    assert search_spotify or not get_features, "Can't get song features without searching Spotify"

    matching_spotify_song = None
    if search_spotify:
        # Make an initial search term
        initial_spotify_search_str = ""
        if song.name is None or song.artist is None:
            print("Not sure how to search Spotify for song \"" + str(song.name) + "\" (YouTube ID " + str(song.yt_id) + "). ")
            initial_spotify_search_str = input('Search Spotify for: ')
        else:
            initial_spotify_search_str = query_string = song.name + " " + song.artist

        # Retry search until results are found (or search options are exhausted)
        strict_time_matching = True
        user_search_string = "" 
        while True:
            search_results = run_API_request(lambda : SP.search(query_string, type='track'), "a Spotify search")

            # Results were returned, check them
            if search_results and len(search_results['tracks']['items']) > 0:
                # Check that the Spotify song is about the same duration as the YTM version
                if strict_time_matching:
                    for candidate_song in search_results['tracks']['items']:
                        time_difference_s = (float(candidate_song['duration_ms'])/1000) - float(song.duration_s)
                        if abs(time_difference_s) <= MAX_SONG_TIME_DIFFERENCE:
                            matching_spotify_song = candidate_song
                            song.metadata_needs_review = False
                            break
                # User has disabled duration checking, just take the first song and notify them
                else:
                    candidate_song = search_results['tracks']['items'][0]
                    time_difference_s = candidate_song['duration_ms']/1000 - song.duration_s
                    print("Selected the first search result, which is " + str(int(abs(time_difference_s))) + " seconds " + ("longer" if time_difference_s > 0 else "shorter") + ". ")
                    matching_spotify_song = search_results['tracks']['items'][0]
                    song.metadata_needs_review = True
                    break

            # No song found even with loose time matching, stop searching
            elif not strict_time_matching:
                break

            # Target song found, stop searching
            if matching_spotify_song:
                if user_search_string != "":
                    print("Found a matching song. ")
                break

            # If the initial search didn't match, try search without "feat." in the track name
            # because Spotify doesn't seem to like that
            if strict_time_matching and query_string == initial_spotify_search_str:
                query_string = re.sub('( \(\s*feat.+\))', '', query_string, flags=re.IGNORECASE)
                # There was a "feat" to reove in the search string, so we'll retry the search
                if query_string != initial_spotify_search_str:
                    continue

            # Song not found, prompt user to modify search query
            print("No song of matching length was found for the Spotify search \"" + query_string + "\". Try a new search query, or enter nothing to do a final retry without trying to match song length. ")
            user_search_string = input('Search Spotify for: ')
            # User had blank input; disable duration matching
            if len(user_search_string) < 1:
                strict_time_matching = False
            else:
                query_string = user_search_string

        # No song was found; can't look up data. Warn user and flag song.  
        if matching_spotify_song is None:
            print("Search still had no results; leaving song metadata empty. ")
            song.metadata_needs_review = True

        # Song was found.  Look up its "features" and process them before saving song to playlist.
        else:
            song.spotify_preview_url = matching_spotify_song['preview_url']
            song.spotify_id = matching_spotify_song['id']
            # Fill album name from Spotify if YTM alt endpoint was used
            if song.album is None:
                song.album = matching_spotify_song['album']['name']

            if get_features:
                features = run_API_request(lambda : SP.audio_features(tracks=[song.spotify_id])[0], "to look up Spotify musical features for track ID " + song.spotify_id)

                song.set_bpm(float(features['tempo']))

                # Validate Spotify pitch class then convert to camelot wheel position number 
                # Camelot position numbers are in tuples (position for major key, position for minor key)
                camelot_lookup = {
                    0: (8, 5),
                    1: (3, 12),
                    2: (10, 7),
                    3: (5, 2),
                    4: (12, 9),
                    5: (7, 4), 
                5: (7, 4), 
                    5: (7, 4), 
                    6: (2, 11),
                    7: (9, 6),
                    8: (4, 1),
                    9: (11, 8),
                    10: (6, 3),
                    11: (1, 10)
                }
                if features['key'] == -1:
                    print("Spotify omitted the musical key for " + initial_spotify_search_str)
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

    # Metadata editor that can compare to metadata retrieved from Spotify
    if edit_metadata:
        # List of dicts containing song metadata fields, list of Song object sub-members, and list of Spotpy sub-dict keys
        song_metadata_fields = [{'field_name':'Song name', 'yt_fields':['name'], 'sp_fields':['name'], 'type':str, 'setter':None},
                                {'field_name':'Song artist', 'yt_fields':['artist'], 'sp_fields':['artists', 0, 'name'], 'type':str, 'setter':None},
                                {'field_name':'Song album', 'yt_fields':['album'], 'sp_fields':['album', 'name'], 'type':str, 'setter':None},
                                {'field_name':'Song BPM (decimal)', 'yt_fields':['bpm'], 'sp_fields':None, 'type':float, 'setter':"set_bpm"},
                                {'field_name':'Song key (Camelot wheel position number)', 'yt_fields':['camelot_position'], 'sp_fields':None, 'type':int, 'setter':None},
                                {'field_name':'Song is in minor key', 'yt_fields':['camelot_is_minor'], 'sp_fields':None, 'type':bool, 'setter':None}]

        # Add possible user ratings to fields-dict
        # TODO later: make song an argument into the lambda so we can set up the fields dict on program init
        for rating_name in USER_RATINGS:
            # Create a lambda to set rating for the current song
            # Lambda needs a fake rating_name argument so that it can capture the current state
            # Note: can't switch to copy.deepcopy() because lambdas are stateless/un-copy-able
            setter = lambda rating_number, rating_name=rating_name : song.set_user_rating(rating_name, rating_number)
            song_metadata_fields.append({'field_name':rating_name + " rating", 'yt_fields':['user_ratings', rating_name], 'sp_fields':None, 'type':int, 'setter':setter})

        def get_field(current_object, subfield_list:list, hide_empty=True):
            """Takes a dict or object and a list of strings, then iterates to get the desired subfield."""
            for field_name in subfield_list:
                if current_object is None:
                    break
                try:
                    current_object = getattr(current_object, field_name)
                except (AttributeError, TypeError, KeyError):
                    try: 
                        current_object = current_object[field_name]
                    except (AttributeError, TypeError, KeyError):
                        current_object = None
                        break
            # Empty strings, dicts, and the like will be treated like they are unset
            try:
                if hide_empty and len(current_object) == 0:
                    current_object = None
            except:
                pass
            return current_object

        def set_song_field(song:Song, field_setter_func, new_field_data, yt_field_list:list):
            if type(field_setter_func) == str:
                # Get and execute the setter func from the song class
                getattr(song, field_setter_func)(new_field_data)
            elif field_setter_func is not None:
                # Execute lambda
                field_setter_func(new_field_data)
            else:
                # No setter func, so get the parent and set its child value
                fields_to_parent = [yt_field_list[field_num] for field_num in range(len(yt_field_list) - 1)]
                parent_of_target = get_field(song, fields_to_parent, hide_empty=False)
                setattr(parent_of_target, fields_to_parent[-1], new_field_data)

        def print_song_metadata(song:Song, matching_spotify_song:dict):
            print("Printing metadata to check. Type a field number and [s]potify's data, or [m]anual input. Or [p]rint this metadata/help again, save and [c]ontinue to next song/operation, or [a]bort all operations. \n" +\
              "For example, \"1s\" selects Spotify's song name. The \"review needed\" flag is cleared upon exit unless you set it with [f]lag. \n" +\
              "You can [a]bort all operations to exit, but changes will still be saved (flag will be left intact). ")
            for field_number, fields_dict in enumerate(song_metadata_fields):
                field_name = fields_dict["field_name"]
                field_setter_func = fields_dict['setter']
                yt_field_list = fields_dict["yt_fields"]
                sp_field_list = fields_dict["sp_fields"]

                # Check which fields are available to compare
                yt_field = None
                if yt_field_list is not None:
                    yt_field = get_field(song, yt_field_list)

                sp_field = None
                if sp_field_list is not None and matching_spotify_song is not None:
                    sp_field = get_field(matching_spotify_song, sp_field_list)

                # Determine which field(s) are available and print the appropriate hint
                if yt_field is None:
                    if sp_field is None:
                        # Neither field available
                        field_to_print = "(Unset, [m]anually input)"
                    else:
                        # Only Spotify available
                        field_to_print = sp_field + " ([s]potify)"
                elif sp_field is not None and yt_field != sp_field:
                    # Both fields avaialable
                    field_to_print = yt_field + " (current data) or " + sp_field + " (from [s]potify)"
                else:
                    # Only current (YTM) available
                    field_to_print = str(yt_field) + " (current data)"
                print(str(field_number + 1) + ". " + field_name + ": " + field_to_print)

        print_song_metadata(song, matching_spotify_song)

        # Check fields for empty strings and replace them with None since they're effectively unset
        for selected_field_number, fields_dict in enumerate(song_metadata_fields):
            if fields_dict['type'] is str:
                yt_field_list = fields_dict["yt_fields"]
                field_setter_func = fields_dict['setter']

                # Check which fields are available to compare
                yt_field = None
                if yt_field_list is not None:
                    yt_field = get_field(song, yt_field_list, hide_empty=False)
                if yt_field == "":
                    if field_setter_func is not None:
                        # Get and execute the setter func
                        getattr(song, field_setter_func)(None)
                    else:
                        # No setter func, so just directly set
                        setattr(song, yt_field_list[0], None)

        # Take edit actions from user
        override_flag = False
        while True:
            user_input = input('Input an action such as [p]rint metadata/help, save and [c]ontinue, or [a]bort all operations: ')
            
            # "Save" and exit
            if user_input == 'c':
                if not override_flag:
                    song.metadata_needs_review = False
                break

            # Keep flag set (or set flag for later)
            elif user_input == 'f':
                override_flag = True
                song.metadata_needs_review = True
                print("Flag set. ")
                continue

            # Abort and immediately exit
            elif user_input == 'a':
                return None

            # Print metadata
            elif user_input == 'p':
                print_song_metadata(song, matching_spotify_song)

            # User must be commanding an edit
            else:
                selected_field_number = None
                try:
                    selected_field_number = int(user_input[0:-1]) - 1
                    selected_field_action = user_input[-1]
                    assert selected_field_action in ['s', 'm']
                except (AssertionError, ValueError):
                    print("Invalid command, try again? ")
                    continue
                if selected_field_number >= 0 and selected_field_number < len(song_metadata_fields):
                    fields_dict = song_metadata_fields[selected_field_number]
                    field_name = fields_dict["field_name"]
                    yt_field_list = fields_dict["yt_fields"]
                    sp_field_list = fields_dict["sp_fields"]
                    field_type = fields_dict['type']
                    field_setter_func = fields_dict['setter']

                    # Determine what field data the user prefers
                    new_field_data = None

                    # User selected Spotify data
                    if selected_field_action == 's':
                        new_field_data = get_field(matching_spotify_song, sp_field_list)

                    # User selected manual input
                    elif selected_field_action == 'm':
                        new_field_data = None
                        if field_type == bool:
                            new_field_data = prompt_user_for_bool(field_name + " ", True)
                        else:
                            # Keep prompting the user for input until it is valid
                            while True:
                                new_field_data = input(field_name + ": ")

                                # Empty string means no data, which we support as "None"
                                if new_field_data == '':
                                    new_field_data = None
                                    break

                                # Convert input if necessary
                                if field_type == float:
                                    try:
                                        new_field_data = float(new_field_data)
                                        break
                                    except ValueError:
                                        continue
                                elif field_type == int:
                                    try:
                                        new_field_data = int(new_field_data)
                                        break
                                    except ValueError:
                                        continue
                                else:
                                    break

                    set_song_field(song, field_setter_func, new_field_data, yt_field_list)

    return song

def load_data_files(path = '.') -> tuple[dict[str, Playlist], dict[str, Song]]:
    """Loads local playlist files into a dict (keyed by YT id) and returns it.  
    Also returns dict of songs by YT id.  Takes optional path argument or just seaches current directory."""

    print("Loading songs database and playlist files from folder \"" + path + "\". You may be prompted to correct errors. ")

    # Load songs db, checking for backup in case save was interrupted
    songs_db = dict()
    if os.path.exists(SONG_DB_FILE + '.bak'):
        print("Songs database backup detected; last save may have failed.")
        if prompt_user_for_bool("Replace the primary copy with the backup? "):
            os.rename(SONG_DB_FILE + '.bak', SONG_DB_FILE)
        else:
            os.remove(SONG_DB_FILE + '.bak')
    if os.path.exists(SONG_DB_FILE):
        songs_file = open(SONG_DB_FILE, "rb")
        songs_db = pickle.load(songs_file)
        songs_file.close()

    # Load playlist files
    # TODO later: switch from glob to os to reduce imports
    playlist_files = glob.glob(PLAYLIST_FILE_PREFIX + '*' + PLAYLIST_FILE_EXTENSION, dir_fd=glob.glob(path)[0])
    playlists_db = dict()
    for playlist_file_name in playlist_files:
        playlist_file = open(playlist_file_name, "rb")
        playlist = pickle.load(playlist_file)
        playlist_file.close()
        playlists_db[playlist.yt_id] = playlist

        # Check if any songs are not in database and download them
        missing_metadata_count = 0
        if playlist.song_ids is None:
            print("Warning: playlist ID " + playlist.yt_id + " seems empty and should be redownloaded. ")
        for song_id in playlist.song_ids:
            if song_id not in songs_db:
                # Print update every 10 retrievals since they take a while
                if missing_metadata_count % 10 == 9:
                    print("Correcting metadata for " + str(missing_metadata_count + 1) + "th song. ")
                songs_db[song_id] = process_song_metadata(song=download_metadata_from_YT_id(song_id), search_spotify=True, edit_metadata=True, get_features=True)
                songs_db[song_id].yt_id = songs_db[song_id] # Don't use alternative ID
                missing_metadata_count = missing_metadata_count + 1
        if missing_metadata_count > 0:
            print("Updated " + str(missing_metadata_count) + " songs that had no data while loading playlist \"" + playlist.name + "\". Note that album names cannot be loaded. ")

    print("Loaded " + str(len(playlists_db.keys())) + " saved playlists and " + str(len(songs_db.keys())) + " songs. ")
    return playlists_db, songs_db

def write_song_db(all_songs : dict[str, Song]):
    """Save song database, moving old copy to backup location in case saving is interrupted."""
    if os.path.exists(SONG_DB_FILE):
        os.rename(SONG_DB_FILE, SONG_DB_FILE + '.bak')
    songs_file = open(SONG_DB_FILE, "wb")
    pickle.dump(all_songs, songs_file)
    songs_file.close()
    if os.path.exists(SONG_DB_FILE + '.bak'):
        os.remove(SONG_DB_FILE + '.bak')

def cleanup_songs_db(songs_db : dict[str, Song], playlists_db : dict[str, Playlist]):
    """Checks and offers to remove songs in database not used by any playlist."""
    unseen_songs = [song_id for song_id in songs_db]
    for playlist in playlists_db.values():
        for song_id in playlist.song_ids:
            try:
                unseen_songs.remove(song_id)
            except:
                pass
    if len(unseen_songs) > 0:
        print(str(len(unseen_songs)) + " songs in the database are not used by a playlist. ")
        if prompt_user_for_bool("Remove them? "):
            for song_id in unseen_songs:
                songs_db.pop(song_id)
    return songs_db

def prompt_for_playlist(playlists_db : dict[str, Playlist], prompt_message : str = "Pick a playlist or enter nothing for all songs: ") -> list[str]:
    """Prompts user to select playlists from the given dict. Allows user to select none to load all songs."""
    print(prompt_message)
    for number, playlist in enumerate(list(playlists_db.values())):
        print(str(number + 1) + ": " + playlist.name)
    selected_song_ids = list()
    selection = input("Playlist: ")
    if selection == "":
        selected_song_ids = None
    else:
        selected_playlist = list(playlists_db.values())[int(selection) - 1]
        selected_song_ids = selected_playlist.song_ids
    return selected_song_ids

if not prompt_user_for_bool(message="Okay to access Spotify API and YouTube Music browser API using supplied credentials? ", allow_no_response=False):
    sys.exit("Aborting launch.\n")
