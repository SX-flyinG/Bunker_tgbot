import json
import hmac
import hashlib
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command, CommandStart
from aiohttp import web

from config import WEBAPP_URL, ROOM_MIN, ROOM_MAX, BOT_TOKEN
from storage import storage, GamePhase, Player
from cards import deal_cards, get_random_scenario, get_random_bunker

router = Router()

# --- API HANDLERS (Для синхронизации с WebApp) ---

async def get_room_state(request):
    room_code = request.query.get("room")
    user_id = int(request.query.get("uid", 0))
    # В продакшене тут должна быть проверка initData!
    
    room = storage.get_room(room_code)
    if not room:
        return web.json_response({"error": "Room not found"}, status=404)
    
    return web.json_response(room.to_dict(user_id))

async def post_action(request):
    data = await request.json()
    action = data.get("action")
    user_id = int(data.get("uid"))
    room_code = data.get("room")
    
    room = storage.get_room(room_code)
    if not room: return web.json_response({"error": "No room"}, status=400)

    if action == "reveal_field":
        field = data.get("field")
        player = room.players.get(user_id)
        if player and player.card and field not in player.card.revealed:
            # Ограничение 1 раунда
            if room.phase == GamePhase.ROUND_1 and field != "profession":
                return web.json_response({"error": "Only profession in Round 1"}, status=400)
            player.card.revealed.append(field)
            
            # Авто-переход если все открылись (пример для раунда 1)
            all_opened = all(p.is_eliminated or "profession" in p.card.revealed for p in room.players.values())
            if room.phase == GamePhase.ROUND_1 and all_opened:
                room.phase = GamePhase.ROUND_2
                room.round_num = 2

    elif action == "start_game" and user_id == room.host_id:
        if len(room.players) >= 2: # Для тестов снизил
            room.scenario = get_random_scenario()
            room.bunker = get_random_bunker()
            for p in room.players.values():
                p.card = deal_cards()
            room.phase = GamePhase.ROUND_1
            room.round_num = 1

    return web.json_response({"ok": True})

# --- BOT COMMANDS ---

def get_main_kb(room_code, user_id):
    url = f"{WEBAPP_URL}?room={room_code}&uid={user_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="☢ ОТКРЫТЬ ТЕРМИНАЛ", web_app=WebAppInfo(url=url))]
    ])

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "<b>☢ ДОБРО ПОЖАЛОВАТЬ В БУНКЕР</b>\n\nСоздай комнату или войди по коду.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать", callback_data="create_room")],
            [InlineKeyboardButton(text="🚪 Войти", callback_data="join_prompt")]
        ])
    )

@router.callback_query(F.data == "create_room")
async def cb_create(call: CallbackQuery):
    room = storage.create_room(call.from_user.id, 10)
    # Хост автоматически заходит
    room.players[call.from_user.id] = Player(
        user_id=call.from_user.id,
        username=call.from_user.username,
        first_name=call.from_user.first_name
    )
    await call.message.answer(f"Комната <code>{room.code}</code> создана!", reply_markup=get_main_kb(room.code, call.from_user.id))
    await call.answer()

@router.message(Command("join"))
async def cmd_join(message: Message):
    args = message.text.split()
    if len(args) < 2: return await message.answer("Введи /join КОД")
    code = args[1].upper()
    room = storage.get_room(code)
    if not room: return await message.answer("Нет такой комнаты")
    
    room.players[message.from_user.id] = Player(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )
    await message.answer(f"Ты вошел в {code}!", reply_markup=get_main_kb(code, message.from_user.id))
