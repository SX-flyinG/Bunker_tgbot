import random
import string
from typing import Dict, Optional

from Classes.RoomClass import Room


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