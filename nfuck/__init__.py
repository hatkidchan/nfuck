from os import getenv
from aiogram import Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from asyncio import sleep
from urllib.parse import urlencode
from logging import DEBUG, getLogger
from random import choice

from nfuck.link_verifier import verify_link
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

BOT_BLACKLIST: set[str] = set(getenv("BOT_BLACKLIST", "").split(","))


@dp.message(Command("dump"))
async def on_dump(message: Message):
    logger.info(message.model_dump_json())
    kinky = ""
    if message.from_user and message.from_user.id != 548392265:
        kinky = " Too bad you probably can't read it"
    msg = await message.reply("Message JSON *should* be in logs now." + kinky)
    await sleep(3)
    await msg.delete()


@dp.message(Command("isitakinkybot"))
async def on_is_kinky(message: Message):
    await message.reply(
        choice(
            [
                "Yes",
                "Very",
                "Perhaps",
                "Maybe",
                "Possibly",
                "Same as you",
                "Definitely",
                "Absolutely",
                "Meow :3",
                "If you insist",
            ]
        )
    )


@dp.message(Command("force"))
async def on_force(message: Message):
    if not message.reply_to_message:
        return
    reply = message.reply_to_message
    detected_links: list[tuple[str, float]] = []
    errored_links: list[tuple[str, Exception]] = []
    urls = []
    if reply.link_preview_options:
        urls.append(reply.link_preview_options.url)
    text = reply.caption or reply.text
    for entity in reply.caption_entities or reply.entities or []:
        if entity.type in ("text_link", "url") and text:
            if entity.type == "url":
                entity.url = text[
                    entity.offset : entity.offset + entity.length
                ]
            if not entity.url:
                continue
            if not entity.url.startswith("http"):
                entity.url = "https://" + entity.url
            urls.append(entity.url)
    for url in urls:
        try:
            confidence = await verify_link(url)
            detected_links.append((url, confidence))
        except Exception as e:
            errored_links.append((url, e))
    n_links = len(detected_links)
    n_harmful = len(list(filter(lambda lnk: lnk[1] > 0.9, detected_links)))

    response = ":shrug:"

    if n_harmful > 0:
        await reply.delete()
        response = f"Found {n_links} links, {n_harmful} of which look sus"
    elif not detected_links:
        response = f"No links found"
    else:
        response = f"Out of {n_links}, none pass minimal threshold"
    if errored_links:
        response += f"\n{len(errored_links)} links failed"
    await message.reply(response)


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
    text = message.caption or message.text
    for entity in message.caption_entities or message.entities or []:
        if entity.type in ("text_link", "url") and text:
            if entity.type == "url":
                entity.url = text[
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
