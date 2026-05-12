"""
게임 컨트롤러 모듈
Game Controller Module

모든 게임 컴포넌트를 통합하여 게임을 관리합니다.
- BrumablGame (게임 로직)
- GameBoard (게임판)
- Player (플레이어)
- PieceDetector (YOLO 말 탐지)
- HandGestureRecognizer (손 인식)
"""

from typing import List, Optional, Dict, Callable
import logging
from .game_logic import BrumablGame, GameState, DiceResult
from .board import GameBoard
from .player import Player
from .piece_detector import PieceDetector
from .hand_gesture import HandGestureRecognizer


# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GameController:
    """
    게임 컨트롤러 클래스
    
    SULIVAN 시스템과 부루마블 게임을 연결하는 역할을 합니다.
    
    Attributes:
        game: BrumablGame 인스턴스
        piece_detector: PieceDetector 인스턴스
        hand_recognizer: HandGestureRecognizer 인스턴스
        callbacks: 콜백 함수 딕셔너리
    """
    
    def __init__(self, player_names: List[str]):
        """
        GameController 초기화
        
        Args:
            player_names: 플레이어 이름 리스트 (2~4명)
        """
        logger.info(f"Initializing GameController with players: {player_names}")
        
        self.game = BrumablGame(player_names)
        self.piece_detector = PieceDetector()
        self.hand_recognizer = HandGestureRecognizer()
        self.callbacks: Dict[str, List[Callable]] = {
            'on_game_start': [],
            'on_turn_start': [],
            'on_dice_roll': [],
            'on_player_move': [],
            'on_property_buy': [],
            'on_turn_end': [],
            'on_game_over': []
        }
        self.is_running = False
        logger.info("GameController initialized successfully")
    
    def start_game(self):
        """게임 시작"""
        logger.info("Starting game...")
        self.game.start_game()
        self.is_running = True
        self._trigger_callback('on_game_start')
        logger.info("Game started")
    
    def process_turn(self):
        """
        현재 플레이어의 턴 처리
        
        Returns:
            Dict: 턴 처리 결과
        """
        if not self.is_running or self.game.game_state == GameState.GAME_OVER:
            return {'success': False, 'message': 'Game is not running'}
        
        player = self.game.current_player
        logger.info(f"Processing turn for {player.name}")
        self._trigger_callback('on_turn_start')
        
        # 주사위 굴리기
        dice_result = self.game.roll_dice()
        logger.info(f"Dice rolled: {dice_result}")
        self._trigger_callback('on_dice_roll', dice_result)
        
        # 플레이어 이동
        self.game.move_player(dice_result.total)
        logger.info(f"{player.name} moved to position {player.position}")
        self._trigger_callback('on_player_move', player.position)
        
        # 착지한 칸 처리
        square = self.game.board.get_square(player.position)
        result = {
            'success': True,
            'dice': dice_result,
            'new_position': player.position,
            'square_name': square.name if square else 'Unknown',
            'player': player.get_status()
        }
        
        return result
    
    def handle_property_purchase(self, player_id: int, property_position: int) -> bool:
        """
        부동산 구매 처리
        
        Args:
            player_id: 플레이어 ID
            property_position: 부동산 위치
            
        Returns:
            bool: 구매 성공 여부
        """
        success = self.game.buy_property(player_id, property_position)
        if success:
            self._trigger_callback('on_property_buy', property_position)
            logger.info(f"Property {property_position} purchased by player {player_id}")
        return success
    
    def end_turn(self) -> bool:
        """
        현재 턴 종료 및 다음 플레이어로 이동
        
        Returns:
            bool: 게임이 계속 진행되는지 여부
        """
        success = self.game.next_turn()
        
        if success:
            logger.info(f"Next player: {self.game.current_player.name}")
            self._trigger_callback('on_turn_end')
        else:
            self.is_running = False
            logger.info("Game over!")
            self._trigger_callback('on_game_over')
        
        return success
    
    def process_hand_gesture(self, frame) -> Dict:
        """
        손 제스처 인식 및 처리
        
        Args:
            frame: 입력 프레임
            
        Returns:
            Dict: 인식된 제스처 정보
        """
        if not self.hand_recognizer.is_initialized:
            self.hand_recognizer.initialize()
        
        hands = self.hand_recognizer.detect_hands(frame)
        
        return {
            'hands_detected': len(hands),
            'hands': hands
        }
    
    def process_piece_detection(self, frame) -> Dict:
        """
        게임 말 탐지
        
        Args:
            frame: 입력 프레임
            
        Returns:
            Dict: 탐지된 말 정보
        """
        if not self.piece_detector.is_initialized:
            self.piece_detector.initialize()
        
        pieces = self.piece_detector.detect_pieces(frame)
        
        return {
            'pieces_detected': len(pieces),
            'pieces': pieces
        }
    
    def get_game_status(self) -> Dict:
        """현재 게임 상태 반환"""
        return self.game.get_game_status()
    
    def get_leaderboard(self) -> List[Dict]:
        """현재 리더보드 반환"""
        return self.game.get_leaderboard()
    
    def register_callback(self, event: str, callback: Callable):
        """
        콜백 함수 등록
        
        Args:
            event: 이벤트 이름
            callback: 콜백 함수
        """
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            logger.info(f"Callback registered for event: {event}")
        else:
            logger.warning(f"Unknown event: {event}")
    
    def _trigger_callback(self, event: str, *args, **kwargs):
        """
        콜백 함수 실행
        
        Args:
            event: 이벤트 이름
            *args: 콜백에 전달할 위치 인자
            **kwargs: 콜백에 전달할 키워드 인자
        """
        if event in self.callbacks:
            for callback in self.callbacks[event]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error executing callback for {event}: {e}")
    
    def reset_game(self):
        """게임 리셋"""
        logger.info("Resetting game...")
        self.is_running = False
        player_names = [p.name for p in self.game.players]
        self.game = BrumablGame(player_names)
        logger.info("Game reset completed")
    
    def __repr__(self) -> str:
        return f"GameController(running={self.is_running}, game={self.game})"