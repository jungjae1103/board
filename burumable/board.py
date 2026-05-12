"""
게임판 관리 모듈
Game Board Management Module
"""

from enum import Enum
from typing import Optional, List
from dataclasses import dataclass


class SquareType(Enum):
    """칸의 종류"""
    GO = "go"  # 출발점 (0번)
    PROPERTY = "property"  # 부동산
    STATION = "station"  # 기차역 (5, 15, 25, 35)
    UTILITY = "utility"  # 공사 (12, 28)
    TAX = "tax"  # 세금 (4, 38)
    CORNER = "corner"  # 코너 (10: 감옥, 20: 공원, 30: 감옥, 40: 기업)
    EVENT = "event"  # 이벤트


@dataclass
class Square:
    """
    게임판 칸 클래스
    
    Attributes:
        position: 칸의 위치 (0~99)
        square_type: 칸의 종류
        name: 칸의 이름
        owner: 소유자 (None이면 미소유)
        purchase_price: 구매 가격
        base_rent: 기본 임대료
        level: 개발 수준 (1~5, 1=기본, 5=호텔)
    """
    position: int
    square_type: SquareType
    name: str
    owner: Optional[int] = None  # 플레이어 ID
    purchase_price: int = 0
    base_rent: int = 0
    level: int = 1
    
    def __post_init__(self):
        """칸 초기화 검증"""
        if not (0 <= self.position <= 99):
            raise ValueError("position은 0~99 사이의 값이어야 합니다")
    
    def get_rent(self) -> int:
        """
        현재 임대료 계산
        
        Returns:
            int: 임대료 (레벨에 따라 증가)
        """
        if self.owner is None or self.square_type != SquareType.PROPERTY:
            return 0
        
        # 레벨에 따른 임대료 배수 (1x, 2x, 3x, 4x, 5x)
        rent_multiplier = self.level
        return int(self.base_rent * rent_multiplier)
    
    def set_owner(self, player_id: int):
        """소유자 설정"""
        self.owner = player_id
    
    def set_level(self, level: int) -> bool:
        """
        개발 수준 설정
        
        Args:
            level: 개발 수준 (1~5)
            
        Returns:
            bool: 성공 여부
        """
        if 1 <= level <= 5:
            self.level = level
            return True
        return False
    
    def get_upgrade_cost(self) -> int:
        """다음 레벨 업그레이드 비용"""
        if self.level >= 5:
            return 0
        return int(self.purchase_price * 0.5) * (self.level)


