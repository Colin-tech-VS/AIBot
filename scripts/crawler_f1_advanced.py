#!/usr/bin/env python3
"""
Crawler F1 AVANCÉ avec pagination/sitemap
Récupère toutes les news (pas juste la première page)
"""
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Set
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

BASE_DIR = Path(__file__).resolve().parents[1]
CRAWLED_DIR = BASE_DIR / "knowledge_base" / "crawled"
CRAWLED_DIR.mkdir(parents=True, exist_ok=True)
META_FILE = CRAWLED_DIR / "_crawl_metadata.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 12
MAX_ITEMS = 1000  # Augmenté pour scraper toutes les pages
MAX_PAGES = 15  # Nombre max de pages à crawler par site


class F1Crawler:
    """Crawler avec support pagination + sitemap"""
    
    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.items: List[Dict[str, str]] = []
    
    def fetch_page(self, url: str) -> str:
        """Récupère une page HTML"""
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            return r.text
        except Exception as e:
            print(f"  ❌ Error fetching {url}: {str(e)[:60]}")
            return ""
    
    def extract_links_from_html(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """Extrait tous les liens d'une page HTML"""
        soup = BeautifulSoup(html, "html.parser")
        items = []
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True)
            
            if not text or len(text) < 3:
                continue
            
            # Normaliser URL
            full_url = urljoin(base_url, href)
            
            # Éviter les doublons
            if full_url not in self.visited_urls:
                self.visited_urls.add(full_url)
                items.append({"title": text, "url": full_url})
        
        return items
    
    def crawl_motorsport(self) -> Dict:
        """Crawl Motorsport.com avec pagination - TOUTES les pages"""
        print("🕷️  Motorsport.com (crawling toutes les pages)...")
        
        base_url = "https://www.motorsport.com/f1/news/"
        
        # Crawl jusqu'à MAX_PAGES
        for page in range(1, MAX_PAGES + 1):
            page_url = f"{base_url}?page={page}"
            print(f"  → Page {page}/{MAX_PAGES}...", end=" ", flush=True)
            
            html = self.fetch_page(page_url)
            if not html:
                print("❌ Arrêt (page vide)")
                break
            
            links = self.extract_links_from_html(html, base_url)
            # Filtrer pour f1/news seulement
            f1_links = [l for l in links if "/f1/news/" in l["url"]]
            
            print(f"✅ {len(f1_links)} articles")
            self.items.extend(f1_links)
            
            if len(self.items) >= MAX_ITEMS:
                print(f"  ✅ Limite atteinte ({MAX_ITEMS} articles)")
                break
            time.sleep(0.3)
        
        return {
            "site": "motorsport",
            "source": base_url,
            "items": self.items[:MAX_ITEMS],
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def crawl_autosport(self) -> Dict:
        """Crawl Autosport.com avec pagination - TOUTES les pages"""
        print("🕷️  Autosport.com (crawling toutes les pages)...")
        
        self.items = []
        self.visited_urls.clear()
        
        base_url = "https://www.autosport.com/f1/news/"
        
        for page in range(1, MAX_PAGES + 1):
            page_url = f"{base_url}?page={page}"
            print(f"  → Page {page}/{MAX_PAGES}...", end=" ", flush=True)
            
            html = self.fetch_page(page_url)
            if not html:
                print("❌ Arrêt (page vide)")
                break
            
            links = self.extract_links_from_html(html, base_url)
            f1_links = [l for l in links if "/f1/news/" in l["url"]]
            
            print(f"✅ {len(f1_links)} articles")
            self.items.extend(f1_links)
            
            if len(self.items) >= MAX_ITEMS:
                print(f"  ✅ Limite atteinte ({MAX_ITEMS} articles)")
                break
            time.sleep(0.3)
        
        return {
            "site": "autosport",
            "source": base_url,
            "items": self.items[:MAX_ITEMS],
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def crawl_actuf1(self) -> Dict:
        """Crawl ActuF1 avec pagination - TOUTES les pages"""
        print("🕷️  ActuF1.com (crawling toutes les pages)...")
        
        self.items = []
        self.visited_urls.clear()
        
        base_url = "https://www.actuf1.com/"
        
        for page in range(1, MAX_PAGES + 1):
            page_url = f"{base_url}?page={page}"
            print(f"  → Page {page}/{MAX_PAGES}...", end=" ", flush=True)
            
            html = self.fetch_page(page_url)
            if not html:
                print("❌ Arrêt (page vide)")
                break
            
            links = self.extract_links_from_html(html, base_url)
            # Filtrer pour /article/ seulement
            article_links = [l for l in links if "/article/" in l["url"]]
            
            print(f"✅ {len(article_links)} articles")
            self.items.extend(article_links)
            
            if len(self.items) >= MAX_ITEMS:
                print(f"  ✅ Limite atteinte ({MAX_ITEMS} articles)")
                break
            time.sleep(0.3)
        
        return {
            "site": "actuf1",
            "source": base_url,
            "items": self.items[:MAX_ITEMS],
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def crawl_via_sitemap(self, sitemap_url: str, site_name: str) -> Dict:
        """Alterne: Crawl via sitemap.xml si disponible"""
        print(f"🗺️  {site_name} (sitemap.xml)...")
        
        try:
            html = self.fetch_page(sitemap_url)
            soup = BeautifulSoup(html, "xml")
            
            # Chercher tous les <loc> (URLs)
            urls = [loc.text for loc in soup.find_all("loc")]
            
            print(f"  → {len(urls)} URLs trouvées dans sitemap")
            
            items = [{"title": url.split("/")[-1], "url": url} for url in urls[:MAX_ITEMS]]
            
            return {
                "site": site_name,
                "source": sitemap_url,
                "items": items,
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            print(f"  ❌ Sitemap error: {str(e)[:60]}")
            return None


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


def main():
    print("🕷️ Crawler F1 AVANCÉ (avec pagination)\n")
    
    crawler = F1Crawler()
    results = []
    
    # Crawl chaque site
    data_motorsport = crawler.crawl_motorsport()
    save_json(CRAWLED_DIR / "news_motorsport.json", data_motorsport)
    update_metadata("motorsport")
    results.append({"site": "motorsport", "count": len(data_motorsport["items"]), "ok": True})
    
    data_autosport = crawler.crawl_autosport()
    save_json(CRAWLED_DIR / "news_autosport.json", data_autosport)
    update_metadata("autosport")
    results.append({"site": "autosport", "count": len(data_autosport["items"]), "ok": True})
    
    data_actuf1 = crawler.crawl_actuf1()
    save_json(CRAWLED_DIR / "news_actuf1.json", data_actuf1)
    update_metadata("actuf1")
    results.append({"site": "actuf1", "count": len(data_actuf1["items"]), "ok": True})
    
    # Résumé
    print()
    total = sum(r["count"] for r in results)
    print(f"✅ Crawling terminé")
    print(f"📊 Total: {total} articles crawlés")
    print(f"   Motorsport: {results[0]['count']} articles")
    print(f"   Autosport: {results[1]['count']} articles")
    print(f"   ActuF1: {results[2]['count']} articles")


if __name__ == "__main__":
    main()
