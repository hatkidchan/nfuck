from os import getenv
from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from httpx import AsyncClient
from asyncio import sleep
from urllib.parse import urlencode

from nfuck.link_verifier import (
    explain_verification,
    get_random_useragent,
    verify_link,
)
from nfuck.utils import sanitize_link


dp = Dispatcher()

SILENT_REMOVAL_IDS: set[int] = set(list(map(int, filter(lambda v: v, getenv("SILENT_REMOVAL_IDS", "").split(",")))))


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

FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScPby92blkuDRcbsb9kAQ35tK3EXYtXVFwgGBMlp6REw_ZNgw/viewform"
def form_for(message: Message, link: str) -> str:
    assert message.from_user != None
    params = {
        "entry.1873578193": link,
        "entry.1733286388": f"@{message.from_user.username}" if message.from_user.username else ""
    }
    return f"{FORM_URL}?{urlencode(params)}"


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
        await message.delete()
        if message.from_user and message.chat.id not in SILENT_REMOVAL_IDS:
            if not message.bot:
                raise RuntimeError("what")
            msg = await message.bot.send_message(
                message.chat.id,
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
                        "(message will be deleted in 20 seconds)",
                        "False positive? Report <a href=\"%s\">here</a>!" % form_for(message, detected_links[0][0])
                    ],
                ),
                parse_mode="html",
            )
            await sleep(20)
            await msg.delete()
