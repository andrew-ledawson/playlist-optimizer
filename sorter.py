import math
from foundation import *

# v1 of the score is simply 50% key and 50% ratings.  It has no awareness of previous "momentum".
def get_similarity_score_v1(song1 : Song, song2 : Song) -> float:
    # Key is 1.0 if identical, 0.8 if changing one unit over, etc. down to 0
    hops_between_keys = abs(song1.camelot_position - song2.camelot_position)
    if hops_between_keys > (CAMELOT_POSITIONS / 2):
        hops_between_keys = CAMELOT_POSITIONS - hops_between_keys
    if song1.camelot_is_minor != song2.camelot_is_minor:
        hops_between_keys = hops_between_keys + 1
    key_subscore = 1.0 - (0.2 * hops_between_keys)
    if key_subscore < 0.0:
        key_subscore = 0.0

    # Average all ratings.  For each rating, 1.0 if identical, 0.75 if one apart, etc.
    subscores = []
    for rating_key in USER_RATINGS:
        rating_difference = abs(song1.user_ratings[rating_key] - song2.user_ratings[rating_key])
        rating_score = 1.0 - (0.25 * rating_difference)
        if rating_score < 0.0:
            rating_score = 0.0
        subscores.append(rating_score)

    rating_subscore = sum(subscores) / len(subscores)
    return (key_subscore + rating_subscore) / 2

# TODO: load playlist
# TODO: validate metadata for songs
# TODO: execute solve
# TODO: put result into YTM