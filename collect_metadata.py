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
playlists = []
ytm_playlists = ytmusic.get_library_playlists()
for candidate_playlist in ytm_playlists:
    playlist_author = candidate_playlist.get('author', [{}])[0].get('name', '')
    if playlist_author == 'Andrew LD':
        print("found your playlist " + candidate_playlist['title'])
        playlist_contents = ytmusic.get_playlist(playlistId=candidate_playlist['playlistId'], limit=1000)

        local_playlist = Playlist
        local_playlist.name = candidate_playlist['title']
        local_playlist.yt_id = candidate_playlist['playlistId']

        # Store song info
        for playlist_song in playlist_contents['tracks']:
            local_song = Song
            local_song.album = playlist_song['album']
            local_song.artist = playlist_song['artists'][0]['name']
            local_song.name = playlist_song['title']
            time_strings = playlist_song['duration'].split(':')
            local_song.duration_s = 60 * int(time_strings[0]) + int(time_strings[1])
            local_song.yt_id = playlist_song['videoId']
            
            # Get additional song info from Spotify
            query_string = local_song.name + " " + local_song.artist
            search_results = sp.search(query_string, type='track')
            song_spotify_id = search_results['items'][0]['id']
            features = sp.audio_features(tracks=[song_spotify_id])

            song_duration = features['duration_ms']/1000 - local_song.duration_s
            if abs(song_duration) > 5:
                print("Warning: Spotify's version of song " + local_song.name + " by " + local_song.artist + " is " + str(song_duration) + " longer")
            local_song.bpm = features['tempo']
            local_song.key = features['key']
            if features['key'] == -1:
                print("Spotify does not know the key of song " + local_song.name + " by " + local_song.artist)
            else:
                # TODO: translate pitch class into camelot
                if features['mode'] == 1:
                    local_song.camelot_position, _ = camelot_lookup[features['key']]
                    local_song.camelot_is_minor = False
                else:
                    _, local_song.camelot_position = camelot_lookup[features['key']]
                    local_song.camelot_is_minor = True
            
            local_playlist.songs.append(local_song)