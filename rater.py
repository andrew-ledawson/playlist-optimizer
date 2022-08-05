from foundation import *

import requests, signal, subprocess

print("Song rater")
print("Allows rating songs by certain traits (+2 to -2) while playing a sample of the song. ")
print("Enter \"e\" in a rating prompt to save and exit and \"s\" to skip to next song. ")

playlists_db, songs_db = load_data_files()

# Prompt user to select playlist
print("\nEnter a playlist number to rate, or enter nothing to rate all songs in database. ")
selected_song_ids = prompt_for_playlist(playlists_db).song_ids
if selected_song_ids is None:
    selected_song_ids = songs_db.keys()

print("\nWhat output volume should song samples be played at?  0 disables playback.  ")
desired_volume = None
while desired_volume is None:
    try:
        volume_input = int(input("Volume, 0-100: "))
        assert 0 <= volume_input <= 100
        desired_volume = volume_input
    except:
        print("Invalid volume. Input a number from 0 up to 100. ")

sample_time_offset = None
if desired_volume > 0:
    print("\nHow many seconds into the song should playback start? ")
    while sample_time_offset is None:
        try:
            time_offset_input = int(input("Seconds: "))
            assert time_offset_input >= 0
            sample_time_offset = time_offset_input
        except:
            print("Invalid number of seconds. Input some number, starting at 0. ")

def print_traits_info():
    print("\nRemember to rate songs from -2 to 2 for the following traits: ")
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

# TODO later: presist preferences, such as cookies.txt path, and try to load before prompting
cookies_file_path = None
if desired_volume > 0:
    print("\nTo play a preview of some songs, use a browser plugin to get a \"Netscape format cookies.txt\" file from your music.youtube.com session. ")
    print("Please save the file and input its location, or enter nothing to skip playback. ")
    input_path = input("Cookies file path: ")
    if input_path != "":
        cookies_file_path = input_path

num_songs_rated = 0

def extract_playback_url_from_json(json):
    """
    Parse the response JSON to find preferred audio formats
    251 is higher quality OPUS audio (for all videos)
    140 and 141 are YouTube Music AAC formats
    18 is 360p MP4, a legacy non-DASH video+audio format
    """
    for perferred_format in ["251", "140", "141", "18"]:
        for format_json in json['formats']:
            if format_json['format_id'] == perferred_format:
                return format_json['url'], perferred_format
    return None, None

def download_ytm_song(play_url, play_format, song_name):
    try:
        playback_data_response = requests.get(play_url)
        extension = "ogg"
        if play_format == 140 or play_format == 141:
            extension = "m4a"
        illegal_filename = str(num_songs_rated) + " " +  song_name
        # TODO: Zero pad
        legal_filename = "".join(x for x in illegal_filename if (x.isalnum() or x == ' ')) + "." + extension
        while "  " in legal_filename: # Remove duplicate spaces
            legal_filename = legal_filename.replace("  ", " ")
        with open(legal_filename, "xb") as playback_file:
            playback_file.write(playback_data_response.content)
    except Exception as error:
        print("Failed to download song: " + str(error))

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
            play_format = None
            ytdlp_path_candidates = ["yt-dlp.exe", "./yt-dlp.exe", "yt-dlp", "./yt-dlp"]
            for ytdlp_path_index, ytdlp_path in enumerate(ytdlp_path_candidates):
                try:
                    yt_manifest_text = subprocess.check_output(ytdlp_path + " -j " + \
                                                               ("--cookies " + cookies_file_path + " " if cookies_file_path is not None else " ") + \
                                                               "--extractor-args player_client:web_music " + \
                                                               "-- " + song_id)
                    yt_manifest = json.loads(yt_manifest_text)
                    play_url, play_format = extract_playback_url_from_json(yt_manifest)
                    if play_url is not None:
                        break
                except Exception as error:
                    print("Failed to acquire stream for song sample (ID " + song_id + "). ")
                    if type(error) is FileNotFoundError:
                        print("Helper program not found, please install yt-dlp, or be sure you placed yt-dlp.exe in this program folder. ")
                    elif target_song.is_private:
                        print("This is a private song uploaded directly to your account. It cannot be played by this program. ")
            song_time_offset = sample_time_offset
            if play_url is None:
                # If youtube playback isn't available, try Spotify's MP3 preview
                print("Falling back to Spotify song preview, ignoring offset")
                play_url = target_song.spotify_preview_url
                song_time_offset = 0
            if play_url is not None:
                #download_ytm_song(play_url, play_format, target_song.name)
                # Try different ffplay paths
                ffplay_path_candidates = ["ffplay.exe", "ffmpeg/bin/ffplay.exe", "ffplay", "ffmpeg/bin/ffplay"]
                for ffplay_path_index, ffplay_path in enumerate(ffplay_path_candidates):
                    try:
                        player = subprocess.Popen(ffplay_path + " " + play_url + " -volume " + str(desired_volume) + " -ss " + str(song_time_offset) + " -nodisp -loglevel error", stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                        # stdout=subprocess.DEVNULL,
                        break # Player launched successfully, stop trying ffplay paths
                    except Exception as error:
                        if ffplay_path_index == len(ffplay_path_candidates) - 1: # Exhausted ffplay paths
                            print("Failed to play stream for song sample (ID " + song_id + "). ")
                            if type(error) is FileNotFoundError:
                                print("Helper program not found, please install ffmpeg and yt-dlp, or be sure you placed yt-dlp.exe and a copy of the folder \"ffmpeg\" (containing bin/ff*.exe) in this program folder. ")
                            elif target_song.is_private:
                                print("This is a private song uploaded directly to your account. It cannot be played by this program. ")

        target_ratings = target_song.user_ratings
        if target_ratings is None:
            target_ratings = dict()
            target_song.user_ratings = target_ratings
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
            # TODO: if windows, else...
            subprocess.call(['taskkill', '/F', '/T', '/PID',  str(player.pid)], stdout=subprocess.DEVNULL) #, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            #os.kill(player.pid, signal.SIGTERM)
            # TODO: Sometimes termianting the player leaves its child running, try switching from Popen() to run(), and also maybe running process with shell flag enabled
            # Can't use signal 1, it kills python process
            # signal.SIGBREAK and signal.SIG_DFL not found (at least on Windows)
            """
            for index, signal in enumerate([signal.SIGINT, signal.SIGTERM]):
                try:
                    print("Trying to kill player with signal " + str(index))
                    player.send_signal(signal)
                    if player.poll() == None: # Player alive after signal sent
                        time.sleep(1.5) # Wait a moment for player to die
                        if player.poll() != None: # Player killed after waiting
                            break # Stop trying kill signals
                    else: # Player was instantly killed
                        break # Stop trying kill signals
                except:
                    pass
            """
        if should_exit_rating_loop:
            break
        elif skip_to_next_song:
            continue

print("\nRated " + str(num_songs_rated) + " songs; saving song database and exiting. ")
cleanup_songs_db(songs_db, playlists_db)
write_song_db(songs_db)
