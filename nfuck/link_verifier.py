from httpx import AsyncClient
from re import Match, Pattern, compile as regexp, IGNORECASE
from random import choice
from logging import DEBUG, getLogger

logger = getLogger("nfuck.link_verifier")
logger.setLevel(DEBUG)

USER_AGENT = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0"
]

REGEX_PATTERNS: list[tuple[float, Pattern, str]] = [
    (1.0, regexp(r"\bp2e\b", IGNORECASE), "Play-to-earn keyword"),
    (5.0, regexp(r"play\-to\-earn", IGNORECASE), "Play-to-earn directly"),
    (3.0, regexp(r"encryption\.js", IGNORECASE), "Metamask"),
    (2.0, regexp(r"\bweb3\b", IGNORECASE), "Web3 mention"),
    (1.0, regexp(r"\bnft\b", IGNORECASE), "NFT mention"),
    (0.7, regexp(r"\belon\b", IGNORECASE), "Cryptobro Elon"),
    (0.5, regexp(r"\bbiden\b", IGNORECASE), "Sleepy Joe"),
    (1.0, regexp(r"\bcrypto\b", IGNORECASE), "Crypto mention"),
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
    async with AsyncClient(
        headers={"User-Agent": get_random_useragent()}
    ) as client:
        data = await client.get(url)
        for score, explanation, match in explain_verification(data.text):
            logger.debug("%s: %s at %d", url, explanation, match.start())
            total_score += score
    logger.info("Score for %r: %f", url, total_score)
    return total_score / MAX_SCORE
