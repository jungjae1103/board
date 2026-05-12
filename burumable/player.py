"""
플레이어 관리 모듈
Player Management Module
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class PlayerColor(Enum):
    """플레이어 색상 정의"""
    RED = "red"
    BLUE = "blue"
    YELLOW = "yellow"
    GREEN = "green"


dataclass
class Player:
    """
    부루마블 게임 플레이어 클래스
    
    Attributes:
        player_id: 플레이어 고유 ID (0~3)
        name: 플레이어 이름
        color: 플레이어 색상
        position: 현재 위치 (0~99)
        money: 현재 보유 자금
        pieces: 소유한 부동산 리스트
        in_prison: 감옥 상태 여부
        prison_turns: 감옥에 있는 남은 턴 수
    """
    
    player_id: int
    name: str
    color: PlayerColor
    position: int = 0
    money: int = 2000  # 초기 자금
    pieces: list = field(default_factory=list)  # 소유 부동산
    in_prison: bool = False
    prison_turns: int = 0
    bankruptcy: bool = False
    
    def __post_init__(self):
        """플레이어 초기화 검증"""
        if not (0 <= self.player_id <= 3):
            raise ValueError("player_id는 0~3 사이의 정수여야 합니다")
        if self.money < 0:
            raise ValueError("초기 자금은 음수일 수 없습니다")
    
    def move(self, steps: int) -> bool:
        """
        플레이어 이동
        
        Args:
            steps: 이동 칸 수
            
        Returns:
            bool: GO 칸을 지났는지 여부 (통과 시 True)
        """
        if self.in_prison:
            return False
        
        old_position = self.position
        self.position = (self.position + steps) % 100
        
        # GO 칸을 지났는지 확��� (200만원 획득)
        if old_position + steps >= 100:
            self.add_money(200)
            return True
        return False
    
    def add_money(self, amount: int):
        """
        자금 증가
        
        Args:
            amount: 증가액
        """
        self.money += amount
        if self.money < 0:
            self.money = 0
    
    def subtract_money(self, amount: int) -> bool:
        """
        자금 차감
        
        Args:
            amount: 차감액
            
        Returns:
            bool: 차감 성공 여부
        """
        if self.money >= amount:
            self.money -= amount
            return True
        else:
            # 파산 처리
            self.bankruptcy = True
            self.money = 0
            return False
    
    def buy_property(self, property_id: int):
        """
        부동산 구매
        
        Args:
            property_id: 부동산 ID
        """
        if property_id not in self.pieces:
            self.pieces.append(property_id)
    
    def sell_property(self, property_id: int) -> bool:
        """
        부동산 판매
        
        Args:
            property_id: 부동산 ID
            
        Returns:
            bool: 판매 성공 여부
        """
        if property_id in self.pieces:
            self.pieces.remove(property_id)
            return True
        return False
    
    def enter_prison(self, turns: int = 3):
        """
        감옥에 입장
        
        Args:
            turns: 감옥에 있을 턴 수
        """
        self.in_prison = True
        self.prison_turns = turns
        self.position = 10  # 감옥 위치
    
    def leave_prison(self) -> bool:
        """
        감옥에서 탈출
        
        Returns:
            bool: 탈출 성공 여부
        """
        if self.in_prison:
            self.prison_turns -= 1
            if self.prison_turns <= 0:
                self.in_prison = False
                return True
        return False
    
    def get_property_count(self) -> int:
        """소유 부동산 개수 반환"""
        return len(self.pieces)
    
    def get_status(self) -> dict:
        """
        플레이어 상태 반환
        
        Returns:
            dict: 플레이어 상태 정보
        """
        return {
            'player_id': self.player_id,
            'name': self.name,
            'color': self.color.value,
            'position': self.position,
            'money': self.money,
            'properties': len(self.pieces),
            'in_prison': self.in_prison,
            'bankruptcy': self.bankruptcy
        }
    
    def __repr__(self) -> str:
        return f"Player({self.name}, ID={self.player_id}, Position={self.position}, Money={self.money})"