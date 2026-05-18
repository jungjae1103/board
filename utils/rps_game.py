def determine_rps_winner(player_moves):
    """
    Args:
        player_moves (dict): {'player1': 'rock', 'player2': 'scissors', ...}
            (rock, paper, scissors 중 하나)
    Returns:
        dict: {
            'winner': 'player2',           # 대표 승자 player key / 비기면 None
            'winners': [...],              # 승자 목록
            'losers': [...],               # 패자 목록
            'order': [...],                # 승자(들) 먼저, 패자(들) 뒤
            'is_tie': True/False           # 비김 여부
        }
    """
    players = list(player_moves.keys())
    moves = list(player_moves.values())
    move_set = set(moves)

    # (1) 모두 같은 손 or 세 종류 모두 있으면 무승부(tie)
    if len(move_set) == 1 or len(move_set) == 3:
        return {
            'winner': None,
            'winners': [],
            'losers': [],
            'order': players,
            'is_tie': True
        }

    # (2) 각 조합 케이스별 이기는 손 결정
    win_move = None
    if move_set == {"rock", "scissors"}:
        win_move = "rock"
    elif move_set == {"scissors", "paper"}:
        win_move = "scissors"
    elif move_set == {"paper", "rock"}:
        win_move = "paper"
    else:
        # 예외 fallback (발생하지 않음)
        return {
            'winner': None,
            'winners': [],
            'losers': [],
            'order': players,
            'is_tie': True
        }

    # (3) 승리/패배 플레이어 추출
    winners = [k for k, v in player_moves.items() if v == win_move]
    losers = [k for k in players if k not in winners]
    order = winners + losers
    winner = winners[0] if winners else None

    return {
        'winner': winner,
        'winners': winners,
        'losers': losers,
        'order': order,
        'is_tie': False
    }
