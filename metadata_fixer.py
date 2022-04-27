from foundation import *

print("Metadata fixer")

playlists_db, songs_db = load_data_files()

prompt_message = "\nEnter a playlist number to rate, or enter nothing to rate all songs in database. "
song_ids_to_check = prompt_for_playlist(playlists_db, prompt_message)
if song_ids_to_check is None:
    song_ids_to_check = songs_db.keys()
should_check_flagged_songs = prompt_user_for_bool("Check only songs that were flagged for review? ")

num_songs_processed = 0
for song_id in song_ids_to_check:
    song = songs_db[song_id]
    assert song is not None, "Song ID " + song_id + " not found in database. Please rerun downloader to update this song. "
    if song.metadata_needs_review or not should_check_flagged_songs:
        num_songs_processed = num_songs_processed + 1
        check_result = download_song_features(song, compare_metadata=True, get_features=False)
        if check_result is None:
            break

# TODO: If thorough, check video ID against YouTube and prompt if private
# TODO: if thorough and private fixes made, prompt user to replace remote playlist

print("Processed " + str(num_songs_processed) + " songs; saving song database and exiting. ")
cleanup_songs_db(songs_db, playlists_db)
write_song_db(songs_db)