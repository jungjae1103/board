"""
부루마블 게임 로직 모듈
Brumabl Game Logic Module

부루마블의 기본 규칙을 구현합니다:
1. 2~4명의 플레이어가 참여
2. 주사위를 던져서 칸을 이동
3. 부동산을 구매하고 임대료 수집
4. 파산할 때까지 게임 진행
"""

import random
from enum import Enum
from typing import List, Optional, Dict, Tuple
from .player import Player, PlayerColor
from .board import GameBoard, SquareType


class GameState(Enum):
    """게임 상태"""
    WAITING = "waiting"  # 대기 중
    PLAYING = "playing"  # 게임 진행 중
    DICE_ROLLING = "dice_rolling"  # 주사위 던지는 중
    PLAYER_TURN = "player_turn"  # 플레이어 턴
    TRANSACTION = "transaction"  # 거래 진행 중
    GAME_OVER = "game_over"  # 게임 종료


class DiceResult:
    """주사위 결과"""
    def __init__(self, dice1: int, dice2: int):
        self.dice1 = dice1
        self.dice2 = dice2
        self.total = dice1 + dice2
        self.is_double = dice1 == dice2
    
    def __repr__(self):
        return f"DiceResult({self.dice1}, {self.dice2}, total={self.total}, double={self.is_double})"


