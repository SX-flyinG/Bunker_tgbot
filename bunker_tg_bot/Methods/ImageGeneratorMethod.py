# -*- coding: utf-8 -*-
import os
import re
import textwrap
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ── КОНФИГУРАЦИЯ ТЕМЫ ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Пути к шрифтам (Убедитесь, что файлы лежат в папке Fonts)
# Unbounded отлично поддерживает кириллицу. DejaVuSans — для символов ☢, ⚡, ☣.
FONTS = {
    "bold": os.path.join(BASE_DIR, "Fonts", "DejaVuSans-Bold.ttf"),
    "reg": os.path.join(BASE_DIR, "Fonts", "DejaVuSans.ttf"),
    "med": os.path.join(BASE_DIR, "Fonts", "DejaVuSans.ttf"),
    "symb": os.path.join(BASE_DIR, "Fonts", "segoe-ui-emoji.ttf")
}

COLORS = {
    "bg": (8, 8, 10),
    "panel": (16, 16, 20),
    "border": (38, 38, 45),
    "accent": (80, 20, 15),
    "red": (210, 45, 30),
    "red_dim": (140, 30, 20),
    "orange": (210, 100, 20),
    "green": (45, 175, 75),
    "white": (235, 235, 240),
    "gray": (110, 110, 120),
    "teal": (30, 140, 140)
}


# ── УТИЛИТЫ ──────────────────────────────────────────────────────────────────

def _get_font(style: str, size: int):
    path = FONTS.get(style, FONTS["reg"])
    try:
        return ImageFont.truetype(path, size)
    except:
        return ImageFont.load_default()


def _draw_rich_text(draw, x, y, text, main_font, fill=COLORS["white"], align="left", width_limit=None):
    """
    Рисует текст + emoji без поломки кириллицы
    """

    symbol_font = _get_font("symb", main_font.size)

    parts = re.findall(r'[\U00010000-\U0010ffff]|.', text)

    calculated = []
    total_w = 0

    for part in parts:

        if ord(part) > 10000:
            font = symbol_font
        else:
            font = main_font

        bbox = draw.textbbox((0, 0), part, font=font)
        w = bbox[2] - bbox[0]

        calculated.append((part, font, w))
        total_w += w

    curr_x = x

    if align == "center" and width_limit:
        curr_x = x + (width_limit - total_w) // 2

    if align == "right" and width_limit:
        curr_x = x + width_limit - total_w

    for part, font, w in calculated:
        draw.text((curr_x, y), part, font=font, fill=fill)
        curr_x += w


def _draw_card_template(draw, W, H, title, subtitle=""):
    """Базовый шаблон для всех экранов"""
    # Сетка (фоновые линии)
    for i in range(0, W + H, 35):
        draw.line([(i, 0), (0, i)], fill=(15, 15, 18), width=1)

    # Верхняя панель
    draw.rectangle([0, 0, W, 90], fill=(12, 8, 8))
    draw.rectangle([0, 88, W, 91], fill=COLORS["red_dim"])

    # Заголовок
    f_title = _get_font("bold", 44)
    _draw_rich_text(draw, 0, 15, title, f_title, fill=COLORS["red"], align="center", width_limit=W)

    if subtitle:
        f_sub = _get_font("reg", 14)
        _draw_rich_text(draw, 0, 66, subtitle, f_sub, fill=COLORS["gray"], align="center", width_limit=W)


def _to_bytes(img):
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf


# ── ГЕНЕРАЦИЯ ────────────────────────────────────────────────────────────────

