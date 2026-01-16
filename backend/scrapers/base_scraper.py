"""🕷️ Classe abstraite pour scrapers F1 avec retry & rate limiting"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import httpx
from bs4 import BeautifulSoup
from backend.logger import get_logger
import json
from datetime import datetime
import time
import os

logger = get_logger(__name__)


class BaseScraper(ABC):
    """Scraper F1 générique sécurisé"""
    
    def __init__(self, source_name: str, base_url: str):
        self.source_name = source_name
        self.base_url = base_url
        self.cache_dir = "knowledge_base/crawled"
        self.cache_file = os.path.join(self.cache_dir, f"{source_name}.json")
        
        # 🔒 Session HTTP avec headers anti-détection
        self.session = httpx.Client(
            timeout=10.0,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }
        )
        
        # 🔒 Rate limiting (1 req/sec)
        self.last_request_time = 0
        self.min_delay = 1.0
        
        # Créer dossier cache
        os.makedirs(self.cache_dir, exist_ok=True)
    
    @abstractmethod
    def parse_article(self, soup: BeautifulSoup, url: str) -> Optional[Dict]:
        """Parser un article (implémenté par scraper spécifique)"""
        pass
    
    @abstractmethod
    def get_article_urls(self) -> List[str]:
        """Récupérer URLs articles à scraper"""
        pass
    
    def fetch_html(self, url: str, retry: int = 3) -> Optional[BeautifulSoup]:
        """Récupérer HTML avec retry exponentiel et rate limiting"""
        # 🔒 Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        
        for attempt in range(retry):
            try:
                self.last_request_time = time.time()
                response = self.session.get(url)
                response.raise_for_status()
                return BeautifulSoup(response.text, 'html.parser')
            
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Too Many Requests
                    wait = 2 ** attempt
                    logger.warning(f"⏳ Rate limit {url}, attente {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"❌ HTTP {e.response.status_code} pour {url}")
                    return None
            
            except Exception as e:
                logger.error(f"❌ Fetch error {url} (tentative {attempt+1}/{retry}): {e}")
                if attempt < retry - 1:
                    time.sleep(1)
        
        return None
    
    def scrape_all(self, max_articles: int = 15) -> List[Dict]:
        """🕷️ Scraper N articles récents"""
        logger.info(f"🕷️ Scraping {self.source_name}...")
        
        urls = self.get_article_urls()[:max_articles]
        articles = []
        
        for i, url in enumerate(urls, 1):
            logger.info(f"  📄 [{i}/{len(urls)}] {url[:60]}...")
            soup = self.fetch_html(url)
            
            if soup:
                article = self.parse_article(soup, url)
                if article:
                    articles.append(article)
                    logger.info(f"    ✅ {article['title'][:50]}...")
                else:
                    logger.warning(f"    ⚠️ Parse failed")
            else:
                logger.warning(f"    ❌ Fetch failed")
        
        if articles:
            self._save_to_cache(articles)
            logger.info(f"✅ {self.source_name}: {len(articles)}/{len(urls)} articles scrapés")
        else:
            logger.error(f"❌ {self.source_name}: 0 articles récupérés")
        
        return articles
    
    def _save_to_cache(self, articles: List[Dict]):
        """💾 Sauvegarder au format KB (JSON)"""
        # Charger existant + fusionner (éviter doublons)
        existing = self.load_from_cache()
        
        # Déduplication par URL
        all_articles = {a['url']: a for a in existing + articles}
        
        # Garder 100 plus récents (rotation)
        sorted_articles = sorted(
            all_articles.values(),
            key=lambda x: x.get('date', ''),
            reverse=True
        )[:100]
        
        data = {
            "source": self.source_name,
            "scraped_at": datetime.now().isoformat(),
            "count": len(sorted_articles),
            "articles": sorted_articles
        }
        
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Sauvegardé: {self.cache_file}")
    
    def load_from_cache(self) -> List[Dict]:
        """📂 Charger depuis cache si existe"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('articles', [])
            except Exception as e:
                logger.warning(f"⚠️ Erreur lecture cache {self.cache_file}: {e}")
        return []
    
    def __del__(self):
        """Fermer session HTTP proprement"""
        try:
            self.session.close()
        except:
            pass
