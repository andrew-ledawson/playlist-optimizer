from foundation import *

saved_playlists, all_songs = load_data_files('.')

for key, song in all_songs.items():
    if type(song.album) is dict:
        song.album = song.album['name']

"""ids_to_remove = []
for id, song in all_songs.items():
    if type(song) is not Song:
        ids_to_remove.append(id)
        print("Popping " + id)
for id in ids_to_remove:
    all_songs.pop(id)"""

"""for index, song_a in enumerate(list(all_songs.values())):
    #song_a.user_ratings = dict()
    for song_b_index in range(index+1, len(all_songs.values())):
        song_b = list(all_songs.values())[song_b_index]
        #print("DEBUG: Checking " + song_a.name + " and " + song_b.name)
        if song_a.user_ratings is song_b.user_ratings:
            print("Shared ratings object detected between " + song_a.name + " and " + song_b.name)"""

write_song_db(all_songs)

"""
song_id = "DwanG6dAl18"
metadata = download_metadata_from_YT_id(song_id)
#response = YTM.get_watch_playlist(song_id)
print("done")
"""