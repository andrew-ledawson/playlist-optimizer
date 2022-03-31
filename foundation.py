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
    metadata_needs_review = False

    camelot_position = -1
    camelot_is_minor = None
    bpm = 0

    # A dict of user ratings (dict values) (+2 to -2) for each custom trait (dict keys)
    user_ratings = {}

# A dictionary of user-ratable traits for each song.  
# Each key is the name of a category and each value is its definition.  
# Capitalize correctly for UI display.  
USER_RATINGS = {'Positivity' : 'Hopeful and optimistic, or regretful and pessimistic',
                'Drive' : 'Driving and forceful, or unhurried and gentle',
                'Presence' : 'Captivating and focused, or detached and distant',
                'Complexity' : 'Crowded and busy, or simple and manageable'}
