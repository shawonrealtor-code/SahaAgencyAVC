"""Keeps a fresh copy of the agency website's text for the concierge.

- Reads the home page, follows links on the same site (up to WEBSITE_MAX_PAGES).
- Keeps only readable text (no menus, scripts, or repeated footer lines).
- Saves to /app/cache/website.json so answers still work if the site is down.
- Refreshes on startup and every WEBSITE_REFRESH_HOURS.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("saha.website")

SITE_URL = os.getenv("WEBSITE_URL", "https://sahaagency.com").rstrip("/") + "/"
REFRESH_HOURS = float(os.getenv("WEBSITE_REFRESH_HOURS", "6"))
MAX_PAGES = int(os.getenv("WEBSITE_MAX_PAGES", "25"))
MAX_CHARS = int(os.getenv("WEBSITE_MAX_CHARS", "24000"))
CACHE_FILE = Path(os.getenv("WEBSITE_CACHE", "/app/cache/website.json"))

SKIP_EXTENSIONS = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".mp4", ".zip", ".css", ".js")
BLOCK_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd", "td", "th",
              "summary", "blockquote", "div", "section", "article", "header", "footer", "main", "nav", "ul", "ol"]
HEADERS = {"User-Agent": "SahaAgency-VirtualConcierge/1.0 (+site content sync)"}

_state = {"pages": [], "updated": None, "error": None, "refreshing": False}
_lock = asyncio.Lock()


# ---------- reading pages ----------

def _same_site(url: str) -> bool:
    base = urlparse(SITE_URL).netloc.removeprefix("www.")
    host = urlparse(url).netloc.removeprefix("www.")
    return host == base


def _clean_url(base: str, href: str) -> str | None:
    if not href or href.startswith(("mailto:", "tel:", "javascript:", "#")):
        return None
    url, _ = urldefrag(urljoin(base, href))
    url = url.split("?")[0].rstrip("/") + "/"
    if not url.startswith(("http://", "https://")) or not _same_site(url):
        return None
    if urlparse(url).path.lower().rstrip("/").endswith(SKIP_EXTENSIONS):
        return None
    return url


def extract_page(html: str, url: str) -> tuple[dict, list[str]]:
    """Return ({url, title, lines}, links) for one HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        clean = _clean_url(url, a["href"])
        if clean:
            links.append(clean)

    for tag in soup(["script", "style", "noscript", "svg", "iframe", "form", "button", "template"]):
        tag.decompose()

    title = (soup.title.get_text(" ", strip=True) if soup.title else "") or url
    body = soup.body or soup

    lines = []
    for block in body.find_all(BLOCK_TAGS):
        has_block_child = block.find(BLOCK_TAGS) is not None
        if has_block_child:
            # Text sitting directly in a container (not inside a child block).
            text = " ".join(
                s.strip() for s in block.find_all(string=True)
                if s.strip() and s.find_parent(BLOCK_TAGS) is block
            )
        else:
            text = block.get_text(" ", strip=True)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < 3:
            continue
        if block.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = f"## {text}"
        lines.append(text)

    # Remove exact duplicates within the page, keep order.
    seen, unique = set(), []
    for line in lines:
        if line not in seen:
            seen.add(line)
            unique.append(line)

    return {"url": url, "title": title, "lines": unique}, links


def _drop_repeated_lines(pages: list[dict]) -> None:
    """Menus and footers appear on every page; keep them only on the first page."""
    if len(pages) < 3:
        return
    counts: dict[str, int] = {}
    for page in pages:
        for line in set(page["lines"]):
            counts[line] = counts.get(line, 0) + 1
    repeated = {line for line, n in counts.items() if n >= max(3, len(pages) // 2 + 1)}
    for index, page in enumerate(pages):
        if index == 0:
            continue
        page["lines"] = [line for line in page["lines"] if line not in repeated]


async def crawl() -> list[dict]:
    pages, queue, visited = [], [SITE_URL], set()
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, headers=HEADERS) as client:
        while queue and len(pages) < MAX_PAGES:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                response = await client.get(url)
                if response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
                    continue
            except httpx.HTTPError as error:
                log.warning("Website page failed %s: %s", url, error)
                continue

            page, links = extract_page(response.text, str(response.url))
            if page["lines"]:
                pages.append(page)
            for link in links:
                if link not in visited and link not in queue:
                    queue.append(link)

    _drop_repeated_lines(pages)
    return pages


# ---------- cache + refresh ----------

def _load_cache() -> None:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        _state["pages"] = data.get("pages", [])
        _state["updated"] = data.get("updated")
    except (OSError, ValueError):
        pass


def _save_cache() -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps({"site": SITE_URL, "updated": _state["updated"], "pages": _state["pages"]},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as error:
        log.warning("Could not save website cache: %s", error)


async def refresh() -> dict:
    if _lock.locked():
        return status()
    async with _lock:
        _state["refreshing"] = True
        try:
            pages = await crawl()
            total = sum(len(" ".join(p["lines"])) for p in pages)
            if not pages or total < 200:
                raise RuntimeError("No readable text found on the website.")
            _state["pages"] = pages
            _state["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            _state["error"] = None
            _save_cache()
            log.info("Website synced: %d pages, %d characters", len(pages), total)
        except Exception as error:  # keep the last good copy
            _state["error"] = str(error)
            log.warning("Website sync failed, keeping previous copy: %s", error)
        finally:
            _state["refreshing"] = False
    return status()


async def refresh_forever() -> None:
    _load_cache()
    while True:
        await refresh()
        await asyncio.sleep(max(REFRESH_HOURS, 0.25) * 3600)


def status() -> dict:
    return {
        "site": SITE_URL,
        "updated": _state["updated"],
        "pages": [{"url": p["url"], "title": p["title"], "lines": len(p["lines"])} for p in _state["pages"]],
        "characters": sum(len(" ".join(p["lines"])) for p in _state["pages"]),
        "refreshing": _state["refreshing"],
        "last_error": _state["error"],
    }


def website_context() -> str:
    """Website text for the prompt (trimmed to MAX_CHARS)."""
    if not _state["pages"]:
        return "Website content is not available right now."
    parts = [f"Fetched from {SITE_URL} on {_state['updated']}."]
    for page in _state["pages"]:
        parts.append(f"\n=== PAGE: {page['title']} ({page['url']}) ===")
        parts.extend(page["lines"])
    text = "\n".join(parts)
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS] + "\n[website text shortened]"
