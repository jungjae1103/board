def determine_rps_winner(player_moves):
    """
    Args:
        player_moves (dict): {'player1': 'rock', 'player2': 'scissors', ...}
            (rock, paper, scissors 중 하나)
    Returns:
        dict: {
            'winner': 'player2',           # 승자 player key (ex: "player2") / 비기면 None
            'order': [...],                # 승자(들) 먼저, 나머지 패자는 뒤에. 예: ["player2", "player1", ...]
            'is_tie': True/False           # 비김 여부
        }
    """
    moves = list(player_moves.values())
    move_set = set(moves)
    # (1) 모두 같은 손 or 세 종류 모두 있으면 무승부(tie)
    if len(move_set) == 1 or len(move_set) == 3:
        return {'winner': None, 'order': list(player_moves.keys()), 'is_tie': True}

    # (2) 각 조합 케이스별 이기는 손 결정
    win_move = None
    if move_set == {"rock", "scissors"}:
        win_move = "rock"
    elif move_set == {"scissors", "paper"}:
        win_move = "scissors"
    elif move_set == {"paper", "rock"}:
        win_move = "paper"
    else:
        # 예외 fallback (사실상 발생X)
        return {'winner': None, 'order': list(player_moves.keys()), 'is_tie': True}

    # (3) 승리 무브 낸 플레이어 모두 추출
    winners = [k for k, v in player_moves.items() if v == win_move]
    # (4) order: 승자(들) 앞, 나머지 뒤
    order = winners + [k for k in player_moves if k not in winners]
    # (5) winner는 다수일 경우 첫 사람 return(순서의미)
    winner = winners[0] if winners else None

    return {'winner': winner, 'order': order, 'is_tie': False}