def gen_welcome():
    W, H = 900, 480
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    _draw_card_template(draw, W, H, "БУНКЕР", "☢ СИСТЕМА КОНТРОЛЯ ВЫЖИВАНИЯ ☢")

    # Центральный блок
    draw.rounded_rectangle([40, 110, W - 40, 400], radius=12, fill=(14, 14, 18), outline=COLORS["accent"], width=2)

    _draw_rich_text(draw, 70, 140, "АПОКАЛИПСИС НАСТУПИЛ.", _get_font("bold", 22))
    _draw_rich_text(draw, 70, 175, "Ваша задача — убедить остальных, что вы достойны места.", _get_font("reg", 15),
                    fill=COLORS["gray"])

    commands = [
        ("/create", "— Инициализировать убежище"),
        ("/join", "— Постучать в гермозатвор"),
        ("/help", "— Протоколы системы")
    ]

    y = 240
    for cmd, desc in commands:
        draw.text((80, y), cmd, font=_get_font("bold", 16), fill=COLORS["orange"])
        draw.text((250, y), desc, font=_get_font("reg", 16), fill=COLORS["white"])
        y += 40

    _draw_rich_text(draw, 0, H - 35, "CONNECTED // SYSTEM_READY", _get_font("med", 12), fill=(60, 60, 70),
                    align="center", width_limit=W)
    return _to_bytes(img)


def gen_lobby(room_code, max_players, slots, players):
    W, H = 900, 450
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    _draw_card_template(draw, W, H, "ЛОББИ", f"☢ ОЖИДАНИЕ ВЫЖИВШИХ [{len(players)}/12] ☢")

    # Левая панель (Код)
    draw.rounded_rectangle([40, 110, 400, 380], radius=10, fill=COLORS["panel"], outline=COLORS["border"])
    draw.text((65, 130), "ДОСТУП:", font=_get_font("med", 12), fill=COLORS["gray"])
    draw.text((65, 155), str(room_code).upper(), font=_get_font("bold", 52), fill=COLORS["red"])

    # Правая панель (Игроки)
    draw.rounded_rectangle([420, 110, W - 40, 380], radius=10, fill=COLORS["panel"], outline=COLORS["border"])

    y = 135
    for i, name in enumerate(players[:10]):
        # Рисуем "лампочку" статуса
        draw.ellipse([445, y + 6, 455, y + 16], fill=COLORS["green"])
        _draw_rich_text(draw, 470, y, f"{i + 1}. {name[:18]}", _get_font("reg", 16))
        y += 32

    _draw_rich_text(draw, 0, 410, "⚡ Ожидайте команды администратора...", _get_font("reg", 14), fill=COLORS["orange"],
                    align="center", width_limit=W)
    return _to_bytes(img)


def gen_game_start(apocalypse: dict, bunker: dict, slots: int, round_num: int = 1):
    W, H = 900, 540
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    _draw_card_template(draw, W, H, "СТАРТ ИГРЫ", "☢ ОТЧЕТ О КАТАСТРОФЕ ☢")

    # Апокалипсис
    draw.rounded_rectangle([40, 110, W - 40, 280], radius=10,
                           fill=COLORS["panel"], outline=COLORS["accent"], width=2)

    _draw_rich_text(draw, 60, 125, "УСЛОВИЕ АПОКАЛИПСИСА",
                    _get_font("med", 12), fill=COLORS["red"])

    _draw_rich_text(draw, 60, 150,
                    apocalypse.get("name", "").upper(),
                    _get_font("bold", 24),
                    fill=COLORS["red"])

    desc_lines = textwrap.wrap(apocalypse.get("desc", ""), width=85)

    y = 190
    for line in desc_lines[:3]:
        _draw_rich_text(draw, 60, y, line,
                        _get_font("reg", 15),
                        fill=COLORS["gray"])
        y += 22

    # Бункер
    draw.rounded_rectangle([40, 300, W - 40, 500], radius=10,
                           fill=COLORS["panel"], outline=COLORS["border"])

    _draw_rich_text(draw, 60, 315, "ИНФОРМАЦИЯ ОБ УБЕЖИЩЕ",
                    _get_font("med", 12),
                    fill=COLORS["teal"])

    _draw_rich_text(draw, 60, 340,
                    bunker.get("name", "Стандартный бункер"),
                    _get_font("bold", 20))

    specs = [
        ("ЕДА", bunker.get("food")),
        ("ВОДА", bunker.get("water")),
        ("МЕСТ", slots)
    ]

    x = 60
    for label, val in specs:
        draw.text((x, 380), label,
                  font=_get_font("med", 11),
                  fill=COLORS["gray"])

        draw.text((x, 400), str(val),
                  font=_get_font("bold", 18),
                  fill=COLORS["orange"])

        x += 280

    return _to_bytes(img)

