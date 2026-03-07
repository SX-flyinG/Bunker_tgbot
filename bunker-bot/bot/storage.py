"""
storage.py — хранилище состояний игры (in-memory)
Для продакшена можно заменить на Redis.
"""
import random
import string
from typing import Dict, Optional
from dataclasses import dataclass, field
from enum import Enum


class GamePhase(str, Enum):
    LOBBY = "lobby"          # Ожидание игроков"""
storage.py — хранилище состояний игры (in-memory)

import random
import string
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum

class GamePhase(str, Enum):
    LOBBY = "lobby"          # Ожидание игроков
    ROUND_1 = "round_1"     # Раунд 1: только профессия
    ROUND_2 = "round_2"     # Раунд 2: любая карта
    VOTING = "voting"        # Голосование
    ROUND_N = "round_n"     # Раунды 3+
    FINISHED = "finished"   # Игра завершена

@dataclass
class PlayerCard:
    profession: str
    biology: str
    health: str
    baggage: str
    fact1: str
    fact2: str
    special: str
    revealed: List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "profession": self.profession,
            "biology": self.biology,
            "health": self.health,
            "baggage": self.baggage,
            "fact1": self.fact1,
            "fact2": self.fact2,
            "special": self.special,
            "revealed": self.revealed
        }

@dataclass
class Player:
    user_id: int
    username: str
    first_name: str
    card: Optional[PlayerCard] = None
    is_eliminated: bool = False
    votes_received: int = 0
    has_voted: bool = False

    def to_dict(self, is_me: bool):
        # Если это не наш профиль и игрок жив, скрываем нераскрытые карты
        card_data = None
        if self.card:
            full_card = self.card.to_dict()
            if is_me or self.is_eliminated:
                card_data = full_card
            else:
                # Скрываем то, что еще не открыто публично
                card_data = {k: (v if k in self.card.revealed else "🔒 СКРЫТО") for k, v in full_card.items()}
                card_data["revealed"] = self.card.revealed
        
        return {
            "id": self.user_id,
            "name": self.first_name,
            "username": self.username,
            "is_eliminated": self.is_eliminated,
            "card": card_data,
            "votes": self.votes_received
        }

@dataclass
class Room:
    code: str
    host_id: int
    max_players: int
    players: Dict[int, Player] = field(default_factory=dict)
    phase: GamePhase = GamePhase.LOBBY
    round_num: int = 0
    scenario: Optional[dict] = None
    bunker: Optional[dict] = None
    votes: Dict[int, int] = field(default_factory=dict)

    def to_dict(self, viewer_id: int):
        return {
            "code": self.code,
            "host_id": self.host_id,
            "phase": self.phase,
            "round_num": self.round_num,
            "scenario": self.scenario,
            "bunker": self.bunker,
            "players": [p.to_dict(p.user_id == viewer_id) for p in self.players.values()],
            "is_host": viewer_id == self.host_id
        }

class Storage:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def generate_code(self) -> str:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            if code not in self.rooms: return code

    def create_room(self, host_id: int, max_players: int) -> Room:
        code = self.generate_code()
        room = Room(code=code, host_id=host_id, max_players=max_players)
        self.rooms[code] = room
        return room

    def get_room(self, code: str) -> Optional[Room]:
        return self.rooms.get(code)

    def find_room_by_player(self, user_id: int) -> Optional[Room]:
        for room in self.rooms.values():
            if user_id in room.players: return room
        return None

storage = Storage()
    ROUND_1 = "round_1"     # Раунд 1: только профессия открыта
    ROUND_2 = "round_2"     # Раунд 2: открыть любую карту
    VOTING = "voting"        # Голосование (с раунда 2)
    ROUND_N = "round_n"     # Раунды 3+
    FINISHED = "finished"   # Игра завершена


@dataclass
class PlayerCard:
    profession: str
    biology: str        # пол + возраст
    health: str
    baggage: str
    fact1: str
    fact2: str
    special: str
    # Какие карты уже открыты публично (список ключей)
    revealed: list = field(default_factory=list)


@dataclass
class Player:
    user_id: int
    username: str
    first_name: str
    card: Optional[PlayerCard] = None
    is_eliminated: bool = False
    votes_received: int = 0


@dataclass
class Room:
    code: str
    host_id: int
    max_players: int
    players: Dict[int, Player] = field(default_factory=dict)
    phase: GamePhase = GamePhase.LOBBY
    round_num: int = 0
    apocalypse: Optional[dict] = None
    bunker: Optional[dict] = None
    votes: Dict[int, int] = field(default_factory=dict)  # voter_id -> target_id
    chat_id: Optional[int] = None  # групповой чат, если есть


class Storage:
    def __init__(self):
        self.rooms: Dict[str, Room] = {}

    def generate_code(self) -> str:
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
            if code not in self.rooms:
                return code

    def create_room(self, host_id: int, max_players: int) -> Room:
        code = self.generate_code()
        room = Room(code=code, host_id=host_id, max_players=max_players)
        self.rooms[code] = room
        return room

    def get_room(self, code: str) -> Optional[Room]:
        return self.rooms.get(code.upper())

    def find_room_by_player(self, user_id: int) -> Optional[Room]:
        for room in self.rooms.values():
            if user_id in room.players:
                return room
        return None

    def delete_room(self, code: str):
        self.rooms.pop(code, None)


storage = Storage()
