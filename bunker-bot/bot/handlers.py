"""
handlers.py — все команды и колбэки Telegram-бота
"""
import json
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, WebAppInfo
)
from aiogram.filters import Command, CommandStart

from config import WEBAPP_URL, ROOM_MIN, ROOM_MAX
from storage import storage, GamePhase, Player
from cards import deal_cards, get_random_scenario, get_random_bunker

router = Router()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def webapp_url_for_room(room_code: str, user_id: int) -> str:
    return f"{WEBAPP_URL}?room={room_code}&uid={user_id}"


def room_info_text(room) -> str:
    players_list = "\n".join(
        f"  {'☠' if p.is_eliminated else '✅'} @{p.username or p.first_name}"
        for p in room.players.values()
    )
    phase_names = {
        GamePhase.LOBBY: "🏠 Лобби",
        GamePhase.ROUND_1: "📋 Раунд 1",
        GamePhase.ROUND_2: "📋 Раунд 2",
        GamePhase.VOTING: "🗳 Голосование",
        GamePhase.ROUND_N: f"📋 Раунд {room.round_num}",
        GamePhase.FINISHED: "🏁 Завершена",
    }
    text = (
        f"<b>☢ БУНКЕР — Комната <code>{room.code}</code></b>\n"
        f"Фаза: {phase_names.get(room.phase, room.phase)}\n"
        f"Игроков: {len(room.players)}/{room.max_players}\n\n"
        f"<b>Участники:</b>\n{players_list or '  (пусто)'}\n"
    )
    if room.apocalypse:
        text += f"\n<b>☢ Апокалипсис:</b> {room.apocalypse['title']}"
    if room.bunker:
        text += f"\n<b>🏚 Бункер:</b> {room.bunker['title']}"
    return text


