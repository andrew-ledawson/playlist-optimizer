import os

from foundation import *

# Launch and auth YouTube Music and Spotify
print("Launching playlist metadata collector.")

# Check which playlists are already saved
target_folder = '.'
saved_playlists, all_songs = load_local_playlists(target_folder)
print("Loaded " + str(len(saved_playlists.keys())) + " saved playlists.")

# Go through each user playlist on YouTube Music
playlist_limit = int(input("How many of your playlists to load? "))
ytm_playlists = run_API_request(lambda : YTM.get_library_playlists(limit=playlist_limit), "to load YouTube Music library playlists")
print("Checking your first " + str(playlist_limit) + " YTM playlists. ")
print("What is the exact spelling of the desired YouTube Music account name or channel ID? Check by opening one of the playlists on music.youtube.com and looking at the author name directly below the playlist name. ")
user_name = input("Name/ID: ")
for candidate_playlist in ytm_playlists:
    local_playlist = Playlist()
    local_playlist.name = candidate_playlist['title']
    local_playlist.yt_id = candidate_playlist['playlistId']
    local_playlist_author_name = candidate_playlist.get('author', [{}])[0].get('name', '')
    local_playlist_author_id =  candidate_playlist.get('author', [{}])[0].get('id', '')

    # Omit playlists by other users or YTM themselves
    if local_playlist_author_name == user_name or local_playlist_author_id == user_name:
        print("Found playlist \"" + local_playlist.name + "\".")

        # Check if playlist is already downloaded and prompt to update it (i.e. replace it)
        if local_playlist.yt_id in saved_playlists:
            if not get_user_bool("Playlist was already downloaded. Update? "):
                continue

        # Get songs of each playlist
        remote_playlist_contents = run_API_request(lambda : YTM.get_playlist(playlistId=local_playlist.yt_id, limit=int(candidate_playlist['count']) + 1), "to get the songs for YouTube Music playlist \"" + local_playlist.name + "\"")
        playlist_length = str(len(remote_playlist_contents['tracks']))
        print("Playlist has " + playlist_length + " songs to check... ")

        # Store song info in a Song object
        for song_count, playlist_song in enumerate(remote_playlist_contents['tracks']):
            # Print update every 10 songs since this can take a few seconds per song
            if song_count % 10 == 9:
                print("Checking song " + str(song_count + 1) + " of " + playlist_length + "... ")

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
                    print("Using alternate method to get duration of song \"" + local_song.name + "\". ")
                    alt_lookup_song = download_metadata(local_song.yt_id)
                    local_song.duration_s = alt_lookup_song.duration_s
                    # Compare metadata just in case
                    alt_lookup_song.album = local_song.album # Album not included in song info API
                    if local_song != alt_lookup_song:
                        print("Caution: alternate method gave different song metadata! ")

                gather_song_features(local_song)
                all_songs[local_song.yt_id] = local_song

            local_playlist.songs_ids.append(local_song.yt_id)

        # Store playlist as a file
        playlist_file = open(target_folder + "/playlist_" + local_playlist.yt_id + ".pp1", "wb")
        pickle.dump(local_playlist, playlist_file)
        playlist_file.close()
        print("Done processing playlist \"" + local_playlist.name + "\"; saved to folder. ")

print("Done processing returned playlists; saving song database and exiting. ")
# Save song database, moving old copy to backup location in case save is interrupted
os.rename(SONG_DB_FILE, SONG_DB_FILE + '.bak')
songs_file = open(SONG_DB_FILE, "wb")
pickle.dump(all_songs, songs_file)
songs_file.close()
os.remove(SONG_DB_FILE + '.bak')