import json, subprocess
from foundation import *

print("Song rater")
print("Allows rating songs by certain traits (+2 to -2) while playing a sample of the song. Enter \"e\" in a rating prompt to save and exit. ")
print("Make sure that the contents of an FFMPEG release are in a folder named \"ffmpeg\" (so that the bin/ folder is within it) and that yt-dlp.exe is in the same folder as this script. ")

saved_playlists, all_songs = load_local_playlists()

# Prompt user to select playlist
print("Enter a playlist number to rate, or enter nothing to rate all songs in database. ")
for number, playlist in enumerate(list(saved_playlists.values())):
    print(str(number + 1) + ": " + playlist.name)
selected_song_ids = list()
selection = input("Playlist: ")
if selection == "":
    selected_song_ids = all_songs.keys()
else:
    selected_playlist = list(saved_playlists.values())[int(selection) - 1]
    selected_song_ids = selected_playlist.song_ids

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

def print_ratings_traits():
    print("Rate songs from -2 to 2 for the following traits: ")
    for trait, description in USER_RATINGS.items():
        print(trait + ": " + description)

print_ratings_traits()

print("How often to print this list of ratings traits? Enter '0' to only print at start. ")
# TODO: implement reminders
reminder_frequency = None
while reminder_frequency is None:
    try:
        reminder_frequency_input = int(input("Songs between ratings reminders: "))
        assert reminder_frequency_input >= 0
        reminder_frequency = reminder_frequency_input
    except:
        print("Invalid time. Input some number, starting at 0. ")
print_ratings_traits()

"""print("Please download a \"Netscape format\" cookies.txt dump of music.youtube.com and give the file path.")
cookies_file_path = input("Cookies file path: ")"""

# For each song, prompt user to rate on each trait
for index, song_id in enumerate(selected_song_ids):
    should_exit = False
    target_song = all_songs[song_id]
    print("\"" + target_song.name + "\" by \"" + target_song.artist + "\"")

    player = None
    yt_manifes_text = subprocess.check_output("./yt-dlp.exe -j -- " + song_id)
    yt_manifest = json.loads(yt_manifes_text)
    for format_json in yt_manifest['formats']:
        if format_json['format_id'] == "251":
            player = subprocess.Popen("ffmpeg/bin/ffplay.exe " + format_json['url'] + " -volume " + str(volume) + " -ss " + str(time_offset) + " -nodisp", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)

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
    player.terminate()
    if should_exit:
        break

print("Done rating; saving song database and exiting. ")
write_song_db(all_songs)
