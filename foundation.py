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
    # TODO: Update collector to support this change
    metadata_needs_review = None

    camelot_position = -1
    camelot_is_minor = None
    bpm = 0

    # A dict of user ratings (dict values) (+2 to -2) for each custom trait (dict keys)
    # TODO: Create a rating program that uses youtube-dl/yt-dlp and some external player to play portions of song 
    # https://www.reddit.com/r/youtubedl/wiki/downloadingytsegments
    # https://www.reddit.com/r/youtubedl/wiki/howdoidownloadpartsofavideo
    user_ratings = {}

# A dictionary of user-ratable traits for each song.  
# Each key is the name of a category and each value is its definition.  
# Capitalize correctly for UI display.  
USER_RATINGS = {'Positivity' : 'Hopeful and optimistic, or regretful and pessimistic',
                'Drive' : 'Driving and forceful, or unhurried and gentle',
                'Presence' : 'Captivating and focused, or detached and distant',
                'Complexity' : 'Crowded and busy, or simple and manageable'}
