#!/usr/bin/env python3
"""
Crawler F1 minimal — collecte légère des dernières news (titres + URLs)
Sites: motorsport.com, autosport.com, actuf1.com
Sortie: knowledge_base/crawled/news_<site>.json + _crawl_metadata.json

Notes:
- Contenu ":headline" uniquement (pas d'articles complets) pour respecter les droits.
- Timeouts courts et User-Agent custom pour éviter les blocages.
- Idempotent: réécrit les fichiers à chaque exécution.
"""
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

import re
import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parents[1]
CRAWLED_DIR = BASE_DIR / "knowledge_base" / "crawled"
CRAWLED_DIR.mkdir(parents=True, exist_ok=True)
META_FILE = CRAWLED_DIR / "_crawl_metadata.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
TIMEOUT = 12
MAX_ITEMS = 20

SITES = [
    {
        "name": "motorsport",
        "url": "https://www.motorsport.com/f1/news/",
        "filter": re.compile(r"/f1/news/", re.I),
    },
    {
        "name": "autosport",
        "url": "https://www.autosport.com/f1/news/",
        "filter": re.compile(r"/f1/news/", re.I),
    },
    {
        "name": "actuf1",
        "url": "https://www.actuf1.com/",
        "filter": re.compile(r"/article/\d+", re.I),  # Articles uniquement /article/59856
    },
]


def fetch_page(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def extract_links(html: str, base_url: str, href_filter: re.Pattern) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[Dict[str, str]] = []

    # Cherche tous les liens <a> 
    for a in soup.find_all("a", href=True):
        if len(items) >= MAX_ITEMS:
            break
            
        href = a["href"]
        text = (a.get_text(strip=True) or "")
        
        if not text or len(text) < 3:
            continue
        
        # Vérifier le filtre
        if not href_filter.search(href):
            continue
        
        # Normaliser URL relative
        if href.startswith("/"):
            full = base_url.rstrip("/") + href
        elif href.startswith("http"):
            full = href
        else:
            full = base_url.rstrip("/") + "/" + href

        # Dédupliquer par URL
        if not any(it["url"] == full for it in items):
            items.append({"title": text, "url": full})

    # Fallback: si aucun lien trouvé, récupérer quelques headings
    if not items:
        for h in soup.find_all(["h1", "h2", "h3"]):
            t = h.get_text(strip=True)
            if t and len(t) > 5:
                items.append({"title": t, "url": base_url})
            if len(items) >= MAX_ITEMS:
                break

    return items


def save_json(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_metadata(site_name: str):
    now = datetime.now(timezone.utc).isoformat()
    meta = {}
    if META_FILE.exists():
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    meta.setdefault("last_crawl", {})
    meta.setdefault("sites", {})
    meta["version"] = 1
    meta["last_crawl"]["news"] = now
    meta["sites"][site_name] = now
    save_json(META_FILE, meta)


def crawl_site(site: Dict) -> Dict:
    name = site["name"]
    url = site["url"]
    filt = site["filter"]
    try:
        html = fetch_page(url)
        items = extract_links(html, url, filt)
        result = {
            "site": name,
            "source": url,
            "items": items,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
        save_json(CRAWLED_DIR / f"news_{name}.json", result)
        update_metadata(name)
        return {"site": name, "count": len(items), "ok": True}
    except Exception as e:
        save_json(CRAWLED_DIR / f"news_{name}.json", {
            "site": name,
            "source": url,
            "items": [],
            "error": str(e),
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        })
        update_metadata(name)
        return {"site": name, "count": 0, "ok": False, "error": str(e)}


def main():
    print("🕷️ Démarrage du crawler F1 minimal...")
    results = []
    for site in SITES:
        r = crawl_site(site)
        print(f"→ {r['site']}: {r['count']} items | ok={r['ok']}")
        results.append(r)
        time.sleep(0.5)  # petite pause pour courtoisie
    total = sum(r.get("count", 0) for r in results)
    ok_sites = sum(1 for r in results if r.get("ok"))
    print(f"✅ Terminé: {total} items sur {ok_sites}/{len(results)} sites.")


if __name__ == "__main__":
    main()
