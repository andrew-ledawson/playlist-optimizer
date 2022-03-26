from ytmusicapi import YTMusic
import pickle, spotipy, time
from spotipy.oauth2 import SpotifyOAuth

class Playlist:
    name = ""
    songs = []
    yt_id = ""

class Song:
    album = ""
    artist = ""
    name = ""
    duration_s = 0
    yt_id = ""
    spotify_id = ""
    camelot_position = ""
    camelot_is_minor = None
    bpm = 0

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

# Auth YouTube Music and Spotify
print("Launching playlist collector")
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

# Get playlists from YouTube Music
pace_ops()
ytm_playlists = ytmusic.get_library_playlists()
print("Checking your saved YTM playlists")
for candidate_playlist in ytm_playlists:
    playlist_author = candidate_playlist.get('author', [{}])[0].get('name', '')
    # Omit playlists by other users or YTM themselves
    if playlist_author == 'Andrew LD':
        print("Found your playlist " + candidate_playlist['title'])
        # Get songs of each playlist
        pace_ops()
        playlist_contents = ytmusic.get_playlist(playlistId=candidate_playlist['playlistId'], limit=1000)

        local_playlist = Playlist
        local_playlist.name = candidate_playlist['title']
        local_playlist.yt_id = candidate_playlist['playlistId']

        # Store song info in a Song object
        for song_count, playlist_song in enumerate(playlist_contents['tracks']):
            if song_count % 10 == 0:
                print("Checking song " + str(song_count) + " of " + str(len(playlist_contents['tracks'])))
            local_song = Song
            local_song.album = playlist_song['album']
            local_song.artist = playlist_song['artists'][0]['name']
            local_song.name = playlist_song['title']
            # Convert song duration to number of seconds
            time_strings = playlist_song['duration'].split(':')
            local_song.duration_s = 60 * int(time_strings[0]) + int(time_strings[1])
            local_song.yt_id = playlist_song['videoId']

            # Get additional song info from Spotify
            # Search Spotify for the song so we can then look up its "features"
            initial_query_string = query_string = local_song.name + " " + local_song.artist
            strict_time_matching = True
            search_results=[]
            target_song = None
            while True:
                # TODO: if search fails, dump first set of parens with "feat" inside them
                pace_ops()
                search_results = sp.search(query_string, type='track')
                if search_results and len(search_results['tracks']['items']) > 0: # At least one song found
                    if strict_time_matching: # Validate song length against YTM
                        for candidate_song in search_results['tracks']['items']:
                            time_difference_s = candidate_song['duration_ms']/1000 - local_song.duration_s
                            if abs(time_difference_s) <= 3:
                                target_song = candidate_song
                                break
                    else:
                        time_difference_s = candidate_song['duration_ms']/1000 - local_song.duration_s
                        print("Choosing first search result that is " + str(time_difference_s) + " seconds longer.")
                        target_song = search_results['tracks']['items'][0]
                        break
                # No song found even with loose time matching, abort
                elif not strict_time_matching:
                    break
                # Target song found, break out of loop
                if target_song:
                    break
                # Song not found, prompt to modify search query and retry
                print("No suitable Spotify results found for search \"" + query_string + "\".  Type a new search query, or enter nothing to do a loose search and give up if there are still no matches.")
                user_search_string = input('Search Spotify for: ')
                if len(user_search_string) < 1:
                    strict_time_matching = False
                else:
                    query_string = user_search_string
            if target_song is None:
                print("Could not get Spotify info for " + initial_query_string + ".  The rater-application will prompt you for info.")
                break
            song_spotify_id = target_song['id']

            # Get song "features"
            pace_ops()
            features = sp.audio_features(tracks=[song_spotify_id])[0]
            local_song.bpm = features['tempo']

            # Validate and convert song key
            if features['key'] == -1:
                print("Spotify does not know the key of " + initial_query_string)
            else:
                if features['mode'] == 1:
                    local_song.camelot_position, _ = camelot_lookup[features['key']]
                    local_song.camelot_is_minor = False
                else:
                    _, local_song.camelot_position = camelot_lookup[features['key']]
                    local_song.camelot_is_minor = True

            # Save song to playlist
            local_playlist.songs.append(local_song)

        # Store playlist info
        pickle.dump(local_playlist, open("playlists/" + local_playlist.yt_id+ "pp1", "wb"))