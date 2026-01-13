"""Crawler léger pour récupérer des URLs F1 pertinentes.

- Parcourt les sitemaps et explore en profondeur limitée.
- Filtre les URLs par motifs autorisés (news, résultats, pilotes, teams, standings).
- Écrit la liste dédupliquée dans knowledge_base/f1_urls.txt.

Usage:
    python f1_crawler.py

Prérequis:
    pip install requests beautifulsoup4 lxml
"""
from __future__ import annotations
import time
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path
from typing import Iterable, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

# =========================
# CONFIGURATION
# =========================
START_URLS = [
    "https://www.formula1.com/",
    "https://www.motorsport.com/f1/",
]

SITEMAPS = [
    "https://www.formula1.com/sitemap.xml",
    "https://www.motorsport.com/sitemap.xml",
]

ALLOWED_PATTERNS = [
    "/news/",
    "/results/",
    "/drivers/",
    "/teams/",
    "/standings/",
    "/race-result",
]

MAX_DEPTH = 2
REQUEST_DELAY = 1.5  # secondes
HEADERS = {
    "User-Agent": "F1-AI-Bot/1.0 (contact: contact@example.com)",
}

OUTPUT_FILE = Path(__file__).parent / "f1_urls.txt"

visited: Set[str] = set()
collected_urls: Set[str] = set()


# =========================
# SITEMAP PARSER
# =========================
def parse_sitemap(sitemap_url: str) -> Set[str]:
    urls: Set[str] = set()
    try:
        resp = httpx.get(sitemap_url, headers=HEADERS, timeout=10, follow_redirects=True)
        if resp.status_code != 200:
            return urls
        root = ET.fromstring(resp.content)
        for loc in root.iter():
            if "loc" in loc.tag and loc.text:
                urls.add(loc.text.strip())
    except Exception as exc:
        print(f"[SITEMAP ERROR] {sitemap_url} -> {exc}")
    return urls


# =========================
# LINK FILTER
# =========================
def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    path = parsed.path or ""
    return any(pattern in path for pattern in ALLOWED_PATTERNS)


# =========================
# PAGE CRAWLER (BFS)
# =========================
def crawl(start_url: str, max_depth: int = MAX_DEPTH) -> None:
    queue: deque[tuple[str, int]] = deque()
    queue.append((start_url, 0))

    while queue:
        url, depth = queue.popleft()
        if depth > max_depth:
            continue
        if url in visited:
            continue
        visited.add(url)

        try:
            print(f"[CRAWL] depth={depth} {url}")
            resp = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            for link in soup.find_all("a", href=True):
                absolute = urljoin(url, link["href"])
                absolute = absolute.split("#")[0]
                if is_valid_url(absolute):
                    collected_urls.add(absolute)
                    queue.append((absolute, depth + 1))
            time.sleep(REQUEST_DELAY)
        except Exception as exc:
            print(f"[ERROR] {url} -> {exc}")


# =========================
# MAIN
# =========================
def run() -> None:
    print("\n🔍 Parsing sitemaps...")
    for sitemap in SITEMAPS:
        urls = parse_sitemap(sitemap)
        for u in urls:
            if is_valid_url(u):
                collected_urls.add(u)
    print(f"✔️ URLs from sitemaps: {len(collected_urls)}")

    print("\n🕷️ Crawling sites...")
    for start in START_URLS:
        crawl(start, MAX_DEPTH)

    print(f"\n📦 TOTAL URLs COLLECTED: {len(collected_urls)}")
    OUTPUT_FILE.write_text("\n".join(sorted(collected_urls)), encoding="utf-8")
    print(f"✅ URLs saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    run()
