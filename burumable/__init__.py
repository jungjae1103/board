"""
부루마블 게임 모듈
Brumabl Game Module - 한국식 주사위 보드게임
"""

from .game_logic import BrumablGame
from .board import GameBoard
from .player import Player
from .piece_detector import PieceDetector
from .hand_gesture import HandGestureRecognizer
from .game_controller import GameController

__version__ = "1.0.0"
__all__ = [
    'BrumablGame',
    'GameBoard',
    'Player',
    'PieceDetector',
    'HandGestureRecognizer',
    'GameController'
]