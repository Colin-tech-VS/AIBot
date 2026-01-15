#!/usr/bin/env python3
"""
Crawler F1 HEBDO - Crawl léger (page 1 seulement)
Exécuté chaque LUNDI pour actualiser les données
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


def load_existing_articles(site_name: str) -> set:
    """Charge les articles existants pour éviter les doublons"""
    file_path = CRAWLED_DIR / f"news_{site_name}.json"
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(item["url"] for item in data.get("items", []))
        except Exception:
            return set()
    return set()


def crawl_site_weekly(site_name: str, base_url: str, filter_pattern: str) -> Dict:
    """Crawl un site légèrement (page 1 seulement) + fusion avec existant"""
    print(f"🕷️  {site_name.upper()} (actualisation hebdo)")
    
    # Charger les articles existants
    existing_urls = load_existing_articles(site_name)
    print(f"    📚 Articles existants: {len(existing_urls)}")
    
    # Crawl page 1
    page_url = f"{base_url}?page=1"
    print(f"    → Page 1...", end=" ", flush=True)
    
    html = fetch_page(page_url)
    if not html:
        print("❌ Vide")
        return None
    
    new_links = extract_links(html, base_url, filter_pattern)
    
    # Filtrer les nouveaux (qui n'existaient pas)
    truly_new = [l for l in new_links if l["url"] not in existing_urls]
    print(f"✅ {len(truly_new)} nouveaux articles")
    
    # Charger les anciennes données
    file_path = CRAWLED_DIR / f"news_{site_name}.json"
    old_data = {"items": []}
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            pass
    
    # Fusionner: nouveaux articles en premier + anciens articles
    merged_items = truly_new + old_data.get("items", [])
    
    # Garder seulement 1000 items (limiter la taille du fichier)
    merged_items = merged_items[:1000]
    
    return {
        "site": site_name,
        "source": base_url,
        "items": merged_items,
        "total_items": len(merged_items),
        "new_items": len(truly_new),
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "type": "WEEKLY"
    }


def save_json(path: Path, data: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_metadata(site_name: str, new_items: int):
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
    meta[f"{site_name}_new_items"] = new_items
    meta["crawl_type"] = "WEEKLY"
    save_json(META_FILE, meta)


def main():
    print("=" * 70)
    print("🕷️  Crawler F1 HEBDO (Actualisation Page 1 - Lundi)")
    print("=" * 70)
    print()
    
    results = []
    
    # Motorsport
    data = crawl_site_weekly("motorsport", "https://www.motorsport.com/f1/news/", "/f1/news/")
    if data:
        save_json(CRAWLED_DIR / "news_motorsport.json", data)
        update_metadata("motorsport", data["new_items"])
        results.append(data)
    print()
    
    # Autosport
    data = crawl_site_weekly("autosport", "https://www.autosport.com/f1/news/", "/f1/news/")
    if data:
        save_json(CRAWLED_DIR / "news_autosport.json", data)
        update_metadata("autosport", data["new_items"])
        results.append(data)
    print()
    
    # ActuF1
    data = crawl_site_weekly("actuf1", "https://www.actuf1.com/", "/article/")
    if data:
        save_json(CRAWLED_DIR / "news_actuf1.json", data)
        update_metadata("actuf1", data["new_items"])
        results.append(data)
    print()
    
    # Résumé
    print("=" * 70)
    total_new = sum(r["new_items"] for r in results)
    total_items = sum(r["total_items"] for r in results)
    print(f"✅ ACTUALISATION HEBDO TERMINÉE")
    print(f"📊 RÉSUMÉ:")
    for r in results:
        print(f"   {r['site']:15s}: {r['new_items']:3d} nouveaux + {r['total_items'] - r['new_items']:4d} existants = {r['total_items']:4d} total")
    print(f"   {'TOTAL':15s}: {total_new:3d} nouveaux, {total_items:4d} items total")
    print("=" * 70)


if __name__ == "__main__":
    main()
