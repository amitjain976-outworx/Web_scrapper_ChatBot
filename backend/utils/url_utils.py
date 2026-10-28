from urllib.parse import urlparse, urljoin, urldefrag
from typing import Set
import re


# =========================
# NORMALIZATION
# =========================

def normalize_url(url: str) -> str:
    """
    Normalize URL for crawl deduplication:
    - strip fragments (#)
    - lowercase scheme + hostname
    - remove trailing slash (except root)
    - collapse duplicate slashes
    """
    if not url:
        return ""

    url = url.strip()

    # Remove fragment (#section)
    url, _ = urldefrag(url)

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # Normalize path
    path = re.sub(r"/{2,}", "/", parsed.path or "/")

    # Remove trailing slash except root
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    normalized = f"{scheme}://{netloc}{path}"

    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


# =========================
# URL JOINING
# =========================

def resolve_url(base_url: str, link: str) -> str:
    """
    Resolve relative links against base URL
    """
    if not link:
        return ""

    return normalize_url(urljoin(base_url, link))


# =========================
# DOMAIN CHECK
# =========================

def is_same_domain(url: str, root_domain: str) -> bool:
    """
    Ensure crawl stays within the same domain
    """
    try:
        return urlparse(url).netloc == urlparse(root_domain).netloc
    except Exception:
        return False


# =========================
# FILTERS
# =========================

def is_valid_http_url(url: str) -> bool:
    """
    Accept only http/https URLs
    """
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"}
    except Exception:
        return False


def should_ignore_url(url: str) -> bool:
    """
    Filter out non-crawlable or useless URLs
    """
    ignore_patterns = (
        r"\.pdf$",
        r"\.jpg$",
        r"\.jpeg$",
        r"\.png$",
        r"\.gif$",
        r"\.svg$",
        r"\.zip$",
        r"\.exe$",
        r"\.mp4$",
        r"\.mp3$",
        r"\.avi$",
        r"mailto:",
        r"tel:",
        r"javascript:",
    )

    for pattern in ignore_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True

    return False


# =========================
# LINK EXTRACTION PIPELINE
# =========================

def filter_and_normalize_links(
    base_url: str,
    links: Set[str],
    root_domain: str,
) -> Set[str]:
    """
    Full link pipeline used by crawler:
    - resolve relative URLs
    - normalize
    - drop non-http links
    - same-domain enforcement
    - ignore unwanted resources
    """
    results: Set[str] = set()

    for link in links:
        resolved = resolve_url(base_url, link)

        if not resolved:
            continue

        if not is_valid_http_url(resolved):
            continue

        if not is_same_domain(resolved, root_domain):
            continue

        if should_ignore_url(resolved):
            continue

        results.add(resolved)

    return results
