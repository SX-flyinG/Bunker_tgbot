from dataclasses import dataclass, field
from typing import Optional


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

