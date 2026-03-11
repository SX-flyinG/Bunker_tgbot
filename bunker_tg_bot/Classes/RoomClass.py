from dataclasses import dataclass, field
from typing import Dict, Optional

from Classes.GamePhaseClass import GamePhase
from Classes.PlayersClasses import Player


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