from foundation import *

print("Metadata fixer")

playlists_db, songs_db = load_data_files()

prompt_message = "\nEnter a playlist number to rate, or enter nothing to rate all songs in database. "
song_ids_to_check = prompt_for_playlist(playlists_db, prompt_message)
should_check_flagged_songs = prompt_user_for_bool("Check only songs that were flagged for review? ")

for song_id in song_ids_to_check:
    song = songs_db[song_id]
    assert song is not None, "Song ID " + song_id + " not found in database. Please rerun downloader to update this song. "
    if song.metadata_needs_review or not should_check_flagged_songs:
        download_song_features(song, compare_metadata=True, get_features=False)

# TODO: If thorough, check video ID against YouTube and prompt if private
# TODO: if thorough and private fixes made, prompt user to replace remote playlist
