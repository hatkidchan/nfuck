from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from httpx import AsyncClient

from nfuck.link_verifier import (
    explain_verification,
    get_random_useragent,
    verify_link,
)
from nfuck.utils import sanitize_link


dp = Dispatcher()

# @dp.message(Command("dd"))
# async def on_dd(message: Message):
#     if message.reply_to_message:
#         await message.reply_to_message.delete()


@dp.message(Command("check"))
async def on_check(message: Message):
    results = []
    for entity in message.entities or []:
        if entity.type in ("text_link", "url") and message.text:
            if entity.type == "url":
                entity.url = message.text[
                    entity.offset : entity.offset + entity.length
                ]
            if not entity.url:
                continue
            if not entity.url.startswith("http"):
                entity.url = "https://" + entity.url
            async with AsyncClient(
                headers={"User-Agent": get_random_useragent()}
            ) as client:
                data = (await client.get(entity.url)).text
                total_score = 0
                results.append(f"<b>{sanitize_link(entity.url)}</b>")
                for score, explanation, match in explain_verification(data):
                    results.append(f"{match.span()}: {explanation}")
                    total_score += score
                results.append(f"<b>Total score: {total_score}</b>")
                results.append("")
    if results:
        await message.reply(
            str.join("\n", results),
            parse_mode="html",
            disable_web_page_preview=True,
        )
    else:
        await message.reply(":shrug:")


@dp.message()
async def on_message(message: Message):
    detected_links: list[tuple[str, float]] = []
    for entity in message.entities or []:
        if entity.type in ("text_link", "url") and message.text:
            if entity.type == "url":
                entity.url = message.text[
                    entity.offset : entity.offset + entity.length
                ]
            if not entity.url:
                continue
            confidence = await verify_link(entity.url)
            if confidence > 0.9:
                detected_links.append((entity.url, confidence))
    if detected_links:
        if message.from_user:
            await message.reply(
                str.join(
                    "\n",
                    [
                        f"Found {len(detected_links)} links:",
                        str.join(
                            "\n",
                            [
                                f"{i}. {sanitize_link(url)} with confidence {confidence:.2f}"
                                for i, (url, confidence) in enumerate(
                                    detected_links, 1
                                )
                            ],
                        ),
                        f"Sender: {message.from_user.full_name} #{message.from_user.id} (@{message.from_user.username})",
                    ],
                ),
                parse_mode="html",
            )
        await message.delete()
