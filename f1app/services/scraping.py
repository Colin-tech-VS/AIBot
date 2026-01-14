"""
Service Scraping - Scrapers pour les sites F1.
Extrait de f1_bot.py pour modularité.
"""

import random
import time
from typing import List, Optional
from functools import wraps

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

from f1app.config import (
    SCRAPING_TIMEOUT, USER_AGENTS, F1_SOURCES,
    SCRAPING_DELAY_MIN, SCRAPING_DELAY_MAX
)
from backend.logger import get_logger
from backend.optimized_cache import get_cache

logger = get_logger(__name__)
_cache = get_cache()


class NewsItem(BaseModel):
    """Modèle pour un article d'actualité."""
    source: str
    content: str = Field(min_length=10, max_length=2000)
    url: Optional[str] = None


def get_random_headers() -> dict:
    """Retourne des headers HTTP avec User-Agent aléatoire."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
    }


def retry_with_backoff(max_attempts: int = 2, base_delay: float = 0.5, max_delay: float = 3.0):
    """Décorateur pour retry avec backoff exponentiel."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


def fetch_url(url: str, timeout: int = None) -> Optional[str]:
    """Récupère le contenu HTML d'une URL.
    
    Args:
        url: L'URL à récupérer
        timeout: Timeout en secondes (défaut: config)
        
    Returns:
        Le contenu HTML ou None si erreur
    """
    timeout = timeout or SCRAPING_TIMEOUT
    try:
        response = httpx.get(
            url,
            headers=get_random_headers(),
            timeout=timeout,
            follow_redirects=True
        )
        response.raise_for_status()
        return response.text
    except httpx.TimeoutException:
        logger.warning(f"Timeout fetching {url}")
        return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP {e.response.status_code} fetching {url}")
        return None
    except Exception as e:
        logger.warning(f"Error fetching {url}: {e}")
        return None


def extract_main_text(html: str, max_chars: int = 600) -> str:
    """Extrait le texte principal d'une page HTML.
    
    Args:
        html: Le contenu HTML
        max_chars: Nombre max de caractères à retourner
        
    Returns:
        Le texte extrait
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        
        # Supprimer scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        
        # Chercher le contenu principal
        main = soup.find("main") or soup.find("article") or soup.find("div", class_="content")
        if main:
            text = main.get_text(separator=" ", strip=True)
        else:
            text = soup.get_text(separator=" ", strip=True)
        
        # Nettoyer les espaces multiples
        text = " ".join(text.split())
        
        return text[:max_chars]
    except Exception:
        return ""


@retry_with_backoff(max_attempts=1, base_delay=0.3, max_delay=2.0)
def scrape_standf1() -> str:
    """Scrape StandF1 - classements et statistiques."""
    html = fetch_url(F1_SOURCES["standf1"], timeout=2)
    if not html:
        raise httpx.TimeoutException("StandF1 inaccessible")
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")[:1]
        if tables:
            rows = tables[0].find_all("tr")[:10]
            data = " | ".join([
                " ".join([td.get_text().strip() for td in tr.find_all(["td", "th"])])
                for tr in rows
            ])
            return data[:600] if data else extract_main_text(html, 600)
        return extract_main_text(html, 600)
    except Exception:
        return ""


@retry_with_backoff(max_attempts=2, base_delay=0.5, max_delay=2.0)
def scrape_lequipe() -> str:
    """Scrape L'Équipe F1 - actualités."""
    html = fetch_url(F1_SOURCES["lequipe"], timeout=3)
    if not html:
        raise httpx.TimeoutException("L'Équipe inaccessible")
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.find_all("article")[:5]
        if articles:
            contents = []
            for article in articles:
                title = article.find(["h1", "h2", "h3"])
                if title:
                    contents.append(title.get_text().strip()[:100])
            return " | ".join(contents)[:600] if contents else extract_main_text(html, 600)
        return extract_main_text(html, 600)
    except Exception:
        return ""


@retry_with_backoff(max_attempts=1, base_delay=0.3, max_delay=2.0)
def scrape_toutf1() -> str:
    """Scrape Tout-F1 - actualités et infos F1."""
    html = fetch_url(F1_SOURCES["toutf1"], timeout=2)
    if not html:
        raise httpx.TimeoutException("Tout-F1 inaccessible")
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.find_all("article")[:5]
        if articles:
            contents = []
            for article in articles:
                title = article.find(["h1", "h2", "h3"])
                if title:
                    contents.append(title.get_text().strip()[:100])
            return " | ".join(contents)[:600] if contents else extract_main_text(html, 600)
        links = soup.find_all("a", href=lambda x: x and "/actualite" in x)[:5]
        if links:
            return " | ".join([link.get_text().strip()[:80] for link in links])[:600]
        return extract_main_text(html, 600)
    except Exception:
        return ""


def scrape_fia_calendar() -> str:
    """Scrape FIA - Calendrier 2025."""
    try:
        html = fetch_url(F1_SOURCES["fia_calendar"], timeout=3)
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        events = soup.find_all("div", class_=lambda x: x and "event" in x.lower())[:5]
        if events:
            contents = []
            for event in events:
                text = event.get_text().strip()
                if text:
                    contents.append(text[:100])
            return " | ".join(contents)[:600] if contents else extract_main_text(html, 600)
        return extract_main_text(html, 600)
    except Exception:
        return ""


def scrape_fia_regulations() -> str:
    """Scrape FIA - Régulations F1."""
    try:
        html = fetch_url(F1_SOURCES["fia_regulations"], timeout=3)
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        regs = soup.find_all("a", class_=lambda x: x and "regulation" in x.lower())[:5]
        if regs:
            return " | ".join([reg.get_text().strip()[:80] for reg in regs])[:600]
        return extract_main_text(html, 600)
    except Exception:
        return ""


def get_news_summaries(limit: int = 3) -> List[NewsItem]:
    """Récupère les actualités F1 depuis plusieurs sources.
    
    Args:
        limit: Nombre max de sources à récupérer
        
    Returns:
        Liste de NewsItem
    """
    # Vérifier le cache
    cached = _cache.get("news:summaries")
    if cached:
        logger.info("News depuis cache")
        return cached[:limit]
    
    summaries: List[NewsItem] = []
    
    sources = [
        ("StandF1", scrape_standf1, F1_SOURCES["standf1"]),
        ("L'Équipe F1", scrape_lequipe, F1_SOURCES["lequipe"]),
        ("Tout-F1", scrape_toutf1, F1_SOURCES["toutf1"]),
        ("FIA Calendar", scrape_fia_calendar, F1_SOURCES["fia_calendar"]),
        ("FIA Regulations", scrape_fia_regulations, F1_SOURCES["fia_regulations"]),
    ]
    
    from concurrent.futures import ThreadPoolExecutor, as_completed
    
    def fetch_source(name, scraper, url):
        try:
            logger.info(f"Fetching {name}")
            content = scraper()
            if content and len(content) >= 50:
                return NewsItem(source=name, content=content[:1500], url=url)
        except Exception as e:
            logger.warning(f"Error fetching {name}: {e}")
        return None
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_source, name, scraper, url): name
            for name, scraper, url in sources
        }
        
        for future in as_completed(futures, timeout=5):
            try:
                result = future.result()
                if result:
                    summaries.append(result)
            except Exception:
                pass
    
    # Fallback si rien
    if not summaries:
        summaries.append(NewsItem(
            source="fallback",
            content="Aucune actualité récupérée (sources inaccessibles)." + " " * 40
        ))
    
    # Mettre en cache
    _cache.set("news:summaries", summaries, 600)
    
    return summaries[:limit]
