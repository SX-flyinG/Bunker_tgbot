"""
Точка входа для Render.
Запускается из корня репозитория.
"""
import sys
import os

# Добавляем папку bot/ в путь поиска модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))

# Запускаем бота
from bot.main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
