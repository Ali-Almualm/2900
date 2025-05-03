import math

K_FACTOR = 32 # K-factor determines the maximum Elo change per match. Adjust as needed.

def calculate_expected_score(player_rating, opponent_rating):
    """Calculates the expected score (probability of winning) for a player."""
    return 1 / (1 + math.pow(10, (opponent_rating - player_rating) / 400))

def update_elo_1v1(winner_rating, loser_rating):
    """Calculates the new Elo ratings for a 1v1 match."""
    expected_winner = calculate_expected_score(winner_rating, loser_rating)
    expected_loser = calculate_expected_score(loser_rating, winner_rating)

    new_winner_rating = winner_rating + K_FACTOR * (1 - expected_winner)
    new_loser_rating = loser_rating + K_FACTOR * (0 - expected_loser)

    return round(new_winner_rating), round(new_loser_rating)

def update_elo_2v2(team1_ratings, team2_ratings, team1_won):
    """
    Calculates new Elo ratings for a 2v2 match.
    team1_ratings: List/tuple of Elo ratings for team 1 players [player1_elo, player2_elo]
    team2_ratings: List/tuple of Elo ratings for team 2 players [player3_elo, player4_elo]
    team1_won: Boolean, True if team 1 won, False if team 2 won (handle draws separately if needed)
    Returns: Dictionary mapping player_id (or index) to new rating (needs adaptation based on how you pass player info)
             Or simply return the new ratings in lists: ([new_p1, new_p2], [new_p3, new_p4])
    """
    if not team1_ratings or not team2_ratings:
         return None # Or handle error appropriately

    avg_team1_rating = sum(team1_ratings) / len(team1_ratings)
    avg_team2_rating = sum(team2_ratings) / len(team2_ratings)

    expected_team1 = calculate_expected_score(avg_team1_rating, avg_team2_rating)
    expected_team2 = calculate_expected_score(avg_team2_rating, avg_team1_rating)

    score_team1 = 1 if team1_won else 0
    score_team2 = 0 if team1_won else 1

    # Calculate the change based on average ratings
    change_team1 = K_FACTOR * (score_team1 - expected_team1)
    change_team2 = K_FACTOR * (score_team2 - expected_team2)

    # Apply the *same* change to each player on the team
    new_team1_ratings = [round(r + change_team1) for r in team1_ratings]
    new_team2_ratings = [round(r + change_team2) for r in team2_ratings]

    return new_team1_ratings, new_team2_ratings

def update_elo_ffa(player_ratings_ranks):
    """
    Calculates new Elo ratings for a Free-for-All match.
    player_ratings_ranks: List of tuples [(player_id_A, rating_A, rank_A), (player_id_B, rating_B, rank_B), ...]
                          Rank 1 is the winner.
    Returns: Dictionary mapping player_id to new rating {player_id_A: new_rating_A, ...}
    """
    num_players = len(player_ratings_ranks)
    if num_players < 2:
        return {} # Cannot calculate Elo for less than 2 players

    new_ratings = {pid: rating for pid, rating, rank in player_ratings_ranks} # Start with current ratings
    total_changes = {pid: 0 for pid, rating, rank in player_ratings_ranks}

    # Iterate through all unique pairs of players
    for i in range(num_players):
        for j in range(i + 1, num_players):
            p1_id, p1_rating, p1_rank = player_ratings_ranks[i]
            p2_id, p2_rating, p2_rank = player_ratings_ranks[j]

            # Determine winner/loser/draw based on rank for this pair
            score1 = 0.5 # Assume draw initially
            if p1_rank < p2_rank:
                score1 = 1.0 # Player 1 wins
            elif p2_rank < p1_rank:
                score1 = 0.0 # Player 1 loses

            score2 = 1.0 - score1

            # Calculate expected scores for this pair
            expected1 = calculate_expected_score(p1_rating, p2_rating)
            expected2 = calculate_expected_score(p2_rating, p1_rating)

            # Calculate Elo change for this pair interaction
            # Divide K-factor by (num_players - 1) to moderate the total change from multiple pairings
            adjusted_k = K_FACTOR / (num_players - 1)
            change1 = adjusted_k * (score1 - expected1)
            change2 = adjusted_k * (score2 - expected2)

            # Accumulate changes for each player
            total_changes[p1_id] += change1
            total_changes[p2_id] += change2

    # Apply the total accumulated changes to get the final new ratings
    for pid, change in total_changes.items():
        new_ratings[pid] = round(new_ratings[pid] + change)

    return new_ratings

# --- Helper to get the correct rating field name ---
def get_elo_field_name(activity_type):
    if activity_type == 'pool':
        return 'ranking_pool'
    elif activity_type == 'switch':
         return 'ranking_switch'
    elif activity_type == 'table_tennis':
         return 'ranking_table_tennis'
    else:
         return None # Or raise error for invalid type
