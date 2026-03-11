from enum import Enum

class GamePhase(str, Enum):
    LOBBY      = "lobby"
    ROUND_1    = "round_1"
    ROUND_2    = "round_2"
    DISCUSSION = "discussion"   # ← фаза обсуждения перед голосованием
    VOTING     = "voting"
    ROUND_N    = "round_n"
    FINISHED   = "finished"