from foundation import *

import numpy, random, scipy.special

from ortools.init import pywrapinit
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

random.seed()
playlists_db, songs_cache = load_data_files()

selected_playlist = None
while selected_playlist is None:
    print("\nSelect a playlist to sort: ")
    selected_playlist = prompt_for_playlist(playlists_db)
original_songs = selected_playlist.song_ids.copy()
dedupliated_songs = [*set(original_songs)]
removed_song_count = len(original_songs) - len(dedupliated_songs)
if removed_song_count > 0:
    print(str(removed_song_count) + " songs will be removed from the sorted playlist for being duplicates")

def smoothstep(x, x_min=0, x_max=1, N=1):
    """A sigmoid/s-curve/clamping function that modifies some score.  As the score drops from 1.0, 
       the smoothed result will gently slope away but begins to ramp up, then becomes more gentle 
       again as it approaches 0.  N is the number of smoothing passes.  
       Taken from https://stackoverflow.com/a/45166120 """
    x = numpy.clip((x - x_min) / (x_max - x_min), 0, 1)
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
    # TODO later: consider ramping the score for point differences, e.g. 1 -> 0.9 -> 0.7 -> 0.4 -> 0
    user_rating_scores = []
    for rating_key in USER_RATINGS:
        rating_difference = abs(song1.user_ratings[rating_key] - song2.user_ratings[rating_key])
        rating_score = 1.0 - (0.25 * rating_difference)
        if rating_score < 0.0:
            rating_score = 0.0
        user_rating_scores.append(rating_score)
    user_rating_subscore = sum(user_rating_scores) / len(user_rating_scores)
    
    return (key_subscore * 0.2) + (bpm_subscore * 0.3) + (user_rating_subscore * 0.5)

def get_current_similarity_score(song_ids:list) -> float:
    num_songs = len(song_ids)
    total_score = 0.0
    for current_song_index in range(-1, len(song_ids) - 1):
        song_0 = songs_cache[song_ids[current_song_index]]
        song_1 = songs_cache[song_ids[current_song_index + 1]]
        score = score + get_similarity_score_v1(song_0, song_1)
    # Normalize score so it ranges between 0.0 and 1.0
    return score / num_songs

def generate_distance_matrix(song_ids:list) -> list:
    """
    Generates an n*n matrix of "distances" between songs in the playlist
    Invert of similarity score because farther is worse
    """
    song_list_length = len(song_ids)

    # Distance matrix should be less than 1 GiB so it can be easily handled
    ONE_GIBIBYTE = 1024 * 1024 * 1024
    FLOAT_SIZE_BYTES = 64 / 8
    if song_list_length * song_list_length > ONE_GIBIBYTE / FLOAT_SIZE_BYTES:
        raise Exception("Playlist is too large to easily sort, aborting. ")

    distance_list = []
    for first_node_index in range(song_list_length):
        distance_sublist = []
        for second_node_index in range(song_list_length):
            # Node already exists on the other side of the matrix; copy it
            if second_node_index < first_node_index:
                distance_sublist.append(distance_list[second_node_index][first_node_index])
            # Distance to self is 0
            elif second_node_index == first_node_index:
                distance_sublist.append(0.0)
            # Haven't calculated this distance yet
            else:
                first_song_id = song_ids[first_node_index]
                second_song_id = song_ids[second_node_index]
                # Similarity score needs to be inverted to become distance (since a distance of 0 is the most similar)
                distance_sublist.append(1.0 - get_similarity_score_v1(songs_cache[first_song_id], songs_cache[second_song_id]))
        distance_list.append(distance_sublist)
    # Solver needs a starting location, so add a dummy node before returning
    return [[0] * song_list_length] + distance_list

def solve_for_playlist_order(original_songs):
    """
    Do a traveling salesperson solve
    """
    # Disable distance matrix and just calculate on the fly to avoid n^2 memory usage
    """problem = {}
    problem['distance_matrix'] = generate_distance_matrix(dedupliated_songs)
    problem['num_vehicles'] = 1 # Only one playlist is being generated
    problem['depot'] = 0 # Start at dummy node"""

    manager = pywrapcp.RoutingIndexManager(len(dedupliated_songs) + 1, 1, 0) # 1 "vehicle" (1 result playlist), start at node 0

    def distance_callback(from_index, to_index):
        # Convert from routing variable Index to distance matrix NodeIndex.
        # This is poorly documented but the NodeIndex seems to just be the input index in the array.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        # Dummy 0th node is perfectly connected, so that it is transparent.
        if from_node == 0 or to_node == 0:
            return 0.0
        first_song_id = dedupliated_songs[from_node + 1]
        second_song_id = dedupliated_songs[to_node + 1]
        return 1.0 - get_similarity_score_v1(songs_cache[first_song_id], songs_cache[second_song_id])

    routing = pywrapcp.RoutingModel(manager)
    vertex_traversal_cost = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(vertex_traversal_cost)
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)

    print("Sorting playlist...")
    solution = routing.SolveWithParameters(search_parameters)
    if not solution:
        raise Exception("Could not sort playlist, aborting. ")


    routes = [] # 2d array of (output playlist, index number)
    for route_nbr in range(routing.vehicles()):
        index = routing.Start(route_nbr)
        route = [manager.IndexToNode(index)]
        while not routing.IsEnd(index):
            index = solution.Value(routing.NextVar(index))
            route.append(manager.IndexToNode(index))
        routes.append(route)

    return routes[0] # Only one playlist is being generated

sorted_indices = solve_for_playlist_order(dedupliated_songs)
sorted_song_ids = []
for song_number in sorted_indices:
    sorted_song_ids.append(dedupliated_songs[song_number - 1])
print("Playlist sorted. ")

if prompt_user_for_bool("Reorder existing playlist on YTM? "):
    if removed_song_count > 0:
        print("Duplicate songs will be at top of playlist. ")
    print("Beginning to reorder playlist...")
    # Moves each song to bottom of playlist, putting them all in order
    moved_song_count = 0
    for current_song_id in sorted_song_ids:
        # Print update every 10 changes since they take a while
        if moved_song_count % 10 == 9:
            print("Moving " + str(moved_song_count + 1) + "th song. ")
        original_index = original_songs.index(current_song_id)
        current_order_id = selected_playlist.order_ids[original_index]
        run_API_request(lambda: YTM.edit_playlist(selected_playlist.yt_id, moveItem=(current_order_id, None)))
        moved_song_count = moved_song_count + 1
    print("Playlist reordered.")

elif prompt_user_for_bool("Create new, sorted playlist on YTM? "):
    sorted_playlist_name = selected_playlist.name + " (sorted on " + time.ctime() + ")"
    playlist_id = run_API_request(lambda : YTM.create_playlist(title=sorted_playlist_name, video_ids=sorted_song_ids, description="Automatically created by sorter"), "to create a YouTube Music playlist with the sorted songs")
    print("Sorted playlist created at https://music.youtube.com/playlist?list=" + playlist_id)

# TODO: print results with song, key, and bpm.  print old and new lists with scores between each song

print("Sorter done, exiting.")
