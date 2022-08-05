from foundation import *

import requests, subprocess

playlists_db, songs_db = load_data_files()

# Prompt user to select playlist
print("\nEnter a playlist number to download, or enter nothing to download all songs in database. ")
selected_song_ids = prompt_for_playlist(playlists_db).song_ids
if selected_song_ids is None:
    selected_song_ids = songs_db.keys()

num_songs_rated = 0

def download_ytm_song(play_url, play_format, song_name, song_number):
    try:
        playback_data_response = requests.get(play_url)
        extension = "webm"
        if play_format == 140 or play_format == 141:
            extension = "m4a"
        illegal_filename = str(song_number) + " " +  song_name
        legal_filename = "".join(x for x in illegal_filename if (x.isalnum() or x == ' ')) + "." + extension
        while "  " in legal_filename: # Remove duplicate spaces
            legal_filename = legal_filename.replace("  ", " ")
        with open(legal_filename, "xb") as playback_file:
            playback_file.write(playback_data_response.content)
    except Exception as error:
        print("Failed to download song: " + str(error))

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

for index, song_id in enumerate(selected_song_ids):
    play_url = None
    play_format = None
    target_song = songs_db[song_id]
    ytdlp_path_candidates = ["yt-dlp.exe", "./yt-dlp.exe", "yt-dlp", "./yt-dlp"]
    for ytdlp_path_index, ytdlp_path in enumerate(ytdlp_path_candidates):
        try:
            yt_manifest_text = subprocess.check_output(ytdlp_path + " -j " + \
                                                       "--cookies cookies.txt " + \
                                                       "--extractor-args player_client:web_music " + \
                                                       "-- " + song_id)
            yt_manifest = json.loads(yt_manifest_text)
            play_url, play_format = extract_playback_url_from_json(yt_manifest)
            if play_url is not None:
                break
        except Exception as error:
            print("Failed to acquire stream for song sample (ID " + song_id + "). ")
    if play_url is not None:
        download_ytm_song(play_url, play_format, target_song.name, index)
    else:
        print("Could not get url to download")

"""
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

"""
song_id = "DwanG6dAl18"
metadata = download_metadata_from_YT_id(song_id)
#response = YTM.get_watch_playlist(song_id)
print("done")
"""