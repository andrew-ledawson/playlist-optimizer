import json, subprocess
from foundation import *

print("Song rater")
print("Allows rating songs by certain traits (+2 to -2) while playing a sample of the song. ")
print("Enter \"e\" in a rating prompt to save and exit and \"s\" to skip to next song. ")
print("Make sure that the contents of an FFMPEG release are in a folder named \"ffmpeg\" (so that the bin/ folder is within it) and that yt-dlp.exe is in the same folder as this script. ")

playlists_db, songs_db = load_data_files()

# Prompt user to select playlist
print("\nEnter a playlist number to rate, or enter nothing to rate all songs in database. ")
for number, playlist in enumerate(list(playlists_db.values())):
    print(str(number + 1) + ": " + playlist.name)
selected_song_ids = list()
selection = input("Playlist: ")
if selection == "":
    selected_song_ids = songs_db.keys()
else:
    selected_playlist = list(playlists_db.values())[int(selection) - 1]
    selected_song_ids = selected_playlist.song_ids

print("\nWhat output volume (0-100) should song samples be played at? ")
desired_volume = None
while desired_volume is None:
    try:
        volume_input = int(input("Volume: "))
        assert 0 <= volume_input <= 100
        desired_volume = volume_input
    except:
        print("Invalid volume. Input a number 0 up to 100. ")

print("\nHow many seconds into the song should playback start? ")
sample_time_offset = None
while sample_time_offset is None:
    try:
        time_offset_input = int(input("Seconds: "))
        assert time_offset_input >= 0
        sample_time_offset = time_offset_input
    except:
        print("Invalid number of seconds. Input some number, starting at 0. ")

def print_traits_info():
    print("\nRate songs from -2 to 2 for the following traits: ")
    for trait, description in USER_RATINGS.items():
        print(trait + ": " + description)

print_traits_info()
print("\nHow often to print this list of ratings traits? Enter '0' to only print at start. ")
desired_reminder_frequency = None
while desired_reminder_frequency is None:
    try:
        reminder_frequency_input = int(input("Songs between ratings reminders: "))
        assert reminder_frequency_input >= 0
        desired_reminder_frequency = reminder_frequency_input
    except:
        print("Invalid time. Input some number, starting at 0. ")

print("\nTo play a preview of some songs, you need to provide a \"Netscape format\" \"cookies.txt\" file of music.youtube.com. ")
print("Please provide the path to the file, or enter nothing to skip playback. ")
cookies_file_path = input("Cookies file path: ")

num_songs_rated = 0

# For each song, prompt user to rate on each trait
for index, song_id in enumerate(selected_song_ids):
    should_exit_rating_loop = False
    skip_to_next_song = False
    song_rated = False

    target_song = songs_db[song_id]

    if not target_song.has_latest_ratings():
        print("\n\"" + target_song.name + "\" by \"" + target_song.artist + "\"")

        # Play a sample of the song in the background, unless disabled
        player = None
        if desired_volume > 0:
            play_url = None
            # Try different song IDs as necessary
            id_candidates = [song_id]
            for candidate_id in id_candidates:
                try:
                    yt_manifes_text = subprocess.check_output("./yt-dlp.exe -j " + \
                                                            ("--cookies " + cookies_file_path + " " if cookies_file_path != "" else " ") + \
                                                            "--extractor-args player_client:web_music " + \
                                                            "-- " + song_id)
                    yt_manifest = json.loads(yt_manifes_text)

                    # Parse the response JSON to find preferred audio formats
                    # 251 is higher quality OPUS audio (for all videos)
                    # 140 and 141 are YouTube Music AAC formats
                    # 18 is 360p MP4, a legacy non-DASH format
                    for perferred_format in ["251", "140", "141", "18"]:
                        for format_json in yt_manifest['formats']:
                            if format_json['format_id'] == perferred_format:
                                play_url = format_json['url']
                except:
                    print("Failed to acquire stream for song sample (ID " + song_id + "). ")
                    # TODO: Check alt song data API 'isPrivate' is True
                    # or musicVideoType is 'MUSIC_VIDEO_TYPE_PRIVATELY_OWNED_TRACK'
                    print("Note that this program cannot stream songs that you uploaded to your own account. ")
            if play_url is not None:
                player = subprocess.Popen("ffmpeg/bin/ffplay.exe " + play_url + " -volume " + str(desired_volume) + " -ss " + str(sample_time_offset) + " -nodisp -loglevel error", stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
                # stdout=subprocess.DEVNULL,

        target_ratings = target_song.user_ratings
        for trait in USER_RATINGS:
            while trait not in target_ratings or target_ratings[trait] is None:
                try:
                    rating_input = input(trait + ": ")
                    if rating_input == "e":
                        should_exit_rating_loop = True
                        break
                    elif rating_input == "s":
                        skip_to_next_song = True
                        break
                    rating = int(rating_input)
                    assert -2 <= rating <= 2
                    target_ratings[trait] = rating
                    song_rated = True
                except:
                    print("Invalid rating. Enter -2 to 2, [e]xit, or [s]kip. ")
            if should_exit_rating_loop or skip_to_next_song:
                break
        if song_rated:
            if desired_reminder_frequency != 0 and num_songs_rated % desired_reminder_frequency == 0:
                print_traits_info()
            num_songs_rated = num_songs_rated + 1
        if player is not None:
            player.terminate()
        if should_exit_rating_loop:
            break
        elif skip_to_next_song:
            continue

print("Rated " + str(num_songs_rated) + " songs; saving song database and exiting. ")
cleanup_songs_db(songs_db, playlists_db)
write_song_db(songs_db)
