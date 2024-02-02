def sanitize_link(url: str) -> str:
    return url.replace("://", "[://]").replace(".", "[dot]")
