from foundation import *

def get_similarity_score_v1(song1 : Song, song2 : Song) -> float:
    """Computes the similarity of songs and returns a score between 1.0 and 0.0.
       The similarity score is 35% key, 30% BPM, and 35% user ratings.
       Score v1 does not consider the "momentum" of previous changes that would
       allow changes to continue in a similar direction."""

    # Key subscore is 1.0 if identical, 0.8 if changing one unit over, etc.
    hops_between_keys = abs(song1.camelot_position - song2.camelot_position)
    if hops_between_keys > (CAMELOT_POSITIONS / 2):
        hops_between_keys = CAMELOT_POSITIONS - hops_between_keys
    if song1.camelot_is_minor != song2.camelot_is_minor:
        hops_between_keys = hops_between_keys + 1
    key_subscore = 1.0 - (0.2 * hops_between_keys)
    if key_subscore < 0.0:
        key_subscore = 0.0

    # TODO: BPM subscore
    # As BPMs diverge, score reduces in a ramping-up fashion towards 0.0
    # Make sure to support wrapping BPM around from 180 back to 90

    # Average user ratings into a subscore.  For each rating, 1.0 if identical, 0.75 if one apart, etc.
    user_rating_scores = []
    for rating_key in USER_RATINGS:
        rating_difference = abs(song1.user_ratings[rating_key] - song2.user_ratings[rating_key])
        rating_score = 1.0 - (0.25 * rating_difference)
        if rating_score < 0.0:
            rating_score = 0.0
        user_rating_scores.append(rating_score)
    user_rating_subscore = sum(user_rating_scores) / len(user_rating_scores)
    
    return (key_subscore * 0.35) + (user_rating_subscore * 0.35)

# TODO: load playlist
# TODO: validate metadata for songs
# TODO: execute solve
# TODO: put result into YTM