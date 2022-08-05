import os

from foundation import *

# Check which playlists are already saved
playlists_db, songs_cache = load_data_files()

# Go through each user playlist on YouTube Music
playlist_limit = 0
while playlist_limit <= 0:
    try:
        playlist_limit = int(input("How many of your playlists to load from YouTube Music? "))
    except:
        print("Invalid number? ")
ytm_playlists = run_API_request(lambda : YTM.get_library_playlists(limit=playlist_limit), "to load YouTube Music library playlists")
print("Got " + str(len(ytm_playlists)) + " playlists from YouTube Music. ")
print("What author's playlists should be downloaded from your YouTube Music Library? Check by opening one of the playlists on music.youtube.com and looking at the author name (directly below the playlist name). ")
user_name = input("Account name or channel ID: ")

overwrite_all_playlists = prompt_user_for_bool(message="Redownload and overwrite playlists that are already saved? Leave answer empty to prompt for every playlist. ", allow_no_response=True)

num_playlists_processed = 0

for candidate_playlist in ytm_playlists:
    local_playlist = Playlist()
    local_playlist.name = candidate_playlist['title']
    local_playlist.yt_id = candidate_playlist['playlistId']
    local_playlist_author_name = candidate_playlist.get('author', [{}])[0].get('name', '')
    local_playlist_author_id =  candidate_playlist.get('author', [{}])[0].get('id', '')
    local_playlist.song_ids = list()

    # Omit playlists by other users or YTM themselves
    if local_playlist_author_name == user_name or local_playlist_author_id == user_name:
        print("Found playlist \"" + local_playlist.name + "\". ")

        # Skip this playlist if it was already downloaded and should not be replaced
        if overwrite_all_playlists is not True and local_playlist.yt_id in playlists_db:
            if overwrite_all_playlists is False or not prompt_user_for_bool("Playlist \"" + local_playlist.name + "\" was already downloaded. Overwrite? "):
                continue # Skip to next playlist
        # Prompt user for playlist if not otherwise asked
        elif not prompt_user_for_bool("Download playlist \"" + local_playlist.name + "\"? "):
            continue

        # Get songs in the playlist
        remote_playlist_contents = run_API_request(lambda : YTM.get_playlist(playlistId=local_playlist.yt_id, limit=int(candidate_playlist['count']) + 1), "to get the songs for YouTube Music playlist \"" + local_playlist.name + "\"")
        playlist_length = str(len(remote_playlist_contents['tracks']))
        print("Playlist has " + playlist_length + " songs to check, please wait a few moments for each song... ")

        # Store song info in a Song object
        for song_count, playlist_song in enumerate(remote_playlist_contents['tracks']):
            # Print update every 10 songs since this can take a few seconds per song
            if song_count % 10 == 9:
                print("Checking song " + str(song_count + 1) + " of " + playlist_length + "... ")

            # Create Song object from YTM's response for the playlist contents
            local_song = Song()
            local_song.yt_id = playlist_song['videoId']
            if local_song.yt_id not in songs_cache:
                if playlist_song['album'] is not None:
                    local_song.album = playlist_song['album']['name']
                local_song.artist = playlist_song['artists'][0]['name']
                local_song.name = playlist_song['title']
                if 'duration' in playlist_song:
                    # Convert song duration to number of seconds
                    time_strings = playlist_song['duration'].split(':')
                    local_song.duration_s = 60 * int(time_strings[0]) + int(time_strings[1])
                else:
                    # Some YTM songs don't include duration in the playlist response
                    print("Using alternate method to get duration of song \"" + local_song.name + "\". ")
                    alt_lookup_song = download_metadata_from_YT_id(local_song.yt_id)
                    local_song.duration_s = alt_lookup_song.duration_s

                process_song_metadata(song=local_song, search_spotify=True, edit_metadata=False, get_features=True)
                songs_cache[local_song.yt_id] = local_song

            local_playlist.song_ids.append(local_song.yt_id)

        # Store complete playlist
        playlist_file = open('./' + PLAYLIST_FILE_PREFIX + local_playlist.yt_id + PLAYLIST_FILE_EXTENSION, "wb")
        pickle.dump(local_playlist, playlist_file)
        playlist_file.close()
        playlists_db[local_playlist.yt_id] = local_playlist
        print("Done processing playlist \"" + local_playlist.name + "\"; saved to folder. ")
        num_playlists_processed = num_playlists_processed + 1
        write_song_cache(songs_cache)

print("Processed " + str(num_playlists_processed) + " playlists; exiting. ")
