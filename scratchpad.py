from foundation import *

saved_playlists, songs_db = load_data_files('.')

selected_playlist = prompt_for_playlist(saved_playlists)
all_songs_ratings = []
for song_id in selected_playlist.song_ids:
    song = songs_db[song_id]
    if song.user_ratings not in all_songs_ratings:
        all_songs_ratings.append(song.user_ratings)
    else:
        song.user_ratings = dict()

write_song_db(songs_db)

"""
song_id = "DwanG6dAl18"
metadata = download_metadata_from_YT_id(song_id)
#response = YTM.get_watch_playlist(song_id)
print("done")
"""