import os

from foundation import *

# Launch and auth YouTube Music and Spotify
print("Launching playlist metadata collector")

# Check which playlists are already saved
saved_playlists, all_songs = load_local_playlists('.')

# Go through each user playlist on YouTube Music
pace_ops()
ytm_playlists = YTM.get_library_playlists()
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
        remote_playlist_contents = YTM.get_playlist(playlistId=local_playlist.yt_id, limit=local_playlist_song_count + 1)

        # Store song info in a Song object
        for song_count, playlist_song in enumerate(remote_playlist_contents['tracks']):
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

            local_playlist.songs.append(local_song.yt_id)

            # TODO: Rewrite everything to have a central songs DB, and playlists just have a list of YT ids
            # TODO: call gather_song_metadata then update stuff accordingly

            # Save song to playlist
            

        # Store playlist as a file
        playlist_file = open("playlist_" + local_playlist.yt_id+ ".pp1", "wb")
        pickle.dump(local_playlist, playlist_file)
        playlist_file.close()

# Save song database
os.rename('songs.pps', 'songs.pps.bak')
songs_file = open('songs.pps', "wb")
pickle.dump(all_songs, songs_file)
songs_file.close()
os.remove('songs.pps.bak')