def gen_all_cards(room, newly_revealed=None):
    W, H = 900, 600
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    _draw_card_template(draw, W, H,
                        "СПИСОК ВЫЖИВШИХ",
                        "📋 АКТУАЛЬНЫЕ ДАННЫЕ")

    y = 120

    for player in room.players.values():

        _draw_rich_text(draw, 60, y,
                        f"• {player.username}",
                        _get_font("bold", 18))

        y += 40

        if y > H - 60:
            break

    return _to_bytes(img)

def gen_vote_results(room, loser=None, is_tie=False):
    W, H = 900, 500
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    _draw_card_template(draw, W, H, "ГОЛОСОВАНИЕ", "🗳 РЕЗУЛЬТАТЫ")

    if is_tie:

        _draw_rich_text(draw, 0, 220,
                        "⚖ НИЧЬЯ!",
                        _get_font("bold", 36),
                        fill=COLORS["orange"],
                        align="center",
                        width_limit=W)

    else:

        _draw_rich_text(draw, 0, 200,
                        "☠ ИГРОК ИСКЛЮЧЕН",
                        _get_font("bold", 34),
                        fill=COLORS["red"],
                        align="center",
                        width_limit=W)

        if loser:
            _draw_rich_text(draw, 0, 260,
                            loser.username,
                            _get_font("bold", 26),
                            align="center",
                            width_limit=W)

    return _to_bytes(img)

def gen_game_over(survivors):
    W, H = 900, 420
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    _draw_card_template(draw, W, H,
                        "КОНЕЦ ИГРЫ",
                        "☢ ВЫЖИВШИЕ ☢")

    y = 150

    for name in survivors:

        _draw_rich_text(draw, 0, y,
                        f"✓ {name}",
                        _get_font("bold", 22),
                        fill=COLORS["green"],
                        align="center",
                        width_limit=W)

        y += 40

    return _to_bytes(img)


def gen_player_card(username: str, card, room_phase, revealed_this_round: set, status="В ИГРЕ"):
    W, H = 560, 680
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 80], fill=(12, 8, 8))
    _draw_rich_text(draw, 20, 25, f"@{username}",
                    _get_font("bold", 24))

    fields = [
        ("profession", "ПРОФЕССИЯ"),
        ("biology", "БИОЛОГИЯ"),
        ("health", "ЗДОРОВЬЕ"),
        ("baggage", "БАГАЖ"),
        ("fact1", "ФАКТ 1"),
        ("fact2", "ФАКТ 2"),
        ("special", "ОСОБОЕ")
    ]

    y = 100

    for key, label in fields:

        is_open = key in card.revealed

        draw.rounded_rectangle(
            [20, y, W - 20, y + 70],
            radius=8,
            fill=(20, 20, 25) if is_open else (12, 12, 15),
            outline=COLORS["border"]
        )

        draw.text((35, y + 10), label,
                  font=_get_font("med", 11),
                  fill=COLORS["gray"])

        val = getattr(card, key) if is_open else "ЗАСЕКРЕЧЕНО"

        _draw_rich_text(
            draw,
            35,
            y + 30,
            textwrap.shorten(val, width=40),
            _get_font("bold", 15),
            fill=COLORS["white"] if is_open else (50, 50, 55)
        )

        if is_open:
            _draw_rich_text(draw, W - 40, y + 28,
                            "✓",
                            _get_font("bold", 18),
                            fill=COLORS["green"])

        y += 80

    return _to_bytes(img)

def gen_round_start(round_num: int, secret: str = None):
    W, H = 900, 400
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    _draw_card_template(draw, W, H,
                        f"РАУНД {round_num}",
                        "📋 ПОДГОТОВКА")

    if secret:
        _draw_rich_text(draw, 0, 200,
                        secret,
                        _get_font("reg", 18),
                        align="center",
                        width_limit=W)

    return _to_bytes(img)