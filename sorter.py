from textwrap import wrap
from foundation import *

import numpi, random, scipy

random.seed()
playlists_db, songs_db = load_data_files()

selected_playlist = None
while selected_playlist is None:
    print("\nSelect a playlist to sort: ")
    selected_playlist = prompt_for_playlist(playlists_db)
original_songs = sorted_songs = selected_playlist.song_ids

def smoothstep(x, x_min=0, x_max=1, N=1):
    """A sigmoid/s-curve/clamping function that modifies some score.  As the score drops from 1.0, 
       the smoothed result will gently slope away but begins to ramp up, then becomes more gentle 
       again as it approaches 0.  N is the number of smoothing passes.  """
    # Taken from https://stackoverflow.com/a/45166120
    x = numpi.clip((x - x_min) / (x_max - x_min), 0, 1)
    result = 0
    for n in range(0, N + 1):
         result += scipy.special.comb(N + n, n) * scipy.special.comb(2 * N + 1, N - n) * (-x) ** n
    result *= x ** (N + 1)
    return result

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

    # BPM subscore is the difference between BPMs, smoothed
    lower_bpm = min(song1.bpm, song2.bpm)
    higher_bpm = max(song1.bpm, song2.bpm)
    bpm_difference = higher_bpm - lower_bpm
    # Since BPMs are normalized in a range, consider doubling the lower BPM to match the higher BPM
    # Divide by 1.5 since we could have used higher_bpm/2 instead, so we'll average the difference between them
    # TODO later: consider increasing the divisor to punish wrapping around
    wraparound_bpm_difference = (lower_bpm * 2 - higher_bpm) / 1.5
    bpm_difference = min([bpm_difference, wraparound_bpm_difference])
    # Do smoothstep to keep give similar BPMs a higher score
    # TODO later: consider a curve that doesn't smooth out towards 0, maybe by only using half of the smoothstep graph
    max_bpm_difference = (MAX_BPM - MIN_BPM) / 2
    bpm_subscore = (max_bpm_difference - smoothstep(bpm_difference, x_min=0, x_max=max_bpm_difference)) / max_bpm_difference

    # Average all user ratings into a subscore.  Each is 1.0 if identical, 0.75 if one apart, etc.
    user_rating_scores = []
    for rating_key in USER_RATINGS:
        rating_difference = abs(song1.user_ratings[rating_key] - song2.user_ratings[rating_key])
        rating_score = 1.0 - (0.25 * rating_difference)
        if rating_score < 0.0:
            rating_score = 0.0
        user_rating_scores.append(rating_score)
    user_rating_subscore = sum(user_rating_scores) / len(user_rating_scores)
    
    return (key_subscore * 0.35) + (bpm_subscore * 0.3) + (user_rating_subscore * 0.35)

# TODO: load playlist
# TODO: validate metadata for songs
# TODO: do scipy solve, probably basinhopping
# TODO: avoid strongly connected vertices?
def solve_for_playlist_order():
    starting_playlist_order = []
    def get_current_optimality(current_playlist : list[Song]):
        # Gets total optimality score of the current playlist order, inverted so lowest is best
        # We will treat playlists as a loop, i.e. the last song will loop around to the first
        score = 0
        for current_song_index in range(-1, len(current_playlist) - 1):
            score = score + get_similarity_score_v1(current_playlist[current_song_index], current_playlist[current_song_index + 1])
        return float(len(original_songs)) - score
    def take_step(stepsize, current_playlist : list[Song]):
        # Takes a step (i.e. generates a new solution) by swapping two songs
        # "Step size" determines how far a song can be swapped in the playlist
        # Randomly select a song
        swap_song_source_index = random.randint(0, len(current_playlist) - 1)
        # Move it a random distance backward or forward
        swap_song_dest_index = swap_song_source_index + random.randint(-1 * int(stepsize), int(stepsize))
        # TODO: fix out of bounds indices
        # Do the swap
        current_playlist[swap_song_dest_index], current_playlist[swap_song_source_index] = current_playlist[swap_song_source_index], current_playlist[swap_song_dest_index]
    # Starting/maximum step size will be len(playlist)/2
    # TODO: ensure step size doesn't drop below 1.0
    pass

sorted_playlist_name = selected_playlist.name + " (sorted on " + time.ctime*() + ")"
playlist_id = run_API_request(lambda : YTM.create_playlist(title=sorted_playlist_name, video_ids=sorted_songs), "to create a YouTube Music playlist with the sorted songs")
print("Sorted playlist created at https://music.youtube.com/playlist?list=" + playlist_id)

# TODO: support modifying existing playlist
# need to do minimum number of moves to transform existing playlist into new order
# need to get setVideoId of every song to enable sorting (it's next to the song metadata in the YTM response)
