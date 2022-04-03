import os

from foundation import *

# Launch and auth YouTube Music and Spotify
print("Launching playlist metadata collector.")

# Check which playlists are already saved
saved_playlists, all_songs = load_local_playlists('.')
print("DEBUG: got " + str(len(saved_playlists.keys())) + " playlists from filesystem")

# Go through each user playlist on YouTube Music
pace_ops()
ytm_playlists = YTM.get_library_playlists()
print("Checking your saved YTM playlists.")
for candidate_playlist in ytm_playlists:
    local_playlist = Playlist()
    local_playlist.name = candidate_playlist['title']
    local_playlist.yt_id = candidate_playlist['playlistId']
    local_playlist_author = candidate_playlist.get('author', [{}])[0].get('name', '')

    # Check if playlist is already downloaded and prompt to update it
    if local_playlist.yt_id in saved_playlists:
        if not get_user_bool("Playlist \"" + local_playlist.name + "\" was already downloaded.  Update?  "):
            continue
        else:
            local_playlist = saved_playlists[local_playlist.yt_id]

    # Omit playlists by other users or YTM themselves
    if local_playlist_author == 'Andrew LD':
        print("Found your playlist \"" + local_playlist.name + "\".")
        # Get songs of each playlist
        pace_ops()
        remote_playlist_contents = YTM.get_playlist(playlistId=local_playlist.yt_id, limit=int(candidate_playlist['count']) + 1)

        # Store song info in a Song object
        for song_count, playlist_song in enumerate(remote_playlist_contents['tracks']):
            # Print update every 10 songs since this can take a few seconds per song
            if song_count % 10 == 9:
                print("Checking song " + str(song_count + 1) + " of " + str(len(remote_playlist_contents['tracks'])) + " for playlist \"" + local_playlist.name + "\".")

            # Create Song object from YTM's response for the playlist contents
            local_song = Song()
            local_song.yt_id = playlist_song['videoId']
            if local_song.yt_id not in all_songs:
                local_song.album = playlist_song['album']
                local_song.artist = playlist_song['artists'][0]['name']
                local_song.name = playlist_song['title']
                if 'duration' in playlist_song:
                    # Convert song duration to number of seconds
                    time_strings = playlist_song['duration'].split(':')
                    local_song.duration_s = 60 * int(time_strings[0]) + int(time_strings[1])
                else:
                    # For some godforsaken reason, YTM won't return duration once in a while
                    print("Using alternate method to get duration of song \"" + local_song.name + "\".")
                    alt_lookup_song = download_metadata(local_song.yt_id)
                    local_song.duration_s = alt_lookup_song.duration_s
                    # Compare metadata just in case
                    alt_lookup_song.album = local_song.album # Album not included in song info API
                    if local_song != alt_lookup_song:
                        print("Warning: YTM returned different song data from different APIs")

                local_playlist.songs_ids.append(local_song.yt_id)

                gather_song_features(local_song)
                all_songs[local_song.yt_id] = local_song

        # Store playlist as a file
        playlist_file = open("playlist_" + local_playlist.yt_id+ ".pp1", "wb")
        pickle.dump(local_playlist, playlist_file)
        playlist_file.close()

print("Done with playlists; saving song database and exiting.")
# Save song database, moving old copy to backup location in case save is interrupted
os.rename(SONG_DB_FILE, SONG_DB_FILE + '.bak')
songs_file = open(SONG_DB_FILE, "wb")
pickle.dump(all_songs, songs_file)
songs_file.close()
os.remove(SONG_DB_FILE + '.bak')