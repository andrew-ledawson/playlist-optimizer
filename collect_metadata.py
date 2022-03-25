from ytmusicapi import YTMusic
import pickle, spotipy
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
ytmusic = YTMusic('headers_auth.json')
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id="CLIENT_ID",
                                               client_secret="CLIENT_SECRET",
                                               redirect_uri="http://www.example.com/",
                                               scope="user-library-read"))

# Get playlists from YouTube Music
ytm_playlists = ytmusic.get_library_playlists()
for candidate_playlist in ytm_playlists:
    playlist_author = candidate_playlist.get('author', [{}])[0].get('name', '')
    # Omit playlists by other users or YTM themselves
    if playlist_author == 'Andrew LD':
        print("Found your playlist " + candidate_playlist['title'])
        # Get songs of each playlist
        playlist_contents = ytmusic.get_playlist(playlistId=candidate_playlist['playlistId'], limit=1000)

        local_playlist = Playlist
        local_playlist.name = candidate_playlist['title']
        local_playlist.yt_id = candidate_playlist['playlistId']

        # Store song info in a Song object
        for playlist_song in playlist_contents['tracks']:
            local_song = Song
            local_song.album = playlist_song['album']
            local_song.artist = playlist_song['artists'][0]['name']
            local_song.name = playlist_song['title']
            # Convert song duration to number of seconds
            time_strings = playlist_song['duration'].split(':')
            local_song.duration_s = 60 * int(time_strings[0]) + int(time_strings[1])
            local_song.yt_id = playlist_song['videoId']

            # Get additional song info from Spotify
            # Search Spotify for the song to get its ID
            query_string = local_song.name + " " + local_song.artist
            strict_time_matching = True
            search_results=[]
            while True:
                search_results = sp.search(query_string, type='track')
                if search_results: # At least one song found
                    for candidate_song in search_results:
                        if strict_time_matching: # Validate song length against YTM
                            song_duration = search_results['tracks']['items'][0]['duration_ms']/1000 - local_song.duration_s
                            if abs(song_duration) <= 2:
                                target_song = search_results['tracks']['items'][0]
                        else:
                                break
                elif not strict_time_matching:
                    target_song = None
                    break
                else:
                    print("No suitable Spotify results found for song \"" + query_string + "\".  Type new search query or enter nothing to stop trying to match song duration (and give up if there are still no matches).")
                    user_search_string = input('Search Spotify for: ')
                    if len(user_search_string) < 1:
                        strict_time_matching = False
                    else:
                        query_string = user_search_string
            if target_song is None:
                print("Failed to get Spotify info for song ")
                break
            song_spotify_id = target_song['id']
            features = sp.audio_features(tracks=[song_spotify_id])[0]
            local_song.bpm = features['tempo']

            # Process Spotify info into preferrable format
            # Validate and convert song key
            local_song.key = features['key']
            if features['key'] == -1:
                print("Spotify does not know the key of song " + local_song.name + " by " + local_song.artist)
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