"""
RouteHandler.py — все команды и колбэки Telegram-бота
"""
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import Command, CommandStart
from aiogram.exceptions import TelegramBadRequest

from Classes.GamePhaseClass import GamePhase
from Classes.PlayersClasses import Player
from Classes.StorageClass import storage
from Methods.RouteMethods import deal_cards, get_random_scenario, get_random_bunker, get_random_secret

router = Router()

# ─────────────────────────────────────────────
# CARD FIELDS
# ─────────────────────────────────────────────

CARD_FIELDS = [
    ("profession", "👔", "Профессия"),
    ("biology",    "🧬", "Биология"),
    ("health",     "❤️", "Здоровье"),
    ("baggage",    "🎒", "Багаж"),
    ("fact1",      "📌", "Факт 1"),
    ("fact2",      "📌", "Факт 2"),
    ("special",    "⚡", "Особое условие"),
]


# ─────────────────────────────────────────────
# MESSAGE TRACKER
# ─────────────────────────────────────────────

def track_msg(room, user_id: int, msg_id: int):
    if not hasattr(room, 'tracked_messages'):
        room.tracked_messages = {}
    room.tracked_messages.setdefault(user_id, []).append(msg_id)


async def delete_tracked_messages(bot, room):
    if not hasattr(room, 'tracked_messages'):
        return
    for uid, msg_ids in room.tracked_messages.items():
        for msg_id in msg_ids:
            try:
                await bot.delete_message(uid, msg_id)
            except Exception:
                pass
    room.tracked_messages = {}


def track_chat_msg(room, user_id: int, msg_id: int):
    if not hasattr(room, 'chat_messages'):
        room.chat_messages = {}
    room.chat_messages.setdefault(user_id, []).append(msg_id)


async def delete_chat_messages(bot, room):
    if not hasattr(room, 'chat_messages'):
        return
    for uid, msg_ids in room.chat_messages.items():
        for msg_id in msg_ids:
            try:
                await bot.delete_message(uid, msg_id)
            except Exception:
                pass
    room.chat_messages = {}


# ─────────────────────────────────────────────
# GENERAL HELPERS
# ─────────────────────────────────────────────

def bunker_slots(max_players: int) -> int:
    if max_players <= 8:    return 2
    elif max_players <= 10: return 3
    else:                   return 4


def room_info_text(room) -> str:
    players_list = "\n".join(
        f"  {'☠' if p.is_eliminated else '✅'} @{p.username or p.first_name}"
        for p in room.players.values()
    )
    phase_names = {
        GamePhase.LOBBY:      "🏠 Лобби",
        GamePhase.ROUND_1:    "📋 Раунд 1",
        GamePhase.ROUND_2:    "📋 Раунд 2",
        GamePhase.DISCUSSION: "💬 Обсуждение",
        GamePhase.VOTING:     "🗳 Голосование",
        GamePhase.ROUND_N:    f"📋 Раунд {room.round_num}",
        GamePhase.FINISHED:   "🏁 Завершена",
    }
    slots = bunker_slots(room.max_players)
    text = (
        f"<b>☢ БУНКЕР — Комната <code>{room.code}</code></b>\n"
        f"Фаза: {phase_names.get(room.phase, str(room.phase))}\n"
        f"Игроков: {len(room.players)}/{room.max_players}\n"
        f"🏚 Мест в бункере: {slots}\n\n"
        f"<b>Участники:</b>\n{players_list or '  (пусто)'}\n"
    )
    if room.apocalypse:
        text += f"\n<b>☢ Апокалипсис:</b> {room.apocalypse['name']}"
    if room.bunker:
        text += f"\n<b>🏚 Бункер:</b> {room.bunker['name']}"
    return text


