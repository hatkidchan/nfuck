from typing import NamedTuple, Optional
from httpx import AsyncClient, AsyncHTTPTransport
from re import Match, Pattern, compile as regexp, IGNORECASE
from random import choice
from logging import DEBUG, getLogger
from os import getenv
from urllib.parse import urlparse
from fnmatch import fnmatch

logger = getLogger("nfuck.link_verifier")
logger.setLevel(DEBUG)

# TODO: get it out of here somehow
DOMAIN_WHITELIST: set[str] = set(filter(lambda v: v, getenv("DOMAIN_WHITELIST", "").split(",")))

USER_AGENT = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0"
]

URL_PATTERNS: list[tuple[float, Pattern, str]] = [
    (30.0, regexp(r"https://t.me/\w+[bB]ot/claim"), "Telegram Bot claim link")
]

REGEX_PATTERNS: list[tuple[float, Pattern, str]] = [
    (1.0, regexp(r"\bp2e\b", IGNORECASE), "Play-to-earn keyword"),
    (5.0, regexp(r"play\-to\-earn", IGNORECASE), "Play-to-earn directly"),
    (15.0, regexp(r"encryption\.js", IGNORECASE), "encryption.js"),
    (30.0, regexp(r"web3-ethers\.js", IGNORECASE), "web3-ethers.js"),
    (1.0, regexp(r"\bweb3\b", IGNORECASE), "Web3 mention"),
    (1.0, regexp(r"\bnft\b", IGNORECASE), "NFT mention"),
    (3.0, regexp(r"What The Fluff | CLAIM ALL !", IGNORECASE), "WTF Claim all"),
    (3.0, regexp(r"Suckerberg's Nutsack", IGNORECASE), "Suckerberg balls"),
    (4.0, regexp(r"\w+: Claim your first \w+ and lets P2E", IGNORECASE), "Claim your first bs"),
    (5.0, regexp(r"https://twitter\.com/what_thefluff"), "Link to what the fluff twitter"),
    (3.0, regexp(r"Discover what \&nbsp;\w+ will become your", IGNORECASE), "Some random button from common scam website"),
    (3.0, regexp(r"fluff (token|coin)", IGNORECASE), "fluff token/coin"),
    (3.0, regexp(r"A collection of \w+ NFTs", IGNORECASE), "Collection of [some] NFTs"),
    (5.0, regexp(r"claim free \$\w+", IGNORECASE), "Claim free shitcoin"),
    (5.0, regexp(r"avoid obstacles to gain \$\w+", IGNORECASE), "play to gain"),
    (5.0, regexp(r"fetch free crypto rewards", IGNORECASE), "free crypto! yay!"),
    (12.0, regexp(r"melondrop.app", IGNORECASE), "Sus developer URL"),
    (12.0, regexp(r"airdrop-blum.fun", IGNORECASE), "Blum airdrop"),
    (8, regexp(r"Claim \w+ and \w+ them all", IGNORECASE), "Claim X and X them all"),
    (4, regexp(r"choose \w+. connect wallet", IGNORECASE), "We all can hear you, stop saying it bajilion times")
]

MAX_SCORE = 30 # sum(t[0] for t in REGEX_PATTERNS)

transport = AsyncHTTPTransport(retries=5)

def explain_verification(content: str) -> list[tuple[float, str, Match]]:
    result: list[tuple[float, str, Match]] = []
    for score, regex, explanation in REGEX_PATTERNS:
        for match in regex.finditer(content):
            result.append((score, explanation, match))
    return result


def get_random_useragent() -> str:
    return choice(USER_AGENT)


async def recurse_into_telegraph(url: str, _depth: int = 0) -> float:
    parsed_url = urlparse(url)
    page_id = parsed_url.path.lstrip("/")

    def _tgraph_find_links(tag: dict | str) -> list[str]:
        if isinstance(tag, str):
            return []
        if tag["tag"] == "a":
            return [tag["attrs"]["href"]]
        else:
            return sum([
                _tgraph_find_links(child)
                for child in tag.get("children", [])
            ], start=[])

    total_score = 0
    async with AsyncClient(
        headers={"User-Agent": get_random_useragent()},
        follow_redirects=True,
        max_redirects=32,
        transport=transport
    ) as client:
        page = (await client.get(f"https://api.telegra.ph/getPage/{page_id}", params={
            "return_content": True
        })).json()["result"]
        for element in page["content"]:
            for link in _tgraph_find_links(element):
                logger.info("Going deeper into %s", link)
                total_score += await verify_link(link, _depth + 1)
    logger.info("Recursive Telegraph returned: %f", total_score)
    return total_score * MAX_SCORE


async def verify_link(url: str, _depth: int = 0) -> float:
    if not url: return 0
    if _depth > 10:
        logger.error("Too deep, bailing out!")
        return 0
    total_score = 0
    logger.info("Verifying link %s", url)
    if not url.startswith("http"):
        url = "https://" + url
    domain = urlparse(url).netloc
    if any(fnmatch(domain, pat) for pat in DOMAIN_WHITELIST):
        logger.info("Score for %r: 0 (whitelisted domain)", url)
        return 0
    for score, regex, explanation in URL_PATTERNS:
        for match in regex.finditer(url):
            total_score += score
    async with AsyncClient(
        headers={"User-Agent": get_random_useragent()},
        follow_redirects=True,
        max_redirects=32,
        transport=transport
    ) as client:
        data = await client.get(url)
        for score, explanation, match in explain_verification(data.text):
            logger.debug("%s: %s at %d", url, explanation, match.start())
            total_score += score

    if domain == "telegra.ph":
        total_score += await recurse_into_telegraph(url, _depth + 1)

    logger.info("Score for %r: %f", url, total_score)

    return total_score / MAX_SCORE
