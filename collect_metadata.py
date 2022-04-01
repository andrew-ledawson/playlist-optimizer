import glob, pickle, re, sys, time

from ytmusicapi import YTMusic
import spotipy
from spotipy.oauth2 import SpotifyOAuth

from foundation import *

# A dict with keys of pitch class numbers and values of camelot wheel (major, minor) tuples
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

# Launch and auth YouTube Music and Spotify
print("Launching playlist collector")

MIN_PYTHON = (3, 6)
if sys.version_info < MIN_PYTHON:
    sys.exit("Python %s.%s or later is required.\n" % MIN_PYTHON)

ytmusic = YTMusic('headers_auth.json')
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="CLIENT_ID",
                                               client_secret="CLIENT_SECRET",
                                               redirect_uri="http://www.example.com/",
                                               scope="user-library-read"))

# Note when last query was and pace ourselves accordingly
last_op_time = time.time()
def pace_ops():
    global last_op_time
    remaining_time = (last_op_time + 1) - time.time()
    if remaining_time > 0:
        time.sleep(remaining_time)
    last_op_time = time.time()

# Check which playlists are already saved
playlist_files = glob.glob('playlist_*.pp1', dir_fd=glob.glob('.'))
saved_playlists = {}
for playlist_file_name in playlist_files:
    playlist_file = open(playlist_file_name, "rb")
    playlist = pickle.load(playlist_file)
    playlist_file.close()
    saved_playlists[playlist.yt_id] = playlist
# TODO: Keep a dict of all songs by YTM-id so we can avoid duplicate metadata lookups?

# Go through each user playlist on YouTube Music
pace_ops()
ytm_playlists = ytmusic.get_library_playlists()
print("Checking your saved YTM playlists")
for candidate_playlist in ytm_playlists:
    local_playlist = Playlist
    local_playlist.name = candidate_playlist['title']
    local_playlist.yt_id = candidate_playlist['playlistId']
    local_playlist_author = candidate_playlist.get('author', [{}])[0].get('name', '')
    local_playlist_song_count = candidate_playlist['count']

    # Check if playlist is already downloaded and prompt to update it
    if local_playlist.yt_id in saved_playlists.keys:
        user_input = ""
        while user_input != 'y' and user_input != 'n':
            user_input = input("Playlist \"" + local_playlist.name + "\" was already downloaded.  Update?  (y/n)")
        if user_input == 'n':
            continue
        else:
            local_playlist = saved_playlists[local_playlist.yt_id]

    # Omit playlists by other users or YTM themselves
    if local_playlist_author == 'Andrew LD':
        print("Found your playlist " + candidate_playlist['title'])
        # Get songs of each playlist
        pace_ops()
        remote_playlist_contents = ytmusic.get_playlist(playlistId=local_playlist.yt_id, limit=local_playlist_song_count + 1)

        # Store song info in a Song object
        for song_count, playlist_song in enumerate(remote_playlist_contents['tracks']):
            # 
            # Print update every 10 songs
            if song_count % 10 == 0:
                print("Checking song " + str(song_count) + " of " + str(len(remote_playlist_contents['tracks'])))

            local_song = Song
            local_song.album = playlist_song['album']
            local_song.artist = playlist_song['artists'][0]['name']
            local_song.name = playlist_song['title']
            # Convert song duration to number of seconds
            time_strings = playlist_song['duration'].split(':')
            local_song.duration_s = 60 * int(time_strings[0]) + int(time_strings[1])
            local_song.yt_id = playlist_song['videoId']

            # Don't update songs that were already seen
            if local_song.yt_id in local_playlist.songs.keys:
                continue

            # Search Spotify for each song so we can then look up its "features"
            initial_query_string = query_string = local_song.name + " " + local_song.artist
            strict_time_matching = True
            search_results=[]
            target_song = None
            while True:
                pace_ops()
                search_results = sp.search(query_string, type='track')

                # Results were returned, check them
                if search_results and len(search_results['tracks']['items']) > 0:
                    # Check that the Spotify song is about the same duration as the YTM version
                    if strict_time_matching:
                        for candidate_song in search_results['tracks']['items']:
                            time_difference_s = candidate_song['duration_ms']/1000 - local_song.duration_s
                            if abs(time_difference_s) <= 3:
                                target_song = candidate_song
                                local_song.metadata_needs_review = False
                                break
                    # User has disabled duration checking, just take the first song and notify them
                    else:
                        candidate_song = search_results['tracks']['items'][0]
                        time_difference_s = candidate_song['duration_ms']/1000 - local_song.duration_s
                        print("Choosing first search result, which is " + str(abs(time_difference_s)) + " seconds " + ("longer" if time_difference_s > 0 else "shorter") + ".")
                        target_song = search_results['tracks']['items'][0]
                        local_song.metadata_needs_review = True
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
                # TODO: LD got "Nonetype" once for initial query so I'll wrap it in a string modifier?
                print("Could not get Spotify info for " + initial_query_string + ".  The rater-application will prompt you for info.")
                local_song.metadata_needs_review = True

            # Song was found.  Look up its "features" and process them before saving song to playlist.
            else:
                local_song.spotify_id = target_song['id']
                pace_ops()
                features = sp.audio_features(tracks=[local_song.spotify_id])[0]

                local_song.bpm = features['tempo']

                # Validate and convert song key
                if features['key'] == -1:
                    print("Spotify does not know the key of " + initial_query_string)
                    local_song.metadata_needs_review = True
                else:
                    if features['mode'] == 1:
                        local_song.camelot_position, _ = camelot_lookup[features['key']]
                        local_song.camelot_is_minor = False
                    else:
                        _, local_song.camelot_position = camelot_lookup[features['key']]
                        local_song.camelot_is_minor = True
                    if local_song.metadata_needs_review is None:
                        local_song.metadata_needs_review = False

            # Save song to playlist
            local_playlist.songs[local_song.yt_id] = local_song

        # Store playlist as a file
        playlist_file = open("playlist_" + local_playlist.yt_id+ ".pp1", "wb")
        pickle.dump(local_playlist, playlist_file)
        playlist_file.close()