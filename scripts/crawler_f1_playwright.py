#!/usr/bin/env python3
"""
Crawler F1 avec Playwright - Supporte JavaScript et pagination réelle
Récupère TOUTES les pages via navigateur automatisé
"""
import json
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
from playwright.async_api import async_playwright, Page
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parents[1]
CRAWLED_DIR = BASE_DIR / "knowledge_base" / "crawled"
CRAWLED_DIR.mkdir(parents=True, exist_ok=True)
META_FILE = CRAWLED_DIR / "_crawl_metadata.json"

MAX_ITEMS = 1000
MAX_PAGES = 15  # Nombre de pages à crawler


class PlaywrightF1Crawler:
    """Crawler avec Playwright pour gérer JavaScript"""
    
    def __init__(self):
        self.items: List[Dict[str, str]] = []
        self.visited_urls = set()
    
    async def crawl_site(self, site_name: str, base_url: str, page_filter: str) -> Dict:
        """Crawl un site avec pagination via Playwright"""
        print(f"🕷️  {site_name.upper()}")
        
        self.items = []
        self.visited_urls.clear()
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            for page_num in range(1, MAX_PAGES + 1):
                page_url = f"{base_url}?page={page_num}"
                print(f"  → Page {page_num}/{MAX_PAGES}...", end=" ", flush=True)
                
                try:
                    # Ouvrir une nouvelle page
                    page = await browser.new_page()
                    await page.goto(page_url, wait_until="networkidle", timeout=30000)
                    
                    # Attendre un peu pour que JavaScript finisse
                    await page.wait_for_timeout(1000)
                    
                    # Récupérer le contenu HTML
                    html = await page.content()
                    
                    # Fermer la page
                    await page.close()
                    
                    # Parser HTML
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Chercher les liens selon le filtre
                    links = soup.find_all('a', href=True)
                    filtered_links = [
                        {
                            "title": l.get_text(strip=True),
                            "url": l['href']
                        }
                        for l in links
                        if l.get_text(strip=True) and len(l.get_text(strip=True)) > 3
                        and page_filter in l.get('href', '')
                        and l['href'] not in self.visited_urls
                    ]
                    
                    # Ajouter les nouveaux liens
                    for link in filtered_links:
                        if link['url'] not in self.visited_urls:
                            self.visited_urls.add(link['url'])
                            self.items.append(link)
                    
                    print(f"✅ {len(filtered_links)} articles")
                    
                    # Arrêter si limite atteinte
                    if len(self.items) >= MAX_ITEMS:
                        print(f"  ✅ Limite atteinte ({MAX_ITEMS} articles)")
                        break
                    
                except Exception as e:
                    print(f"❌ Erreur: {str(e)[:50]}")
                    continue
            
            await browser.close()
        
        return {
            "site": site_name,
            "source": base_url,
            "items": self.items[:MAX_ITEMS],
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }


async def main():
    print("=" * 70)
    print("🕷️  Crawler F1 avec Playwright (JavaScript + Pagination Réelle)")
    print("=" * 70)
    print()
    
    crawler = PlaywrightF1Crawler()
    
    # Crawl Motorsport
    print("Démarrage Motorsport...")
    motorsport_data = await crawler.crawl_site(
        "motorsport",
        "https://www.motorsport.com/f1/news/",
        "/f1/news/"
    )
    save_json(CRAWLED_DIR / "news_motorsport.json", motorsport_data)
    update_metadata("motorsport")
    print()
    
    # Crawl Autosport
    print("Démarrage Autosport...")
    autosport_data = await crawler.crawl_site(
        "autosport",
        "https://www.autosport.com/f1/news/",
        "/f1/news/"
    )
    save_json(CRAWLED_DIR / "news_autosport.json", autosport_data)
    update_metadata("autosport")
    print()
    
    # Crawl ActuF1
    print("Démarrage ActuF1...")
    actuf1_data = await crawler.crawl_site(
        "actuf1",
        "https://www.actuf1.com/",
        "/article/"
    )
    save_json(CRAWLED_DIR / "news_actuf1.json", actuf1_data)
    update_metadata("actuf1")
    print()
    
    # Résumé
    print("=" * 70)
    total = (
        len(motorsport_data["items"]) +
        len(autosport_data["items"]) +
        len(actuf1_data["items"])
    )
    print(f"✅ Crawling TERMINÉ")
    print(f"📊 Résumé:")
    print(f"   Motorsport: {len(motorsport_data['items'])} articles")
    print(f"   Autosport: {len(autosport_data['items'])} articles")
    print(f"   ActuF1: {len(actuf1_data['items'])} articles")
    print(f"   TOTAL: {total} articles crawlés")
    print("=" * 70)


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


if __name__ == "__main__":
    asyncio.run(main())