class GameBoard:
    """
    게임판 클래스
    
    부루마블 게임판은 총 100칸으로 구성
    - GO (0): 출발점
    - 1~39: 부동산 및 기타 칸 (25칸 반복)
    - 40: 기업
    - 41~99: 부동산 및 기타 칸
    """
    
    BOARD_SIZE = 100
    
    def __init__(self):
        """게임판 초기화"""
        self.squares: List[Square] = []
        self._initialize_board()
    
    def _initialize_board(self):
        """게임판 칸 초기화"""
        # 기본 부루마블 보드 레이아웃
        board_layout = [
            # 형식: (position, type, name, purchase_price, base_rent)
            (0, SquareType.GO, "GO", 0, 0),
            (1, SquareType.PROPERTY, "명동", 100, 6),
            (2, SquareType.EVENT, "이벤트", 0, 0),
            (3, SquareType.PROPERTY, "남대문", 100, 6),
            (4, SquareType.TAX, "세금", 0, 0),
            (5, SquareType.STATION, "기차역1", 200, 50),
            (6, SquareType.PROPERTY, "종로", 120, 8),
            (7, SquareType.EVENT, "이벤트", 0, 0),
            (8, SquareType.PROPERTY, "청계천", 120, 8),
            (9, SquareType.PROPERTY, "강남", 140, 10),
            (10, SquareType.CORNER, "감옥", 0, 0),
            (11, SquareType.PROPERTY, "강남역", 160, 12),
            (12, SquareType.UTILITY, "공사1", 150, 25),
            (13, SquareType.PROPERTY, "삼성", 180, 14),
            (14, SquareType.PROPERTY, "현대", 180, 14),
            (15, SquareType.STATION, "기차역2", 200, 50),
            (16, SquareType.PROPERTY, "LG", 200, 16),
            (17, SquareType.EVENT, "이벤트", 0, 0),
            (18, SquareType.PROPERTY, "SK", 220, 18),
            (19, SquareType.PROPERTY, "네이버", 220, 18),
            (20, SquareType.CORNER, "공원", 0, 0),
            (21, SquareType.PROPERTY, "카카오", 240, 20),
            (22, SquareType.EVENT, "이벤트", 0, 0),
            (23, SquareType.PROPERTY, "쿠팡", 260, 22),
            (24, SquareType.PROPERTY, "배달의민족", 260, 22),
            (25, SquareType.STATION, "기차역3", 200, 50),
            (26, SquareType.PROPERTY, "우아한형제들", 280, 24),
            (27, SquareType.PROPERTY, "마켓컬리", 280, 24),
            (28, SquareType.UTILITY, "공사2", 150, 25),
            (29, SquareType.PROPERTY, "SSG닷컴", 300, 26),
            (30, SquareType.CORNER, "감옥", 0, 0),
            (31, SquareType.PROPERTY, "롯데", 320, 28),
            (32, SquareType.PROPERTY, "현대백화점", 320, 28),
            (33, SquareType.EVENT, "이벤트", 0, 0),
            (34, SquareType.PROPERTY, "신세계", 340, 30),
            (35, SquareType.STATION, "기차역4", 200, 50),
            (36, SquareType.EVENT, "이벤트", 0, 0),
            (37, SquareType.PROPERTY, "GS샵", 360, 32),
            (38, SquareType.TAX, "세금", 0, 0),
            (39, SquareType.PROPERTY, "11번가", 400, 34),
            (40, SquareType.CORNER, "기업", 0, 0),
            # 나머지는 기본 부동산으로 채우기
        ]
        
        # 보드 레이아웃에서 Square 객체 생성
        for position, square_type, name, purchase_price, base_rent in board_layout:
            square = Square(
                position=position,
                square_type=square_type,
                name=name,
                purchase_price=purchase_price,
                base_rent=base_rent
            )
            self.squares.append(square)
        
        # 나머지 칸 채우기 (41~99)
        for position in range(len(board_layout), self.BOARD_SIZE):
            square = Square(
                position=position,
                square_type=SquareType.PROPERTY,
                name=f"Property_{position}",
                purchase_price=100,
                base_rent=5
            )
            self.squares.append(square)
    
    def get_square(self, position: int) -> Optional[Square]:
        """특정 위치의 칸 반환"""
        
        Args:
            position: 칸의 위치
            
        Returns:
            Square: 해당 칸의 정보
        """
        if 0 <= position < self.BOARD_SIZE:
            return self.squares[position]
        return None
    
    def get_squares_by_type(self, square_type: SquareType) -> List[Square]:
        """특정 종류의 칸 반환"""
        
        Args:
            square_type: 칸의 종류
            
        Returns:
            List[Square]: 해당 종류의 칸 리스트
        """
        return [sq for sq in self.squares if sq.square_type == square_type]
    
    def get_properties_by_owner(self, player_id: int) -> List[Square]:
        """플레이어가 소유한 부동산 반환"""
        
        Args:
            player_id: 플레이어 ID
            
        Returns:
            List[Square]: 해당 플레이어의 부동산 리스트
        """
        return [sq for sq in self.squares 
                if sq.owner == player_id and sq.square_type == SquareType.PROPERTY]
    
    def get_board_state(self) -> dict:
        """게임판 상태 반환"""
        
        Returns:
            dict: 게임판 상태 정보
        """
        return {
            'board_size': self.BOARD_SIZE,
            'total_squares': len(self.squares),
            'properties': len(self.get_squares_by_type(SquareType.PROPERTY)),
            'stations': len(self.get_squares_by_type(SquareType.STATION)),
            'utilities': len(self.get_squares_by_type(SquareType.UTILITY))
        }