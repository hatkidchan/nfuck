from httpx import AsyncClient
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

REGEX_PATTERNS: list[tuple[float, Pattern, str]] = [
    (1.0, regexp(r"\bp2e\b", IGNORECASE), "Play-to-earn keyword"),
    (5.0, regexp(r"play\-to\-earn", IGNORECASE), "Play-to-earn directly"),
    (3.0, regexp(r"encryption\.js", IGNORECASE), "encryption.js"),
    (3.0, regexp(r"web3-ethers\.js", IGNORECASE), "web3-ethers.js"),
    (1.0, regexp(r"\bweb3\b", IGNORECASE), "Web3 mention"),
    (1.0, regexp(r"\bnft\b", IGNORECASE), "NFT mention"),
    (3.0, regexp(r"What The Fluff | CLAIM ALL !", IGNORECASE), "WTF Claim all"),
    (3.0, regexp(r"Suckerberg's Nutsack", IGNORECASE), "Suckerberg balls"),
    (4.0, regexp(r"\w+: Claim your first \w+ and lets P2E", IGNORECASE), "Claim your first bs"),
    (5.0, regexp(r"https://twitter\.com/what_thefluff"), "Link to what the fluff twitter"),
    (3.0, regexp(r"Discover what \&nbsp;\w+ will become your", IGNORECASE), "Some random button from common scam website"),
    (3.0, regexp(r"fluff (token|coin)", IGNORECASE), "fluff token/coin"),
    (3.0, regexp(r"A collection of \w+ NFTs", IGNORECASE), "Collection of [some] NFTs"),
]

MAX_SCORE = sum(t[0] for t in REGEX_PATTERNS)


def explain_verification(content: str) -> list[tuple[float, str, Match]]:
    result: list[tuple[float, str, Match]] = []
    for score, regex, explanation in REGEX_PATTERNS:
        for match in regex.finditer(content):
            result.append((score, explanation, match))
    return result


def get_random_useragent() -> str:
    return choice(USER_AGENT)


async def verify_link(url: str) -> float:
    total_score = 0
    logger.info("Verifying link %s", url)
    if not url.startswith("http"):
        url = "https://" + url
    domain = urlparse(url).netloc
    if any(fnmatch(domain, pat) for pat in DOMAIN_WHITELIST):
        logger.info("Score for %r: 0 (whitelisted domain)", url)
        return 0
    async with AsyncClient(
        headers={"User-Agent": get_random_useragent()}
    ) as client:
        data = await client.get(url)
        for score, explanation, match in explain_verification(data.text):
            logger.debug("%s: %s at %d", url, explanation, match.start())
            total_score += score
    logger.info("Score for %r: %f", url, total_score)
    return total_score / MAX_SCORE