def lobby_keyboard(room_code: str, user_id: int, is_host: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_host:
        buttons.append([InlineKeyboardButton(
            text="⚡ Начать игру", callback_data=f"start_game:{room_code}"
        )])
    buttons.append([InlineKeyboardButton(
        text="👁 Моя карточка", callback_data=f"my_card:{room_code}"
    )])
    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить статус", callback_data=f"refresh:{room_code}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def card_fields_keyboard(room_code: str, revealed: list, phase: GamePhase,
                          already_revealed_this_round: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    for key, icon, label in CARD_FIELDS:
        display = f"{icon} {label}"
        if key in revealed:
            buttons.append([InlineKeyboardButton(
                text=f"✅ {display} (открыто)", callback_data="noop"
            )])
        elif phase == GamePhase.ROUND_1 and key != "profession":
            buttons.append([InlineKeyboardButton(
                text=f"🔒 {display}", callback_data="noop"
            )])
        elif phase in (GamePhase.ROUND_2, GamePhase.ROUND_N) and already_revealed_this_round:
            buttons.append([InlineKeyboardButton(
                text=f"🔒 {display} (уже открыл в раунде)", callback_data="noop"
            )])
        else:
            buttons.append([InlineKeyboardButton(
                text=f"👁 Открыть: {display}", callback_data=f"reveal:{room_code}:{key}"
            )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vote_keyboard(room_code: str, alive_players: list, voter_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for p in alive_players:
        if p.user_id == voter_id:
            continue
        name = f"@{p.username}" if p.username else p.first_name
        buttons.append([InlineKeyboardButton(
            text=f"☠ Исключить {name}", callback_data=f"vote:{room_code}:{p.user_id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def end_discussion_keyboard(room_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🗳 Перейти к голосованию",
            callback_data=f"end_discussion:{room_code}"
        )
    ]])


def build_owner_card_text(player, room) -> str:
    card = player.card
    name = f"@{player.username}" if player.username else player.first_name
    values = {
        "profession": card.profession, "biology": card.biology,
        "health": card.health,         "baggage": card.baggage,
        "fact1": card.fact1,           "fact2": card.fact2,
        "special": card.special,
    }
    lines = [
        f"<b>🃏 Твоя карточка, {name}</b>",
        f"<i>Видишь только ты. Открытые карты видят все.</i>\n",
    ]
    for key, icon, label in CARD_FIELDS:
        marker = "(👁 открыто всем)" if key in card.revealed else "(🔒 только ты)"
        lines.append(f"{icon} <b>{label}:</b> {values[key]}  <i>{marker}</i>")
    lines.append(f"\n<i>Открыто: {len(card.revealed)}/7</i>")

    revealed_this = getattr(room, 'revealed_this_round', set())
    if room.phase == GamePhase.ROUND_1:
        lines.append("⚠️ <i>Раунд 1: можно открыть только профессию</i>")
    elif room.phase in (GamePhase.ROUND_2, GamePhase.ROUND_N):
        if player.user_id in revealed_this:
            lines.append("🔒 <i>В этом раунде ты уже открыл карту. Ожидай обсуждения.</i>")
        else:
            lines.append("✅ <i>Открой одну карту в этом раунде</i>")
    return "\n".join(lines)


def all_players_revealed_text(room, newly_revealed: dict = None) -> str:
    newly_revealed = newly_revealed or {}
    val_map_for = lambda card: {
        "profession": card.profession, "biology": card.biology,
        "health": card.health,         "baggage": card.baggage,
        "fact1": card.fact1,           "fact2": card.fact2,
        "special": card.special,
    }
    text = "<b>👥 Открытые карты участников:</b>\n"
    for p in room.players.values():
        name   = f"@{p.username}" if p.username else p.first_name
        status = "☠" if p.is_eliminated else "✅"
        text  += f"\n{status} <b>{name}</b>\n"
        if p.card and p.card.revealed:
            vals = val_map_for(p.card)
            for key, icon, label in CARD_FIELDS:
                if key in p.card.revealed:
                    new_mark = "  <i>🆕 вскрыто</i>" if newly_revealed.get(p.user_id) == key else ""
                    text += f"  {icon} {label}: {vals[key]}{new_mark}\n"
        else:
            text += "  <i>Нет открытых карт</i>\n"
    return text


def get_player_keyboard(room, player) -> InlineKeyboardMarkup:
    revealed_this = getattr(room, 'revealed_this_round', set())
    return card_fields_keyboard(
        room.code, player.card.revealed, room.phase,
        player.user_id in revealed_this
    )


# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "☢ <b>ДОБРО ПОЖАЛОВАТЬ В БУНКЕР</b> ☢\n\n"
        "Апокалипсис случился. Только часть из вас попадёт в бункер.\n"
        "Докажите свою ценность — или вас исключат.\n\n"
        "<b>Команды:</b>\n"
        "/create — создать комнату\n"
        "/join [код] — войти в комнату\n"
        "/room — статус текущей комнаты\n"
        "/card — посмотреть свою карточку\n"
        "/leave — покинуть комнату\n"
        "/help — помощь"
    )


# ─────────────────────────────────────────────
# /create
# ─────────────────────────────────────────────

@router.message(Command("create"))
async def cmd_create(message: Message):
    user_id = message.from_user.id
    existing = storage.find_room_by_player(user_id)
    if existing:
        await message.answer(
            f"⚠️ Ты уже в комнате <code>{existing.code}</code>. Используй /leave."
        )
        return
    row1 = [InlineKeyboardButton(text=str(n), callback_data=f"create_room:{n}") for n in range(4, 7)]
    row2 = [InlineKeyboardButton(text=str(n), callback_data=f"create_room:{n}") for n in range(7, 10)]
    row3 = [InlineKeyboardButton(text=str(n), callback_data=f"create_room:{n}") for n in range(10, 13)]
    kb = InlineKeyboardMarkup(inline_keyboard=[row1, row2, row3])
    await message.answer(
        "🏚 <b>Создание комнаты</b>\n\n"
        "Выбери максимальное количество игроков:\n\n"
        "<i>4–8 → 2 места | 9–10 → 3 места | 11–12 → 4 места</i>",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("create_room:"))
async def cb_create_room(call: CallbackQuery):
    user_id = call.from_user.id
    max_players = int(call.data.split(":")[1])
    room = storage.create_room(host_id=user_id, max_players=max_players)
    room.players[user_id] = Player(
        user_id=user_id,
        username=call.from_user.username or "",
        first_name=call.from_user.first_name or "Игрок"
    )
    slots = bunker_slots(max_players)
    kb = lobby_keyboard(room.code, user_id, is_host=True)
    await call.message.edit_text(
        f"✅ <b>Комната создана!</b>\n\n"
        f"Код: <code>{room.code}</code>\n"
        f"Размер: до {max_players} игроков | 🏚 Мест: {slots}\n\n"
        f"Поделись кодом: /join {room.code}\n\n"
        + room_info_text(room),
        reply_markup=kb
    )


# ─────────────────────────────────────────────
# /join
# ─────────────────────────────────────────────

@router.message(Command("join"))
async def cmd_join(message: Message):
    user_id = message.from_user.id
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /join КОД"); return
    code = args[1].upper()
    room = storage.get_room(code)
    if not room:
        await message.answer(f"❌ Комната <code>{code}</code> не найдена."); return
    if room.phase != GamePhase.LOBBY:
        await message.answer("❌ Игра уже началась."); return
    if len(room.players) >= room.max_players:
        await message.answer("❌ Комната заполнена."); return
    existing = storage.find_room_by_player(user_id)
    if existing and existing.code != code:
        await message.answer(f"⚠️ Ты уже в <code>{existing.code}</code>. Используй /leave."); return
    if user_id in room.players:
        await message.answer("Ты уже в этой комнате!"); return

    room.players[user_id] = Player(
        user_id=user_id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "Игрок"
    )
    kb = lobby_keyboard(code, user_id, is_host=(user_id == room.host_id))
    await message.answer(
        f"✅ Ты вошёл в комнату <code>{code}</code>!\n\n" + room_info_text(room),
        reply_markup=kb
    )


# ─────────────────────────────────────────────
# /room  /leave
# ─────────────────────────────────────────────

@router.message(Command("room"))
async def cmd_room(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате. /create или /join КОД"); return
    kb = lobby_keyboard(room.code, user_id, is_host=(user_id == room.host_id))
    await message.answer(room_info_text(room), reply_markup=kb)


@router.message(Command("leave"))
async def cmd_leave(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате."); return
    del room.players[user_id]
    if not room.players:
        storage.delete_room(room.code)
        await message.answer("Ты вышел. Комната удалена.")
    elif room.host_id == user_id:
        room.host_id = next(iter(room.players))
        await message.answer("Ты вышел. Хост передан другому игроку.")
    else:
        await message.answer(f"Ты вышел из комнаты <code>{room.code}</code>.")


# ─────────────────────────────────────────────
# START GAME
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("start_game:"))
async def cb_start_game(call: CallbackQuery):
    user_id = call.from_user.id
    code    = call.data.split(":")[1]
    room    = storage.get_room(code)

    if not room:
        await call.answer("Комната не найдена.", show_alert=True); return
    if room.host_id != user_id:
        await call.answer("Только хост может начать игру.", show_alert=True); return
    if len(room.players) < 2:
        await call.answer("Нужно минимум 2 игрока.", show_alert=True); return

    for pid, player in room.players.items():
        player.card = deal_cards()

    room.apocalypse          = get_random_scenario()
    room.bunker              = get_random_bunker()
    room.bunker_secret       = get_random_secret()
    room.phase               = GamePhase.ROUND_1
    room.round_num           = 1
    room.revealed_this_round = set()
    room.newly_revealed      = {}
    room.votes               = {}
    room.tracked_messages    = {}
    room.chat_messages       = {}

    slots = bunker_slots(room.max_players)
    game_text = (
        f"⚡ <b>ИГРА НАЧАЛАСЬ!</b>\n\n"
        f"☢ <b>АПОКАЛИПСИС:</b> {room.apocalypse['name']}\n"
        f"{room.apocalypse.get('desc', '')}\n\n"
        f"🏚 <b>БУНКЕР:</b> {room.bunker['name']}\n"
        f"Вместимость: {room.bunker['capacity']}\n"
        f"Еда: {room.bunker['food']} | Вода: {room.bunker['water']}\n"
        f"Энергия: {room.bunker['energy']}\n"
        f"Медицина: {room.bunker['medicine']}\n"
        f"Особенности: {room.bunker['features']}\n\n"
        f"🔒 <i>Секрет бункера откроется на 3-м раунде</i>\n\n"
        f"🏚 Мест в бункере: <b>{slots}</b>\n\n"
        f"<b>📋 РАУНД 1:</b> Каждый открывает профессию.\n"
        f"Как только все откроют — раунд 2 начнётся автоматически."
    )

    for pid, player in room.players.items():
        try:
            msg1 = await call.bot.send_message(pid, game_text)
            track_msg(room, pid, msg1.message_id)
            card_text = build_owner_card_text(player, room) + "\n\n" + all_players_revealed_text(room)
            msg2 = await call.bot.send_message(
                pid, card_text, reply_markup=get_player_keyboard(room, player)
            )
            track_msg(room, pid, msg2.message_id)
        except Exception:
            pass

    await call.message.edit_text(game_text, reply_markup=lobby_keyboard(code, user_id, is_host=True))


# ─────────────────────────────────────────────
# /card  +  my_card callback
# ─────────────────────────────────────────────

@router.message(Command("card"))
async def cmd_card(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате."); return
    player = room.players.get(user_id)
    if not player or not player.card:
        await message.answer("Карточка ещё не выдана."); return
    text = build_owner_card_text(player, room) + "\n\n" + all_players_revealed_text(room, getattr(room, 'newly_revealed', {}))
    await message.answer(text, reply_markup=get_player_keyboard(room, player))


@router.callback_query(F.data.startswith("my_card:"))
async def cb_my_card(call: CallbackQuery):
    user_id = call.from_user.id
    room    = storage.get_room(call.data.split(":")[1])
    player  = room.players.get(user_id) if room else None
    if not room or not player:
        await call.answer("Комната не найдена.", show_alert=True); return
    if not player.card:
        await call.answer("Карточка ещё не выдана.", show_alert=True); return
    await call.answer()
    text = build_owner_card_text(player, room) + "\n\n" + all_players_revealed_text(room, getattr(room, 'newly_revealed', {}))
    await call.message.answer(text, reply_markup=get_player_keyboard(room, player))


# ─────────────────────────────────────────────
# REVEAL
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("reveal:"))
async def cb_reveal(call: CallbackQuery):
    _, code, field = call.data.split(":")
    user_id = call.from_user.id
    room    = storage.get_room(code)
    player  = room.players.get(user_id) if room else None

    if not room or not player or not player.card:
        await call.answer("Ошибка.", show_alert=True); return

    card = player.card

    if room.phase == GamePhase.ROUND_1 and field != "profession":
        await call.answer("В раунде 1 только профессию!", show_alert=True); return

    if room.phase in (GamePhase.ROUND_2, GamePhase.ROUND_N):
        if user_id in getattr(room, 'revealed_this_round', set()):
            await call.answer("В этом раунде ты уже открыл карту!", show_alert=True); return

    if field in card.revealed:
        await call.answer("Эта карта уже открыта.", show_alert=True); return

    card.revealed.append(field)

    if not hasattr(room, 'revealed_this_round'): room.revealed_this_round = set()
    if not hasattr(room, 'newly_revealed'):       room.newly_revealed = {}

    label_map = {f[0]: f[2] for f in CARD_FIELDS}
    val_map   = {
        "profession": card.profession, "biology": card.biology,
        "health": card.health,         "baggage": card.baggage,
        "fact1": card.fact1,           "fact2": card.fact2,
        "special": card.special,
    }
    label = label_map.get(field, field)
    value = val_map.get(field, "")

    await call.answer(f"✅ {label}: {value}", show_alert=True)

    if room.phase in (GamePhase.ROUND_2, GamePhase.ROUND_N):
        room.revealed_this_round.add(user_id)
    room.newly_revealed[user_id] = field

    # Обновить карточку владельца
    owner_text = build_owner_card_text(player, room) + "\n\n" + all_players_revealed_text(room, room.newly_revealed)
    try:
        await call.message.edit_text(owner_text, reply_markup=get_player_keyboard(room, player))
    except TelegramBadRequest:
        pass

    # Уведомить остальных — обновлённая сводка
    player_name = f"@{player.username}" if player.username else player.first_name
    summary = all_players_revealed_text(room, room.newly_revealed)
    for pid, p in room.players.items():
        if pid == user_id:
            continue
        try:
            msg = await call.bot.send_message(
                pid,
                f"👁 <b>{player_name}</b> вскрыл(а) <b>{label}</b>: {value}\n\n{summary}"
            )
            track_msg(room, pid, msg.message_id)
        except Exception:
            pass

    alive = [p for p in room.players.values() if not p.is_eliminated]

    # Раунд 1: все вскрыли профессию → раунд 2
    if room.phase == GamePhase.ROUND_1 and field == "profession":
        room.revealed_this_round.add(user_id)
        if all(p.user_id in room.revealed_this_round for p in alive):
            await advance_to_round_2(call.bot, room)
        return

    # Раунды 2+: все вскрыли по карте → обсуждение
    if room.phase in (GamePhase.ROUND_2, GamePhase.ROUND_N):
        if all(p.user_id in room.revealed_this_round for p in alive):
            await start_discussion(call.bot, room)


# ─────────────────────────────────────────────
# DISCUSSION
# ─────────────────────────────────────────────

async def start_discussion(bot, room):
    room.phase = GamePhase.DISCUSSION
    summary = all_players_revealed_text(room, getattr(room, 'newly_revealed', {}))

    for pid, player in room.players.items():
        if player.is_eliminated:
            continue
        try:
            kb  = end_discussion_keyboard(room.code) if pid == room.host_id else None
            cap = (
                f"💬 <b>ОБСУЖДЕНИЕ — Раунд {room.round_num}</b>\n\n"
                f"Все карты открыты. Пиши боту — сообщения видят все участники.\n"
                + ("Когда готовы — нажми кнопку ниже." if pid == room.host_id
                   else "Хост завершит обсуждение когда будете готовы.\n")
                + f"\n\n{summary}"
            )
            msg = await bot.send_message(pid, cap, reply_markup=kb)
            track_msg(room, pid, msg.message_id)
        except Exception:
            pass


@router.message(F.text & ~F.text.startswith("/"))
async def relay_chat(message: Message):
    user_id = message.from_user.id
    room    = storage.find_room_by_player(user_id)
    if not room or room.phase != GamePhase.DISCUSSION:
        return
    player = room.players.get(user_id)
    if not player or player.is_eliminated:
        return

    sender = f"@{player.username}" if player.username else player.first_name
    relay  = f"💬 <b>{sender}:</b> {message.text}"

    for pid, p in room.players.items():
        if pid == user_id or p.is_eliminated:
            continue
        try:
            msg = await message.bot.send_message(pid, relay)
            track_chat_msg(room, pid, msg.message_id)
        except Exception:
            pass

    track_chat_msg(room, user_id, message.message_id)


@router.callback_query(F.data.startswith("end_discussion:"))
async def cb_end_discussion(call: CallbackQuery):
    code    = call.data.split(":")[1]
    user_id = call.from_user.id
    room    = storage.get_room(code)

    if not room:
        await call.answer("Комната не найдена.", show_alert=True); return
    if room.host_id != user_id:
        await call.answer("Только хост может завершить обсуждение.", show_alert=True); return
    if room.phase != GamePhase.DISCUSSION:
        await call.answer("Сейчас не фаза обсуждения.", show_alert=True); return

    await call.answer()
    await delete_chat_messages(call.bot, room)
    await start_voting(call.bot, room)


# ─────────────────────────────────────────────
# VOTING
# ─────────────────────────────────────────────

async def start_voting(bot, room):
    room.phase = GamePhase.VOTING
    alive = [p for p in room.players.values() if not p.is_eliminated]
    text  = (
        f"🗳 <b>ГОЛОСОВАНИЕ — Раунд {room.round_num}</b>\n\n"
        "Обсуждение завершено. Кого исключаем из бункера?"
    )
    for pid, player in room.players.items():
        if player.is_eliminated:
            continue
        try:
            msg = await bot.send_message(pid, text, reply_markup=vote_keyboard(room.code, alive, pid))
            track_msg(room, pid, msg.message_id)
        except Exception:
            pass


@router.message(Command("vote"))
async def cmd_vote(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате."); return
    if room.round_num < 2:
        await message.answer("Голосование начинается с раунда 2!"); return
    player = room.players.get(user_id)
    if player and player.is_eliminated:
        await message.answer("Ты исключён."); return
    alive = [p for p in room.players.values() if not p.is_eliminated]
    await message.answer("🗳 За кого голосуешь?", reply_markup=vote_keyboard(room.code, alive, user_id))


@router.callback_query(F.data.startswith("vote:"))
async def cb_vote(call: CallbackQuery):
    _, code, target_id_str = call.data.split(":")
    user_id   = call.from_user.id
    target_id = int(target_id_str)
    room = storage.get_room(code)
    if not room:
        await call.answer("Комната не найдена.", show_alert=True); return

    voter = room.players.get(user_id)
    if voter and voter.is_eliminated:
        await call.answer("Ты исключён.", show_alert=True); return

    target = room.players.get(target_id)
    if not target or target.is_eliminated:
        await call.answer("Игрок недоступен.", show_alert=True); return

    room.votes[user_id] = target_id
    name = f"@{target.username}" if target.username else target.first_name
    await call.answer(f"✅ Голос за {name} учтён", show_alert=True)
    try:
        await call.message.edit_text(f"✅ Ты проголосовал за исключение <b>{name}</b>")
    except TelegramBadRequest:
        pass

    alive_players = [p for p in room.players.values() if not p.is_eliminated]
    votes_cast = sum(
        1 for vid in room.votes
        if vid in room.players and not room.players[vid].is_eliminated
    )
    if votes_cast >= len(alive_players):
        await resolve_vote(call.message, room)


async def resolve_vote(message, room):
    for p in room.players.values():
        p.votes_received = 0
    for voter_id, target_id in room.votes.items():
        if voter_id in room.players and not room.players[voter_id].is_eliminated:
            if target_id in room.players:
                room.players[target_id].votes_received += 1

    alive = [p for p in room.players.values() if not p.is_eliminated]
    if not alive: return

    max_votes = max(p.votes_received for p in alive)
    losers    = [p for p in alive if p.votes_received == max_votes]
    is_tie    = len(losers) > 1

    results = "🗳 <b>РЕЗУЛЬТАТЫ ГОЛОСОВАНИЯ:</b>\n\n"
    for p in sorted(alive, key=lambda x: x.votes_received, reverse=True):
        name = f"@{p.username}" if p.username else p.first_name
        results += f"{name}: {p.votes_received} голос(ов)\n"

    loser = None
    if not is_tie:
        loser = losers[0]
        loser.is_eliminated = True
        lname = f"@{loser.username}" if loser.username else loser.first_name
        results += f"\n☠ <b>{lname} ИСКЛЮЧЁН ИЗ БУНКЕРА!</b>\n"
        if loser.card:
            c = loser.card
            results += (
                f"\n🃏 <b>Карточка {lname}:</b>\n"
                f"👔 {c.profession}\n🧬 {c.biology}\n❤️ {c.health}\n"
                f"🎒 {c.baggage}\n📌 {c.fact1}\n📌 {c.fact2}\n⚡ {c.special}\n"
            )
    else:
        names = ", ".join(f"@{p.username}" if p.username else p.first_name for p in losers)
        results += f"\n⚖️ <b>НИЧЬЯ!</b> {names} — повторное голосование!"

    room.votes = {}

    alive_after = [p for p in room.players.values() if not p.is_eliminated]
    slots = bunker_slots(room.max_players)

    if len(alive_after) <= slots:
        # ── ИГРА ЗАВЕРШЕНА ──
        survivors = ", ".join(f"@{p.username}" if p.username else p.first_name for p in alive_after)
        results += f"\n\n🏁 <b>ИГРА ЗАВЕРШЕНА!</b>\nВ бункере: {survivors}"
        room.phase = GamePhase.FINISHED

        await delete_tracked_messages(message.bot, room)

        for pid in room.players:
            try:
                await message.bot.send_message(pid, results)
                await message.bot.send_message(
                    pid,
                    "Используй /leave чтобы покинуть комнату или /create для новой игры."
                )
            except Exception:
                pass
    else:
        # ── Следующий раунд ──
        room.round_num           += 1
        room.revealed_this_round  = set()
        room.newly_revealed       = {}

        if room.round_num == 3:
            room.phase = GamePhase.ROUND_N
            secret     = getattr(room, 'bunker_secret', '—')
            results += (
                f"\n\n📋 <b>РАУНД 3 начался!</b>\n\n"
                f"🔓 <b>СЕКРЕТ БУНКЕРА РАСКРЫТ:</b>\n{secret}\n\n"
                f"Каждый открывает <b>одну</b> карту, затем — обсуждение и голосование."
            )
        else:
            room.phase = GamePhase.ROUND_N
            results += (
                f"\n\n📋 <b>РАУНД {room.round_num} начался!</b>\n"
                f"Каждый открывает <b>одну</b> карту, затем — обсуждение и голосование."
            )

        await delete_tracked_messages(message.bot, room)
        await delete_chat_messages(message.bot, room)

        for pid, player in room.players.items():
            try:
                msg1 = await message.bot.send_message(pid, results)
                track_msg(room, pid, msg1.message_id)
                if not player.is_eliminated:
                    card_text = build_owner_card_text(player, room) + "\n\n" + all_players_revealed_text(room)
                    msg2 = await message.bot.send_message(
                        pid, card_text, reply_markup=get_player_keyboard(room, player)
                    )
                    track_msg(room, pid, msg2.message_id)
            except Exception:
                pass


# ─────────────────────────────────────────────
# advance_to_round_2
# ─────────────────────────────────────────────

async def advance_to_round_2(bot, room):
    room.round_num           = 2
    room.phase               = GamePhase.ROUND_2
    room.revealed_this_round = set()
    room.newly_revealed      = {}
    room.votes               = {}

    text = (
        "📋 <b>РАУНД 2 начался!</b>\n\n"
        "Все открыли профессию.\n"
        "Теперь каждый открывает <b>одну</b> любую карту.\n"
        "После этого начнётся обсуждение, затем — голосование."
    )

    await delete_tracked_messages(bot, room)

    for pid, player in room.players.items():
        try:
            msg1 = await bot.send_message(pid, text)
            track_msg(room, pid, msg1.message_id)
            card_text = build_owner_card_text(player, room) + "\n\n" + all_players_revealed_text(room)
            msg2 = await bot.send_message(pid, card_text, reply_markup=get_player_keyboard(room, player))
            track_msg(room, pid, msg2.message_id)
        except Exception:
            pass


# ─────────────────────────────────────────────
# Refresh
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("refresh:"))
async def cb_refresh(call: CallbackQuery):
    code    = call.data.split(":")[1]
    user_id = call.from_user.id
    room    = storage.get_room(code)
    if not room:
        await call.answer("Комната не найдена.", show_alert=True); return
    kb = lobby_keyboard(code, user_id, is_host=(user_id == room.host_id))
    try:
        await call.message.edit_text(room_info_text(room), reply_markup=kb)
        await call.answer("Обновлено ✅")
    except TelegramBadRequest:
        await call.answer("Уже актуально ✅")


# ─────────────────────────────────────────────
# /next — форс (только хост)
# ─────────────────────────────────────────────

@router.message(Command("next"))
async def cmd_next_round(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате."); return
    if room.host_id != user_id:
        await message.answer("Только хост может переключать раунды."); return
    if room.phase == GamePhase.LOBBY:
        await message.answer("Игра не началась."); return

    room.round_num           += 1
    room.revealed_this_round  = set()
    room.newly_revealed       = {}
    room.votes                = {}

    if room.round_num == 2:
        room.phase = GamePhase.ROUND_2
        text = "📋 <b>РАУНД 2!</b>\nКаждый открывает <b>одну</b> карту."
    elif room.round_num == 3:
        room.phase = GamePhase.ROUND_N
        secret = getattr(room, 'bunker_secret', '—')
        text = (
            f"📋 <b>РАУНД 3!</b>\n\n"
            f"🔓 <b>СЕКРЕТ БУНКЕРА:</b>\n{secret}\n\n"
            f"Каждый открывает <b>одну</b> карту."
        )
    else:
        room.phase = GamePhase.ROUND_N
        text = f"📋 <b>РАУНД {room.round_num}!</b>\nКаждый открывает <b>одну</b> карту."

    await delete_tracked_messages(message.bot, room)
    await delete_chat_messages(message.bot, room)

    for pid in room.players:
        try:
            msg = await message.bot.send_message(pid, text)
            track_msg(room, pid, msg.message_id)
        except Exception:
            pass


# ─────────────────────────────────────────────
# /players
# ─────────────────────────────────────────────

@router.message(Command("players"))
async def cmd_players(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате."); return
    await message.answer(all_players_revealed_text(room, getattr(room, 'newly_revealed', {})))


# ─────────────────────────────────────────────
# /help
# ─────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "☢ <b>ПОМОЩЬ — БУНКЕР</b>\n\n"
        "<b>Команды:</b>\n"
        "/create — создать комнату (4–12 игроков)\n"
        "/join КОД — войти в комнату\n"
        "/room — статус комнаты\n"
        "/card — посмотреть и открыть свои карты\n"
        "/players — карты всех игроков\n"
        "/vote — проголосовать\n"
        "/next — форс-переход раунда (хост)\n"
        "/leave — покинуть комнату\n\n"
        "<b>Раунды:</b>\n"
        "🔹 Раунд 1: все открывают профессию → авто раунд 2\n"
        "🔹 Раунды 2+: одна карта → 💬 обсуждение → 🗳 голосование\n"
        "🔹 Раунд 3: раскрывается секрет бункера\n\n"
        "<b>Обсуждение:</b> просто пиши боту — сообщения видят все участники\n\n"
        "<b>Мест в бункере:</b>\n"
        "4–8 → 2 | 9–10 → 3 | 11–12 → 4"
    )


# ─────────────────────────────────────────────
# NOOP
# ─────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()