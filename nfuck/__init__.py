from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from httpx import AsyncClient

from nfuck.link_verifier import explain_verification, get_random_useragent, verify_link

dp = Dispatcher()

@dp.message(Command("check"))
async def on_check(message: Message):
    results = []
    for entity in message.entities or []:
        if entity.type in ("text_link", "url") and message.text:
            if entity.type == "url":
                entity.url = message.text[entity.offset : entity.offset + entity.length]
            if not entity.url:
                continue
            async with AsyncClient(
                headers={"User-Agent": get_random_useragent()}
            ) as client:
                data = (await client.get(entity.url)).text
                total_score = 0
                results.append(f"<b>{entity.url}</b>")
                for score, explanation, match in explain_verification(data):
                    results.append(f"{match.span()}: {explanation}")
                    total_score += score
                results.append(f"<b>Total score: {total_score}</b>")
                results.append("")
    await message.reply(str.join("\n", results), parse_mode="html")


@dp.message()
async def on_message(message: Message):
    for entity in message.entities or []:
        if entity.type in ("text_link", "url") and message.text:
            if entity.type == "url":
                entity.url = message.text[entity.offset : entity.offset + entity.length]
            if not entity.url:
                continue
            confidence = await verify_link(entity.url)
            if confidence > 0.75:
                await message.reply(f"Holy smokes, another one (~{confidence*100:.0f}% sure)")
                await message.delete()


