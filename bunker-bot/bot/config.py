# config.py
import os

# Вставь свой токен от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8704064363:AAHEBdJO03RYkkftWnJItMugJVxq-Rm3xJA")

# URL твоего Mini App (GitHub Pages, Vercel и т.д.)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://sx-flying.github.io/Bunker_tgbot/")

# Максимальный и минимальный размер комнаты
ROOM_MIN = 8
ROOM_MAX = 12