class BrumablGame:
    """
    부루마블 게임 클래스
    
    Attributes:
        players: 플레이어 리스트
        board: 게임판
        current_player_index: 현재 플레이어 인덱스
        game_state: 게임 상태
        turn_count: 총 턴 수
        dice_history: 주사위 기록
    """
    
    MIN_PLAYERS = 2
    MAX_PLAYERS = 4
    INITIAL_MONEY = 2000
    GO_BONUS = 200
    
    def __init__(self, player_names: List[str]):
        """
        게임 초기화
        
        Args:
            player_names: 플레이어 이름 리스트
            
        Raises:
            ValueError: 플레이어 수가 2~4명이 아닐 경우
        """
        if not (self.MIN_PLAYERS <= len(player_names) <= self.MAX_PLAYERS):
            raise ValueError(f"플레이어 수는 {self.MIN_PLAYERS}~{self.MAX_PLAYERS}명이어야 합니다")
        
        self.players: List[Player] = self._initialize_players(player_names)
        self.board: GameBoard = GameBoard()
        self.current_player_index: int = 0
        self.game_state: GameState = GameState.WAITING
        self.turn_count: int = 0
        self.dice_history: List[DiceResult] = []
        self.transaction_log: List[Dict] = []
    
    def _initialize_players(self, player_names: List[str]) -> List[Player]:
        """
        플레이어 초기화
        
        Args:
            player_names: 플레이어 이름 리스트
            
        Returns:
            List[Player]: 초기화된 플레이어 리스트
        """
        colors = [PlayerColor.RED, PlayerColor.BLUE, PlayerColor.YELLOW, PlayerColor.GREEN]
        players = []
        
        for idx, name in enumerate(player_names):
            player = Player(
                player_id=idx,
                name=name,
                color=colors[idx],
                position=0,
                money=self.INITIAL_MONEY
            )
            players.append(player)
        
        return players
    
    def start_game(self):
        """게임 시작"""
        if self.game_state == GameState.WAITING:
            self.game_state = GameState.PLAYING
            self.current_player_index = random.randint(0, len(self.players) - 1)
            print(f"게임 시작! {self.current_player.name}부터 시작합니다.")
        else:
            raise RuntimeError("이미 게임이 시작되었습니다")
    
    def roll_dice(self) -> DiceResult:
        """
        주사위 던지기
        
        Returns:
            DiceResult: 주사위 결과 (1~6, 1~6)
        """
        if self.game_state != GameState.PLAYING:
            raise RuntimeError("게임이 진행 중이 아닙니다")
        
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        result = DiceResult(dice1, dice2)
        
        self.dice_history.append(result)
        self.game_state = GameState.DICE_ROLLING
        
        return result
    
    def move_player(self, steps: int) -> bool:
        """
        플레이어 이동
        
        Args:
            steps: 이동 칸 수
            
        Returns:
            bool: GO 칸을 지났는지 여부
        """
        if self.game_state != GameState.DICE_ROLLING:
            raise RuntimeError("주사위를 먼저 던져야 합니다")
        
        passed_go = self.current_player.move(steps)
        old_position = (self.current_player.position - steps) % 100
        
        # 착지한 칸의 효과 처리
        self._process_square_effect(self.current_player.position)
        
        self.game_state = GameState.PLAYER_TURN
        return passed_go
    
    def _process_square_effect(self, position: int):
        """
        칸에 착지했을 때의 효과 처리
        
        Args:
            position: 칸의 위치
        """
        square = self.board.get_square(position)
        if not square:
            return
        
        player = self.current_player
        
        # 칸의 종류에 따른 처리
        if square.square_type == SquareType.TAX:
            self._handle_tax(player, square)
        elif square.square_type == SquareType.CORNER and position == 10:
            # 감옥 칸에 착지한 경우
            if not player.in_prison:
                player.position = 10  # 감옥 위치로 이동
                print(f"{player.name}이 감옥에 들어갔습니다!")
        elif square.square_type == SquareType.PROPERTY and square.owner is not None:
            # 다른 플레이어의 부동산에 착지한 경우
            if square.owner != player.player_id:
                self._pay_rent(player, square)
    
    def _handle_tax(self, player: Player, square):
        """
        세금 처리
        
        Args:
            player: 세금을 낼 플레이어
            square: 세금 칸
        """
        tax_amount = 100  # 기본 세금
        if player.subtract_money(tax_amount):
            self.transaction_log.append({
                'type': 'tax',
                'player': player.name,
                'amount': tax_amount
            })
            print(f"{player.name}이 세금 {tax_amount}을 납부했습니다")
        else:
            print(f"{player.name}이 파산했습니다!")
    
    def _pay_rent(self, player: Player, square):
        """
        임대료 지불
        
        Args:
            player: 임대료를 낼 플레이어
            square: 소유한 부동산
        """
        rent = square.get_rent()
        owner = self.players[square.owner]
        
        if player.subtract_money(rent):
            owner.add_money(rent)
            self.transaction_log.append({
                'type': 'rent',
                'payer': player.name,
                'receiver': owner.name,
                'amount': rent,
                'property': square.name
            })
            print(f"{player.name}이 {owner.name}에게 {square.name} 임대료 {rent}을 지불했습니다")
        else:
            print(f"{player.name}이 임대료를 낼 수 없어 파산했습니다!")
    
    def buy_property(self, player_id: int, property_position: int) -> bool:
        """부동산 구매"""
        
        Args:
            player_id: 플레이어 ID
            property_position: 부동산 위치
            
        Returns:
            bool: 구매 성공 여부
        """
        if player_id != self.current_player.player_id:
            raise RuntimeError("현재 플레이어만 구매할 수 있습니다")
        
        square = self.board.get_square(property_position)
        if not square or square.square_type != SquareType.PROPERTY:
            return False
        
        if square.owner is not None:
            print(f"{square.name}은 이미 소유되었습니다")
            return False
        
        player = self.players[player_id]
        if player.money < square.purchase_price:
            print(f"{player.name}의 자금이 부족합니다")
            return False
        
        # 부동산 구매 처리
        player.subtract_money(square.purchase_price)
        square.set_owner(player_id)
        player.buy_property(property_position)
        
        self.transaction_log.append({
            'type': 'purchase',
            'player': player.name,
            'property': square.name,
            'price': square.purchase_price
        })
        
        print(f"{player.name}이 {square.name}을 {square.purchase_price}에 구매했습니다")
        return True
    
    def upgrade_property(self, player_id: int, property_position: int) -> bool:
        """부동산 업그레이드 (집/호텔 추가)"""
        
        Args:
            player_id: 플레이어 ID
            property_position: 부동산 위치
            
        Returns:
            bool: 업그레이드 성공 여부
        """
        square = self.board.get_square(property_position)
        if not square or square.owner != player_id:
            return False
        
        player = self.players[player_id]
        upgrade_cost = square.get_upgrade_cost()
        
        if player.money < upgrade_cost:
            print(f"{player.name}의 자금이 부족합니다")
            return False
        
        player.subtract_money(upgrade_cost)
        square.set_level(square.level + 1)
        
        self.transaction_log.append({
            'type': 'upgrade',
            'player': player.name,
            'property': square.name,
            'level': square.level,
            'cost': upgrade_cost
        })
        
        print(f"{player.name}이 {square.name}을 레벨 {square.level}로 업그레이드했습니다")
        return True
    
    def next_turn(self) -> bool:
        """다음 플레이어로 턴 넘기기"""
        
        Returns:
            bool: 게임이 계속 진행되는지 여부
        """
        # 파산한 플레이어 제거
        active_players = [p for p in self.players if not p.bankruptcy]
        
        if len(active_players) <= 1:
            self.game_state = GameState.GAME_OVER
            return False
        
        # 다음 플레이어 찾기
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        while self.players[self.current_player_index].bankruptcy:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
        
        self.turn_count += 1
        self.game_state = GameState.PLAYING
        return True
    
    def get_game_status(self) -> Dict:
        """게임 상태 반환"""
        
        Returns:
            Dict: 게임 상태 정보
        """
        return {
            'game_state': self.game_state.value,
            'turn_count': self.turn_count,
            'current_player': self.current_player.name,
            'players': [p.get_status() for p in self.players],
            'total_transactions': len(self.transaction_log)
        }
    
    def get_leaderboard(self) -> List[Dict]:
        """리더보드 (자산 기준 정렬)"""
        
        Returns:
            List[Dict]: 플레이어별 자산 정보
        """
        leaderboard = []
        for player in self.players:
            properties_value = sum(
                sq.purchase_price for sq in self.board.get_properties_by_owner(player.player_id)
            )
            total_assets = player.money + properties_value
            leaderboard.append({
                'name': player.name,
                'money': player.money,
                'properties': len(player.pieces),
                'properties_value': properties_value,
                'total_assets': total_assets,
                'status': '파산' if player.bankruptcy else '진행 중'
            })
        
        return sorted(leaderboard, key=lambda x: x['total_assets'], reverse=True)
    
    @property
    def current_player(self) -> Player:
        """현재 플레이어 반환"""
        return self.players[self.current_player_index]
    
    def __repr__(self) -> str:
        return f"BrumablGame(players={len(self.players)}, turn={self.turn_count})"