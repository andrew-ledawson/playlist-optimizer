class Playlist:
    name = ""
    songs = {}
    yt_id = ""

class Song:
    album = ""
    artist = ""
    name = ""
    duration_s = 0

    yt_id = ""
    spotify_id = ""
    # None if not downloaded, false if all downloaded, true if downloaded with error
    metadata_needs_review = None

    camelot_position = -1
    camelot_is_minor = None
    bpm = 0

    # A dict of user ratings (dict values) (+2 to -2) for each custom trait (dict keys)
    # TODO: Create a rating module that uses youtube-dl/yt-dlp and external player like ffmpeg to play portion/offset
    # Partial download: https://www.reddit.com/r/youtubedl/wiki/downloadingytsegments
    # Partial download: https://www.reddit.com/r/youtubedl/wiki/howdoidownloadpartsofavideo
    # YouTube DASH stream formats: https://gist.github.com/AgentOak/34d47c65b1d28829bb17c24c04a0096f
    user_ratings = {}

# A dictionary of user-ratable traits for each song.  
# Each key is the name of a category and each value is its definition.  
# Capitalize correctly for UI display.  
USER_RATINGS = {'Positivity' : 'Hopeful and optimistic, or regretful and pessimistic',
                'Drive' : 'Driving and forceful, or unhurried and gentle',
                'Presence' : 'Captivating and focused, or detached and distant',
                'Complexity' : 'Crowded and busy, or simple and manageable'}
