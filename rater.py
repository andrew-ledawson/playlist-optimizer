from foundation import *

print("Song rater")
print("Allows rating songs by certain traits while playing a sample of the song. Enter \"e\" in a rating prompt to save and exit. ")
print("Make sure the contents of an FFMPEG release are in a folder named \"ffmpeg\" (so that the bin/ folder is within it) and yt-dlp.exe is in the same folder as this script. ")

# Load songs and playlists
target_folder = '.'
saved_playlists, all_songs = load_local_playlists(target_folder)
print("Enter a playlist number to rate, or enter nothing to rate all songs in database. ")
for number, playlist in enumerate(list(saved_playlists.values())):
    print(str(number + 1) + ": " + playlist.name)

selected_song_ids = []
selection = input("Playlist: ")
if selection == "":
    selected_song_ids = all_songs.keys()
else:
    selected_playlist = list(saved_playlists.values())[int(selection) - 1]
    selected_song_ids = selected_playlist.song_ids

print("Rate songs from -2 to 2 for the following traits: ")
for trait, description in USER_RATINGS.items():
    print(trait + ": " + description)

print("What input volume (0-100) should song samples be played at? ")
volume = None
while volume is None:
    try:
        volume_input = int(input("Volume: "))
        assert 0 <= volume_input <= 100
        volume = volume_input
    except:
        print("Invalid volume. Input a number 0 up to 100. ")

print("How many seconds into the song should playback start? ")
time_offset = None
while time_offset is None:
    try:
        time_offset_input = int(input("Seconds: "))
        assert time_offset_input >= 0
        time_offset = time_offset_input
    except:
        print("Invalid time. Input some number, starting at 0. ")

for song_id in selected_song_ids:
    should_exit = False
    target_song = all_songs[song_id]
    print("\"" + target_song.name + "\" by \"" + target_song.artist + "\"")
    # TODO: invoke youtube-dl then ffmpeg to play preview
    # TODO: why does entering a rating apply it to every song?
    target_ratings = target_song.user_ratings
    for trait in USER_RATINGS:
        while trait not in target_ratings or target_ratings[trait] is None:
            try:
                rating_input = input(trait + ": ")
                if rating_input == "e":
                    should_exit = True
                    break
                rating = int(rating_input)
                assert -2 <= rating <= 2
                target_ratings[trait] = rating
            except:
                print("Invalid rating. Enter -2, -1, 0, 1, or 2. ")
        if should_exit:
            break
    if should_exit:
        break
    # TODO: Verify references are all updated before overwriting db

print("Done rating; saving song database and exiting. ")
write_song_db(all_songs)
