from os import getenv
from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from httpx import AsyncClient
from asyncio import sleep
from urllib.parse import urlencode
from logging import DEBUG, getLogger

from nfuck.link_verifier import (
    explain_verification,
    get_random_useragent,
    verify_link,
)
from nfuck.utils import sanitize_link


dp = Dispatcher()
logger = getLogger("nfuck.__init__")
logger.setLevel(DEBUG)

SILENT_REMOVAL_IDS: set[int] = set(
    list(
        map(
            int,
            filter(lambda v: v, getenv("SILENT_REMOVAL_IDS", "").split(",")),
        )
    )
)


@dp.message(Command("check"))
async def on_check(message: Message):
    results = []
    urls = []
    if message.link_preview_options:
        urls.append(message.link_preview_options.url)
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
            urls.append(entity.url)
    for url in urls:
        if not url:
            continue
        async with AsyncClient(
            headers={"User-Agent": get_random_useragent()}
        ) as client:
            data = (await client.get(url)).text
            total_score = 0
            results.append(f"<b>{sanitize_link(url)}</b>")
            counts = {}
            for score, explanation, _ in explain_verification(data):
                counts[explanation] = counts.get(explanation, 0) + 1
                total_score += score
            for explanation, count in counts.items():
                results.append(f"<i>{explanation}</i>: <b>x{count}</b>")
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


@dp.message(Command("dump"))
async def on_dump(message: Message):
    logger.info(message.model_dump_json())
    kinky = ""
    if message.from_user and message.from_user.id != 548392265:
        kinky = " Too bad you probably can't read it"
    msg = await message.reply("Message JSON *should* be in logs now." + kinky)
    await sleep(3)
    await msg.delete()


@dp.message(Command("force"))
async def on_force(message: Message):
    if not message.reply_to_message:
        return
    reply = message.reply_to_message
    detected_links: list[tuple[str, float]] = []
    urls = []
    if reply.link_preview_options:
        urls.append(reply.link_preview_options.url)
    for entity in reply.entities or []:
        if entity.type in ("text_link", "url") and reply.text:
            if entity.type == "url":
                entity.url = reply.text[
                    entity.offset : entity.offset + entity.length
                ]
            if not entity.url:
                continue
            if not entity.url.startswith("http"):
                entity.url = "https://" + entity.url
            urls.append(entity.url)
    for url in urls:
        confidence = await verify_link(url)
        detected_links.append((url, confidence))
    n_links = len(detected_links)
    n_harmful = len(list(filter(lambda lnk: lnk[1] > 0.9, detected_links)))
    if n_harmful > 0:
        await reply.delete()
        await message.reply(
            f"Found {n_links} links, {n_harmful} of which look sus"
        )
    elif not detected_links:
        await message.reply(f"No links found")
    else:
        await message.reply(f"Out of {n_links}, none pass minimal threshold")


FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScPby92blkuDRcbsb9kAQ35tK3EXYtXVFwgGBMlp6REw_ZNgw/viewform"


def form_for(message: Message, link: str) -> str:
    assert message.from_user != None
    params = {
        "entry.1873578193": link,
        "entry.1733286388": (
            f"@{message.from_user.username}"
            if message.from_user.username
            else ""
        ),
    }
    return f"{FORM_URL}?{urlencode(params)}"


@dp.message()
async def on_message(message: Message):
    detected_links: list[tuple[str, float]] = []
    urls = []
    if message.link_preview_options:
        urls.append(message.link_preview_options.url)
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
            urls.append(entity.url)
    for url in urls:
        confidence = await verify_link(url)
        if confidence > 0.9:
            detected_links.append((url, confidence))
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
                        'False positive? Report <a href="%s">here</a>!'
                        % form_for(message, detected_links[0][0]),
                    ],
                ),
                parse_mode="html",
            )
            await sleep(20)
            await msg.delete()
