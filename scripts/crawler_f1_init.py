#!/usr/bin/env python3
"""
Crawler F1 INITIAL - Crawl complet (15 pages)
À exécuter UNE SEULE FOIS pour créer la base de données complète
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
from urllib.parse import urljoin

BASE_DIR = Path(__file__).resolve().parents[1]
CRAWLED_DIR = BASE_DIR / "knowledge_base" / "crawled"
CRAWLED_DIR.mkdir(parents=True, exist_ok=True)
META_FILE = CRAWLED_DIR / "_crawl_metadata.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
TIMEOUT = 12
MAX_PAGES_INITIAL = 1  # JUSTE PAGE 1 - Suffisant + rapide


def fetch_page(url: str) -> str:
    """Récupère une page HTML"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"    ❌ Erreur: {str(e)[:50]}")
        return ""


def extract_links(html: str, base_url: str, filter_pattern: str) -> List[Dict[str, str]]:
    """Extrait les liens d'une page"""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    visited = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        
        if not text or len(text) < 3:
            continue
        
        # Normaliser URL
        full_url = urljoin(base_url, href)
        
        # Filtrer
        if filter_pattern not in full_url:
            continue
        
        # Éviter doublons
        if full_url in visited:
            continue
        visited.add(full_url)
        
        items.append({"title": text, "url": full_url})
    
    return items


def crawl_site_initial(site_name: str, base_url: str, filter_pattern: str) -> Dict:
    """Crawl un site complet (15 pages)"""
    print(f"🕷️  {site_name.upper()} (crawl INITIAL - 15 pages)")
    
    all_items = []
    visited_urls = set()
    
    for page in range(1, MAX_PAGES_INITIAL + 1):
        page_url = f"{base_url}?page={page}"
        print(f"  → Page {page:2d}/{MAX_PAGES_INITIAL}...", end=" ", flush=True)
        
        html = fetch_page(page_url)
        if not html:
            print("❌ Vide")
            break
        
        links = extract_links(html, base_url, filter_pattern)
        # Ajouter seulement les nouveaux liens
        new_links = [l for l in links if l["url"] not in visited_urls]
        visited_urls.update(l["url"] for l in new_links)
        
        print(f"✅ {len(new_links)} articles")
        all_items.extend(new_links)
        
        time.sleep(0.5)  # Courtoisie
    
    return {
        "site": site_name,
        "source": base_url,
        "items": all_items,
        "total_crawled": len(all_items),
        "pages_crawled": page,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "type": "INITIAL"
    }


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
    meta["crawl_type"] = "INITIAL"
    save_json(META_FILE, meta)


def main():
    print("=" * 70)
    print("🕷️  Crawler F1 INITIAL (Création Base Complète)")
    print("=" * 70)
    print()
    
    results = []
    
    # Motorsport
    data = crawl_site_initial("motorsport", "https://www.motorsport.com/f1/news/", "/f1/news/")
    save_json(CRAWLED_DIR / "news_motorsport.json", data)
    update_metadata("motorsport")
    results.append(data)
    print()
    
    # Autosport
    data = crawl_site_initial("autosport", "https://www.autosport.com/f1/news/", "/f1/news/")
    save_json(CRAWLED_DIR / "news_autosport.json", data)
    update_metadata("autosport")
    results.append(data)
    print()
    
    # ActuF1
    data = crawl_site_initial("actuf1", "https://www.actuf1.com/", "/article/")
    save_json(CRAWLED_DIR / "news_actuf1.json", data)
    update_metadata("actuf1")
    results.append(data)
    print()
    
    # Résumé
    print("=" * 70)
    total = sum(r["total_crawled"] for r in results)
    print(f"✅ CRAWLING INITIAL TERMINÉ")
    print(f"📊 RÉSUMÉ:")
    for r in results:
        print(f"   {r['site']:15s}: {r['total_crawled']:4d} articles ({r['pages_crawled']} pages)")
    print(f"   {'TOTAL':15s}: {total:4d} articles")
    print("=" * 70)
    print()
    print("💡 Prochains crawls: chaque lundi via crawler_f1_weekly.py")


if __name__ == "__main__":
    main()
