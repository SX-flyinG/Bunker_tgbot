# config.py
import os

# Вставь свой токен от @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# URL твоего Mini App (GitHub Pages, Vercel и т.д.)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-username.github.io/bunker-webapp")

# Максимальный и минимальный размер комнаты
ROOM_MIN = 8
ROOM_MAX = 12
