import asyncio
import logging

from aiogram import Dispatcher , Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from Handlers.RouteHandler import router
from config import BOT_TOKEN

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())