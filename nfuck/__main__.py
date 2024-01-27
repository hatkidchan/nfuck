from aiogram import Bot
from aiosqlite import connect as asqlite
from os import environ
from nfuck import dp

async def main():
    bot = Bot(environ["TG_BOT_TOKEN"])
    db = await asqlite(environ["DB_PATH"])
    await dp.start_polling(bot, db=db)
    await db.close()

if __name__ == "__main__":
    from asyncio import run
    run(main())