def lobby_keyboard(room_code: str, user_id: int, is_host: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_host:
        buttons.append([InlineKeyboardButton(
            text="⚡ Начать игру",
            callback_data=f"start_game:{room_code}"
        )])
    buttons.append([InlineKeyboardButton(
        text="🎮 Открыть Mini App",
        web_app=WebAppInfo(url=webapp_url_for_room(room_code, user_id))
    )])
    buttons.append([InlineKeyboardButton(
        text="👁 Моя карточка",
        callback_data=f"my_card:{room_code}"
    )])
    buttons.append([InlineKeyboardButton(
        text="🔄 Обновить статус",
        callback_data=f"refresh:{room_code}"
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def card_fields_keyboard(room_code: str, revealed: list, phase: GamePhase) -> InlineKeyboardMarkup:
    """Кнопки для открытия карт в зависимости от раунда"""
    all_fields = [
        ("profession", "👔 Профессия"),
        ("biology", "🧬 Биология"),
        ("health", "❤️ Здоровье"),
        ("baggage", "🎒 Багаж"),
        ("fact1", "📌 Факт 1"),
        ("fact2", "📌 Факт 2"),
        ("special", "⚡ Особое условие"),
    ]
    buttons = []
    for key, label in all_fields:
        if key in revealed:
            buttons.append([InlineKeyboardButton(
                text=f"✅ {label} (открыто)",
                callback_data="noop"
            )])
        else:
            # В раунде 1 можно открыть только профессию
            if phase == GamePhase.ROUND_1 and key != "profession":
                buttons.append([InlineKeyboardButton(
                    text=f"🔒 {label}",
                    callback_data="noop"
                )])
            else:
                buttons.append([InlineKeyboardButton(
                    text=f"👁 Открыть: {label}",
                    callback_data=f"reveal:{room_code}:{key}"
                )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─────────────────────────────────────────────
# /start
# ─────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    text = (
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
    await message.answer(text)


# ─────────────────────────────────────────────
# /create
# ─────────────────────────────────────────────

@router.message(Command("create"))
async def cmd_create(message: Message):
    user_id = message.from_user.id

    # Если уже в комнате — предупредить
    existing = storage.find_room_by_player(user_id)
    if existing:
        await message.answer(
            f"⚠️ Ты уже в комнате <code>{existing.code}</code>.\n"
            f"Используй /leave чтобы выйти."
        )
        return

    # Предложить размер
    buttons = []
    for size in range(ROOM_MIN, ROOM_MAX + 1):
        buttons.append(InlineKeyboardButton(
            text=str(size),
            callback_data=f"create_room:{size}"
        ))
    kb = InlineKeyboardMarkup(inline_keyboard=[buttons])
    await message.answer(
        "🏚 <b>Создание комнаты</b>\n\nВыбери максимальное количество игроков:",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("create_room:"))
async def cb_create_room(call: CallbackQuery):
    user_id = call.from_user.id
    max_players = int(call.data.split(":")[1])

    room = storage.create_room(host_id=user_id, max_players=max_players)
    player = Player(
        user_id=user_id,
        username=call.from_user.username or "",
        first_name=call.from_user.first_name or "Игрок"
    )
    room.players[user_id] = player

    kb = lobby_keyboard(room.code, user_id, is_host=True)
    await call.message.edit_text(
        f"✅ <b>Комната создана!</b>\n\n"
        f"Код: <code>{room.code}</code>\n"
        f"Размер: до {max_players} игроков\n\n"
        f"Поделись кодом с друзьями: /join {room.code}\n\n"
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
        await message.answer("Использование: /join КОД\nПример: /join AB12C")
        return

    code = args[1].upper()
    room = storage.get_room(code)
    if not room:
        await message.answer(f"❌ Комната <code>{code}</code> не найдена.")
        return

    if room.phase != GamePhase.LOBBY:
        await message.answer("❌ Игра уже началась, войти нельзя.")
        return

    if len(room.players) >= room.max_players:
        await message.answer("❌ Комната заполнена.")
        return

    existing = storage.find_room_by_player(user_id)
    if existing and existing.code != code:
        await message.answer(f"⚠️ Ты уже в комнате <code>{existing.code}</code>. Используй /leave.")
        return

    if user_id in room.players:
        await message.answer("Ты уже в этой комнате!")
        return

    player = Player(
        user_id=user_id,
        username=message.from_user.username or "",
        first_name=message.from_user.first_name or "Игрок"
    )
    room.players[user_id] = player

    kb = lobby_keyboard(code, user_id, is_host=(user_id == room.host_id))
    await message.answer(
        f"✅ Ты вошёл в комнату <code>{code}</code>!\n\n" + room_info_text(room),
        reply_markup=kb
    )


# ─────────────────────────────────────────────
# /room — статус
# ─────────────────────────────────────────────

@router.message(Command("room"))
async def cmd_room(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате. /create или /join КОД")
        return

    kb = lobby_keyboard(room.code, user_id, is_host=(user_id == room.host_id))
    await message.answer(room_info_text(room), reply_markup=kb)


# ─────────────────────────────────────────────
# /leave
# ─────────────────────────────────────────────

@router.message(Command("leave"))
async def cmd_leave(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате.")
        return

    del room.players[user_id]
    if len(room.players) == 0:
        storage.delete_room(room.code)
        await message.answer("Ты вышел из комнаты. Комната удалена (ты был последним).")
    elif room.host_id == user_id:
        # Передать хоста следующему
        new_host = next(iter(room.players))
        room.host_id = new_host
        await message.answer(f"Ты вышел. Хост передан другому игроку.")
    else:
        await message.answer(f"Ты вышел из комнаты <code>{room.code}</code>.")


# ─────────────────────────────────────────────
# START GAME
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("start_game:"))
async def cb_start_game(call: CallbackQuery):
    user_id = call.from_user.id
    code = call.data.split(":")[1]
    room = storage.get_room(code)

    if not room:
        await call.answer("Комната не найдена.", show_alert=True)
        return

    if room.host_id != user_id:
        await call.answer("Только хост может начать игру.", show_alert=True)
        return

    if len(room.players) < 2:
        await call.answer("Нужно минимум 2 игрока.", show_alert=True)
        return

    # Раздать карточки
    for pid, player in room.players.items():
        player.card = deal_cards()

    # Выбрать сценарий и бункер
    room.apocalypse = get_random_scenario()
    room.bunker = get_random_bunker()
    room.phase = GamePhase.ROUND_1
    room.round_num = 1

    text = (
        f"⚡ <b>ИГРА НАЧАЛАСЬ!</b>\n\n"
        f"☢ <b>АПОКАЛИПСИС:</b> {room.apocalypse['title']}\n"
        f"{room.apocalypse['desc']}\n\n"
        f"🏚 <b>БУНКЕР:</b> {room.bunker['title']}\n"
        f"Вместимость: {room.bunker['capacity']} чел.\n"
        f"Еда: {room.bunker['food']} | Вода: {room.bunker['water']}\n"
        f"Энергия: {room.bunker['energy']}\n"
        f"Медицина: {room.bunker['med']}\n"
        f"Особенности: {room.bunker['features']}\n\n"
        f"🔒 <i>Особая функция бункера будет раскрыта на 3-м раунде</i>\n\n"
        f"<b>📋 РАУНД 1:</b> Каждый игрок может открыть ТОЛЬКО профессию.\n"
        f"Используй кнопку «Моя карточка» или Mini App."
    )

    # Уведомить каждого игрока лично
    for pid, player in room.players.items():
        try:
            await call.bot.send_message(
                pid,
                f"🎲 Игра началась в комнате <code>{code}</code>!\n\n"
                f"Твоя профессия: <b>{player.card.profession}</b> (единственное что можно открыть в раунде 1)\n\n"
                f"Нажми /card чтобы управлять картами.",
            )
        except Exception:
            pass

    kb = lobby_keyboard(code, user_id, is_host=True)
    await call.message.edit_text(text, reply_markup=kb)


# ─────────────────────────────────────────────
# /card — карточка игрока
# ─────────────────────────────────────────────

@router.message(Command("card"))
async def cmd_card(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате.")
        return

    player = room.players.get(user_id)
    if not player or not player.card:
        await message.answer("Карточка ещё не выдана. Дождись начала игры.")
        return

    await send_card(message, room, player)


CARD_FIELDS = [
    ("profession", "👔", "Профессия"),
    ("biology",    "🧬", "Биология"),
    ("health",     "❤️", "Здоровье"),
    ("baggage",    "🎒", "Багаж"),
    ("fact1",      "📌", "Факт 1"),
    ("fact2",      "📌", "Факт 2"),
    ("special",    "⚡", "Особое условие"),
]


def build_owner_card_text(player, room) -> str:
    """
    Текст карточки для ВЛАДЕЛЬЦА.
    Он всегда видит ВСЕ свои значения.
    (👁 открыто всем) — другие игроки это уже видят.
    (🔒 только ты)   — ты видишь, остальные нет.
    """
    card = player.card
    name = f"@{player.username}" if player.username else player.first_name
    values = {
        "profession": card.profession,
        "biology":    card.biology,
        "health":     card.health,
        "baggage":    card.baggage,
        "fact1":      card.fact1,
        "fact2":      card.fact2,
        "special":    card.special,
    }
    lines = [
        f"<b>🃏 Твоя карточка, {name}</b>",
        f"<i>Видишь только ты. Открытые карты видят все игроки.</i>\n",
    ]
    for key, icon, label in CARD_FIELDS:
        val = values[key]
        if key in card.revealed:
            lines.append(f"{icon} <b>{label}:</b> {val}  <i>(👁 открыто всем)</i>")
        else:
            lines.append(f"{icon} <b>{label}:</b> {val}  <i>(🔒 только ты)</i>")

    lines.append(f"\n<i>Публично раскрыто: {len(card.revealed)}/7</i>")
    if room.phase == GamePhase.ROUND_1:
        lines.append("⚠️ <i>Раунд 1: открыть публично можно только профессию</i>")
    elif room.phase in (GamePhase.ROUND_2, GamePhase.ROUND_N):
        lines.append("✅ <i>Можно открыть любую карту — нажми кнопку ниже</i>")
    return "\n".join(lines)


async def send_card(message, room, player):
    """Отправляет карточку строго в личку владельцу."""
    text = build_owner_card_text(player, room)
    kb = card_fields_keyboard(room.code, player.card.revealed, room.phase)
    await message.answer(text, reply_markup=kb)


# ─────────────────────────────────────────────
# Callback: my_card
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("my_card:"))
async def cb_my_card(call: CallbackQuery):
    user_id = call.from_user.id
    code = call.data.split(":")[1]
    room = storage.get_room(code)
    player = room.players.get(user_id) if room else None

    if not room or not player:
        await call.answer("Комната не найдена.", show_alert=True)
        return
    if not player.card:
        await call.answer("Карточка ещё не выдана.", show_alert=True)
        return

    await call.answer()
    await send_card(call.message, room, player)


# ─────────────────────────────────────────────
# Callback: reveal card field
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("reveal:"))
async def cb_reveal(call: CallbackQuery):
    _, code, field = call.data.split(":")
    user_id = call.from_user.id
    room = storage.get_room(code)
    player = room.players.get(user_id) if room else None

    if not room or not player or not player.card:
        await call.answer("Ошибка.", show_alert=True)
        return

    card = player.card

    # Проверка раунда 1
    if room.phase == GamePhase.ROUND_1 and field != "profession":
        await call.answer("В раунде 1 можно открыть только профессию!", show_alert=True)
        return

    if field in card.revealed:
        await call.answer("Эта карта уже открыта.", show_alert=True)
        return

    card.revealed.append(field)

    # Найти читаемое имя поля для алерта
    label_map = {f[0]: f[2] for f in CARD_FIELDS}
    val_map = {
        "profession": card.profession, "biology": card.biology,
        "health": card.health, "baggage": card.baggage,
        "fact1": card.fact1, "fact2": card.fact2, "special": card.special,
    }
    label = label_map.get(field, field)
    value = val_map.get(field, "")
    await call.answer(f"✅ {label} теперь открыта всем: {value}", show_alert=True)

    # Обновить карточку — владелец видит все значения + статус открытия
    text = build_owner_card_text(player, room)
    kb = card_fields_keyboard(code, card.revealed, room.phase)
    await call.message.edit_text(text, reply_markup=kb)


# ─────────────────────────────────────────────
# Callback: refresh
# ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("refresh:"))
async def cb_refresh(call: CallbackQuery):
    code = call.data.split(":")[1]
    user_id = call.from_user.id
    room = storage.get_room(code)
    if not room:
        await call.answer("Комната не найдена.", show_alert=True)
        return
    kb = lobby_keyboard(code, user_id, is_host=(user_id == room.host_id))
    await call.message.edit_text(room_info_text(room), reply_markup=kb)
    await call.answer("Обновлено")


# ─────────────────────────────────────────────
# /next — следующий раунд (только хост)
# ─────────────────────────────────────────────

@router.message(Command("next"))
async def cmd_next_round(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате.")
        return
    if room.host_id != user_id:
        await message.answer("Только хост может переключать раунды.")
        return
    if room.phase == GamePhase.LOBBY:
        await message.answer("Игра ещё не началась. /start_game")
        return

    room.round_num += 1

    if room.round_num == 2:
        room.phase = GamePhase.ROUND_2
        text = (
            f"📋 <b>РАУНД 2 начался!</b>\n\n"
            f"Теперь каждый может открыть любую одну карту.\n"
            f"После обсуждения начнётся голосование.\n\n"
            f"Используй /vote @ник чтобы проголосовать за исключение."
        )
    elif room.round_num == 3:
        room.phase = GamePhase.ROUND_N
        # Раскрыть секрет бункера
        secret = room.bunker.get("secret", "") if room.bunker else ""
        text = (
            f"📋 <b>РАУНД 3!</b>\n\n"
            f"🔓 <b>ОСОБАЯ ФУНКЦИЯ БУНКЕРА РАСКРЫТА:</b>\n"
            f"{secret}\n\n"
            f"Это может изменить всё!"
        )
    else:
        room.phase = GamePhase.ROUND_N
        text = f"📋 <b>РАУНД {room.round_num} начался!</b>\n\nОбсуждение и голосование продолжается."

    if room.round_num >= 2:
        text += "\n\n🗳 <b>Начинается голосование!</b>\nИспользуй /vote @ник"

    await message.answer(text)

    # Уведомить всех
    for pid in room.players:
        if pid != user_id:
            try:
                await message.bot.send_message(pid, text)
            except Exception:
                pass


# ─────────────────────────────────────────────
# /vote @username — голосование
# ─────────────────────────────────────────────

@router.message(Command("vote"))
async def cmd_vote(message: Message):
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате.")
        return
    if room.round_num < 2:
        await call.answer("Голосование начинается с раунда 2!", show_alert=True)
        return

    args = message.text.split()
    if len(args) < 2:
        # Показать кнопки для голосования
        alive = [p for p in room.players.values() if not p.is_eliminated and p.user_id != user_id]
        if not alive:
            await message.answer("Не за кого голосовать.")
            return

        buttons = []
        for p in alive:
            name = f"@{p.username}" if p.username else p.first_name
            buttons.append([InlineKeyboardButton(
                text=f"☠ Исключить {name}",
                callback_data=f"vote:{room.code}:{p.user_id}"
            )])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("🗳 За кого голосуешь?", reply_markup=kb)
        return

    # Найти игрока по юзернейму
    target_username = args[1].lstrip("@").lower()
    target = None
    for p in room.players.values():
        if (p.username or "").lower() == target_username:
            target = p
            break

    if not target:
        await message.answer(f"Игрок @{target_username} не найден в комнате.")
        return

    if target.is_eliminated:
        await message.answer("Этот игрок уже исключён.")
        return

    room.votes[user_id] = target.user_id
    name = f"@{target.username}" if target.username else target.first_name
    await message.answer(f"✅ Ты проголосовал за исключение {name}")

    # Проверить если все проголосовали
    alive_players = [p for p in room.players.values() if not p.is_eliminated]
    votes_cast = sum(1 for vid in room.votes if vid in room.players and not room.players[vid].is_eliminated)
    if votes_cast >= len(alive_players):
        await resolve_vote(message, room)


@router.callback_query(F.data.startswith("vote:"))
async def cb_vote(call: CallbackQuery):
    _, code, target_id_str = call.data.split(":")
    user_id = call.from_user.id
    target_id = int(target_id_str)
    room = storage.get_room(code)
    if not room:
        await call.answer("Комната не найдена.", show_alert=True)
        return

    target = room.players.get(target_id)
    if not target or target.is_eliminated:
        await call.answer("Игрок недоступен.", show_alert=True)
        return

    room.votes[user_id] = target_id
    name = f"@{target.username}" if target.username else target.first_name
    await call.answer(f"✅ Голос за {name} учтён")
    await call.message.edit_text(f"✅ Ты проголосовал за исключение {name}")

    # Проверить завершение голосования
    alive_players = [p for p in room.players.values() if not p.is_eliminated]
    votes_cast = sum(1 for vid in room.votes if vid in room.players and not room.players[vid].is_eliminated)
    if votes_cast >= len(alive_players):
        await resolve_vote(call.message, room)


async def resolve_vote(message, room):
    """Подсчёт голосов и исключение"""
    # Сброс счётчиков
    for p in room.players.values():
        p.votes_received = 0

    # Подсчёт
    for voter_id, target_id in room.votes.items():
        if voter_id in room.players and not room.players[voter_id].is_eliminated:
            if target_id in room.players:
                room.players[target_id].votes_received += 1

    # Найти лидера голосования
    alive = [p for p in room.players.values() if not p.is_eliminated]
    if not alive:
        return

    max_votes = max(p.votes_received for p in alive)
    losers = [p for p in alive if p.votes_received == max_votes]

    results = "🗳 <b>РЕЗУЛЬТАТЫ ГОЛОСОВАНИЯ:</b>\n\n"
    for p in sorted(alive, key=lambda x: x.votes_received, reverse=True):
        name = f"@{p.username}" if p.username else p.first_name
        results += f"{name}: {p.votes_received} голос(ов)\n"

    if len(losers) == 1:
        loser = losers[0]
        loser.is_eliminated = True
        name = f"@{loser.username}" if loser.username else loser.first_name
        results += f"\n☠ <b>{name} ИСКЛЮЧЁН ИЗ БУНКЕРА!</b>\n"

        # Раскрыть все карты исключённого
        if loser.card:
            card = loser.card
            results += (
                f"\n🃏 <b>Карточка {name}:</b>\n"
                f"👔 Профессия: {card.profession}\n"
                f"🧬 Биология: {card.biology}\n"
                f"❤️ Здоровье: {card.health}\n"
                f"🎒 Багаж: {card.baggage}\n"
                f"📌 Факт 1: {card.fact1}\n"
                f"📌 Факт 2: {card.fact2}\n"
                f"⚡ Особое условие: {card.special}\n"
            )
    else:
        results += f"\n⚖️ <b>НИЧЬЯ!</b> {', '.join(f'@{p.username}' if p.username else p.first_name for p in losers)}\nПовторное голосование!"

    # Сбросить голоса
    room.votes = {}

    # Проверить победу
    alive_after = [p for p in room.players.values() if not p.is_eliminated]
    if len(alive_after) <= (room.max_players // 2):
        results += f"\n\n🏁 <b>ИГРА ЗАВЕРШЕНА!</b>\nВ бункере остались: {', '.join(f'@{p.username}' if p.username else p.first_name for p in alive_after)}"
        room.phase = GamePhase.FINISHED

    # Разослать всем
    for pid in room.players:
        try:
            await message.bot.send_message(pid, results)
        except Exception:
            pass


# ─────────────────────────────────────────────
# /players — список игроков с открытыми картами
# ─────────────────────────────────────────────

@router.message(Command("players"))
async def cmd_players(message: Message):
    """
    Показывает ТОЛЬКО публично раскрытые карты каждого игрока.
    Скрытые карты не отображаются — даже заглушкой.
    Это защищает приватность игроков.
    """
    user_id = message.from_user.id
    room = storage.find_room_by_player(user_id)
    if not room:
        await message.answer("Ты не в комнате.")
        return

    val_map_for = lambda card: {
        "profession": card.profession, "biology": card.biology,
        "health": card.health, "baggage": card.baggage,
        "fact1": card.fact1, "fact2": card.fact2, "special": card.special,
    }

    text = f"<b>👥 Игроки — комната {room.code}</b>\n"
    text += f"<i>Показаны только публично открытые карты</i>\n\n"

    for p in room.players.values():
        name = f"@{p.username}" if p.username else p.first_name
        status = "☠" if p.is_eliminated else "✅"
        text += f"{status} <b>{name}</b>\n"

        if p.card:
            revealed = p.card.revealed
            if revealed:
                vals = val_map_for(p.card)
                for key, icon, label in CARD_FIELDS:
                    if key in revealed:
                        text += f"  {icon} {label}: {vals[key]}\n"
            else:
                text += f"  <i>Ни одна карта ещё не открыта</i>\n"
        text += "\n"

    await message.answer(text)


# ─────────────────────────────────────────────
# /help
# ─────────────────────────────────────────────

@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "☢ <b>ПОМОЩЬ — БУНКЕР</b>\n\n"
        "<b>Команды:</b>\n"
        "/create — создать комнату (выбрать 8-12 игроков)\n"
        "/join КОД — войти в комнату\n"
        "/room — статус комнаты\n"
        "/card — посмотреть и открыть свои карты\n"
        "/players — все игроки и их открытые карты\n"
        "/next — след. раунд (только хост)\n"
        "/vote — проголосовать за исключение\n"
        "/leave — покинуть комнату\n\n"
        "<b>Правила раскрытия:</b>\n"
        "🔹 Раунд 1: только профессию\n"
        "🔹 Раунд 2+: любую одну карту за раунд\n"
        "🔹 Голосование: с раунда 2\n"
        "🔹 Раунд 3: раскрывается особая функция бункера\n"
        "🔹 При исключении: все карты игрока открываются"
    )
    await message.answer(text)


# ─────────────────────────────────────────────
# NOOP callback
# ─────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(call: CallbackQuery):
    await call.answer()


# ─────────────────────────────────────────────
# WEBAPP DATA (от Mini App)
# ─────────────────────────────────────────────

@router.message(F.web_app_data)
async def handle_webapp_data(message: Message):
    """Принимает действия из Mini App"""
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")
        user_id = message.from_user.id
        room_code = data.get("room")

        room = storage.get_room(room_code) if room_code else storage.find_room_by_player(user_id)
        if not room:
            await message.answer("Комната не найдена")
            return

        if action == "reveal_field":
            field = data.get("field")
            player = room.players.get(user_id)
            if player and player.card and field not in player.card.revealed:
                if room.phase == GamePhase.ROUND_1 and field != "profession":
                    await message.answer("В раунде 1 только профессию!")
                    return
                player.card.revealed.append(field)
                await message.answer(f"✅ Карта открыта: {field}")

        elif action == "vote":
            target_id = data.get("target_id")
            if target_id and room.round_num >= 2:
                room.votes[user_id] = int(target_id)
                await message.answer("✅ Голос учтён")

    except Exception as e:
        await message.answer(f"Ошибка: {e}")
