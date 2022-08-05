from foundation import *

print("Metadata fixer")

playlists_db, songs_cache = load_data_files()

print("\nEnter a playlist number to rate, or enter nothing to rate all songs in the cache. ")
song_ids_to_check = prompt_for_playlist(playlists_db).song_ids
if song_ids_to_check is None:
    song_ids_to_check = songs_cache.keys()

should_check_flagged_songs = prompt_user_for_bool("Check only songs that were flagged for review? ")

search_spotify = prompt_user_for_bool("Search Spotify for song metadata? ")

# TODO later: offer advanced control to delete songs, redownload features, etc.

num_songs_processed = 0
for song_id in song_ids_to_check:
    song = songs_cache[song_id]
    assert song is not None, "Song ID " + song_id + " not found in the cache. Please rerun downloader. "
    if song.metadata_needs_review or not should_check_flagged_songs:
        num_songs_processed = num_songs_processed + 1
        check_result = process_song_metadata(song=song, search_spotify=search_spotify, edit_metadata=True, get_features=False)
        if check_result is None:
            break

# TODO later: Make "private song fixer" that checks video ID against YouTube, prompts if private, and offers to update remote playlist

print("Processed " + str(num_songs_processed) + " songs; saving song cache and exiting. ")
cleanup_song_cache(songs_cache, playlists_db)
write_song_cache(songs_cache)