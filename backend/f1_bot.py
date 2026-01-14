from __future__ import annotations
import asyncio
import os
import sys
import textwrap
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from pydantic import BaseModel, Field
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import Knowledge Base
from backend.knowledge_base import get_knowledge_base
from backend.optimized_cache import get_cache, CACHE_TTL
from backend.intent_router import get_router
from backend.fast_handlers import FAST_HANDLERS
from backend.standings_utils import get_standf1_standings_summary, get_standf1_constructors_summary

# Import Optimized Prompt Builder
from backend.optimized_prompts import OptimizedPromptBuilder

# Import Long Term Memory
from backend.long_term_memory import long_term_memory, CentralizedMemory

# Import Logger structuré
from backend.logger import get_logger
logger = get_logger(__name__)

# Import CSV parser
import csv


# Configuration Ollama (multiplateforme)
OLLAMA_PATHS = [
    # Windows
    Path(os.path.expanduser("~")) / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
    Path("C:/Program Files/Ollama/ollama.exe"),
    # macOS
    Path("/usr/local/bin/ollama"),
    Path(os.path.expanduser("~")) / ".ollama" / "ollama",
    # Linux
    Path("/usr/bin/ollama"),
    Path("/usr/local/bin/ollama"),
    # Fallback (cherche dans PATH)
    "ollama",
]
OLLAMA_MODEL = "qwen2.5:3b"  # Qwen 2.5 3B - Rapide et performant (change si 7b est chargé)
OLLAMA_TIMEOUT = 12  # Augmenté 8s→12s pour réponses plus cohérentes
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")

# Mode RAG strict : pas de scraping web général
# Mettre à True pour forcer le RAG (KB + sources structurées) et éviter le scraping
RAG_ONLY = False

# Suivi limité de liens internes lors du scraping (actualités)
ENABLE_LINK_FOLLOW = True

# Mode libre: aucune restriction hors F1. (F1_ONLY retiré)

# Cache centralisé via OptimizedCache (voir backend/optimized_cache.py)
_cache = get_cache()


def resolve_ollama_path() -> str:
    """Retourne un chemin valide vers ollama (multiplateforme)."""
    for p in OLLAMA_PATHS:
        if p == "ollama":
            cmd = ["which", "ollama"] if sys.platform != "win32" else ["where", "ollama"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return "ollama"
            continue
        if isinstance(p, Path) and p.exists():
            return str(p)
    return "ollama"


OLLAMA_PATH = resolve_ollama_path()



# Modèles Pydantic (validation des données)

class NewsItem(BaseModel):
    source: str
    content: str = Field(min_length=50, max_length=1500)



# Circuits F1 (CSV)

def load_circuits_from_csv() -> List[Dict]:
    """Charge les circuits depuis circuits_kb.csv"""
    circuits = []
    csv_path = Path(__file__).parent.parent / "knowledge_base" / "circuits_kb.csv"
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, fieldnames=['Nom du circuit', 'Lien du circuit', 'Lieu', 'Courses', "Années d'activité", 'Nombre de Grands Prix'])
            next(reader)  # Skip header
            for row in reader:
                if row and row.get('Nom du circuit'):
                    circuits.append({
                        'nom': row['Nom du circuit'].strip().strip('"'),
                        'lieu': row['Lieu'].strip().strip('"') if row.get('Lieu') else '',
                        'courses': row['Courses'].strip().strip('"') if row.get('Courses') else '',
                        'lien': row['Lien du circuit'].strip().strip('"') if row.get('Lien du circuit') else '',
                        'années': row["Années d'activité"].strip().strip('"') if row.get("Années d'activité") else '',
                        'nb_gp': row['Nombre de Grands Prix'].strip().strip('"') if row.get('Nombre de Grands Prix') else '',
                    })
    except Exception as e:
        logger.warning(f"Erreur chargement circuits CSV: {e}")
    
    return circuits


def search_circuit(query: str) -> Optional[Dict]:
    """Recherche un circuit par nom ou lieu (matching plus robuste)"""
    circuits = load_circuits_from_csv()
    query_lower = query.lower().strip()

    if not query_lower:
        return None

    # Découper en tokens significatifs (>3 lettres)
    tokens = [t for t in query_lower.replace("?", " ").split() if len(t) > 3]
    
    # Chercher correspondance par token
    for circuit in circuits:
        name = circuit['nom'].lower()
        city = circuit['lieu'].lower()
        if any(t in name or t in city for t in tokens):
            return circuit

    # Dernière chance: substring simple
    for circuit in circuits:
        if query_lower in circuit['nom'].lower() or query_lower in circuit['lieu'].lower():
            return circuit

    return None


def find_longest_circuit() -> Optional[Dict]:
    """Trouve le circuit le plus long (basé sur le nombre de tours/distance)"""
    circuits = load_circuits_from_csv()
    
    # Chercher les plus anciens circuits actifs (Monza, Spa, Silverstone, Monaco)
    # Ces circuits sont généralement les plus longs en F1 moderne
    famous_long_circuits = {
        'spa': 'Circuit de Spa-Francorchamps (7.004 km)',
        'monza': 'Circuit de Monza (5.793 km)',
        'silverstone': 'Circuit de Silverstone (5.891 km)',
        'monaco': 'Circuit de Monaco (3.337 km)',
    }
    
    # Chercher Spa (le plus long)
    for circuit in circuits:
        if 'spa' in circuit['nom'].lower():
            return {
                'nom': circuit['nom'],
                'lieu': circuit['lieu'],
                'longueur': '7.004 km',
                'info': 'Le plus long circuit de F1 moderne'
            }
    
    return None



# News Sources
NEWS_SOURCES = [
    "https://www.motorsport.com/f1/news/",
    "https://www.autosport.com/f1/news/",
    "https://www.actuf1.com/",  # Actualités F1
    "https://www.standf1.com/",  # Classements/Stats
    "https://www.lequipe.fr/Formule-1/",  # L'Équipe F1 (FR)
    "https://aurupteur.com/",  # Aurupteur F1 (FR)
]

# Sources complémentaires (officiel FIA)
FIA_SOURCES = [
    "https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship",  # Calendrier 2025
    "https://www.fia.com/regulation/category/110",  # Régulations
]

# User-Agents rotatifs pour éviter blocage anti-bot
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

import random

def get_random_headers():
    """Retourne des headers avec User-Agent rotatif pour éviter blocage"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

HEADERS = get_random_headers()  # Headers par défaut

# Client HTTP persistant pour réduire la latence (réutilise les connexions)
# ULTRA-OPTIMISÉ: timeout DRASTIQUE pour <2s de réponse totale
http_client = httpx.Client(
    headers=get_random_headers(),  # Headers rotatifs
    follow_redirects=True,
    timeout=httpx.Timeout(2.0, connect=1.0),  # Réduit 3s→2s (rapid fail si lent)
    limits=httpx.Limits(max_connections=30, max_keepalive_connections=15)  # Pool augmenté 20→30
)



# Scraping helpers avec retry logic

def retry_with_backoff(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 10.0):
    """Décorateur retry avec exponential backoff pour fonctions scraping.
    
    Args:
        max_attempts: Nombre max de tentatives (défaut: 3)
        base_delay: Délai initial en secondes (défaut: 1.0)
        max_delay: Délai max entre tentatives (défaut: 10.0)
    
    Gère automatiquement:
    - Timeout réseau
    - Erreurs HTTP temporaires (429, 500, 502, 503, 504)
    - Exponential backoff: 1s → 2s → 4s → ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                    
                except httpx.TimeoutException as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        logger.info(f"⏱️ Timeout {func.__name__} - Retry {attempt}/{max_attempts} dans {delay:.1f}s")
                        time.sleep(delay)
                    
                except httpx.HTTPStatusError as e:
                    last_exception = e
                    # Retry seulement sur erreurs temporaires
                    if e.response and e.response.status_code in [429, 500, 502, 503, 504]:
                        if attempt < max_attempts:
                            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                            logger.info(f"🔄 HTTP {e.response.status_code} {func.__name__} - Retry {attempt}/{max_attempts} dans {delay:.1f}s")
                            time.sleep(delay)
                        else:
                            logger.warning(f"❌ {func.__name__} échoué après {max_attempts} tentatives (HTTP {e.response.status_code})")
                            return ""
                    else:
                        # 404, 403, etc. → pas de retry
                        logger.warning(f"❌ {func.__name__} erreur définitive (HTTP {e.response.status_code})")
                        return ""
                        
                except Exception as e:
                    last_exception = e
                    logger.warning(f"❌ {func.__name__} erreur inattendue: {type(e).__name__}")
                    return ""
            
            # Si toutes les tentatives échouent
            logger.warning(f"❌ {func.__name__} échoué après {max_attempts} tentatives")
            return ""
        
        return wrapper
    return decorator


@retry_with_backoff(max_attempts=1, base_delay=0.5, max_delay=1.0)  # 1 seule tentative (rapide fail)
def fetch_url(url: str, timeout: int = 2) -> str:  # Timeout réduit 6s→2s (fail rapide si lent)
    """Récupère le contenu HTML d'une URL avec headers rotatifs."""
    # Créer un client avec headers frais pour chaque requête (éviter fingerprinting)
    headers = get_random_headers()
    resp = http_client.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def extract_main_text(html: str, max_chars: int = 1500) -> str:
    """Nettoie le HTML, extrait le texte principal, tronque à max_chars.
    
    Optimisations:
    - Supprime les balises inutiles plus agressivement
    - Priorise le contenu <main> et <article>
    - Filtre les textes non-F1 (publicités, etc.)
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Supprimer éléments inutiles
    for tag in soup(["script", "style", "noscript", "header", "footer", "form", "svg", "nav", "aside", "iframe"]):
        tag.decompose()
    
    # Chercher d'abord le contenu principal
    main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=lambda x: x and "content" in x.lower())
    
    if main_content:
        paragraphs = [p.get_text(" ", strip=True) for p in main_content.find_all("p")]
    else:
        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    
    text = " ".join(paragraphs)
    text = " ".join(text.split())  # normaliser espaces
    
    # Sécuriser la plage 600–1500 caractères
    upper = max(600, min(max_chars, 1500))
    return text[:upper]


def _extract_article_links_actuf1(html: str, base_url: str = "https://www.actuf1.com/") -> List[Tuple[str, str]]:
    """Extrait jusqu'à 3 liens d'articles internes depuis ActuF1 (titre + URL absolue)."""
    out: List[Tuple[str, str]] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for art in soup.find_all("article")[:5]:
            a = art.find("a", href=True)
            title = (art.find("h2") or art.find("h3") or a)
            if a and title:
                url = urljoin(base_url, a["href"])
                if url and url.startswith(base_url):
                    t = title.get_text(" ", strip=True)
                    if t and (t, url) not in out:
                        out.append((t, url))
            if len(out) >= 3:
                break
    except Exception:
        pass
    return out


def _extract_article_links_lequipe(html: str) -> List[Tuple[str, str]]:
    """Extrait jusqu'à 3 liens internes F1 depuis L'Équipe."""
    out: List[Tuple[str, str]] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        links = [
            a for a in soup.find_all("a", href=True)
            if a.get("href") and "/Formule-1/" in a["href"]
        ]
        for a in links:
            url = urljoin("https://www.lequipe.fr/", a["href"])
            title = a.get_text(" ", strip=True)
            if url and title and (title, url) not in out:
                out.append((title, url))
            if len(out) >= 3:
                break
    except Exception:
        pass
    return out


def _follow_and_extract(links: List[Tuple[str, str]], cache_prefix: str, max_pages: int = 2, timeout: int = 8) -> List[str]:
    """Suis jusqu'à `max_pages` liens internes, extrait texte principal et retourne des bullets avec citation.
    Met en cache chaque page pour réduire la latence."""
    results: List[str] = []
    for title, url in links[:max_pages]:
        try:
            key = f"follow:{cache_prefix}:{url}"
            cached = _cache.get(key)
            if cached:
                results.append(cached)
                continue
            html = fetch_url(url, timeout=timeout)
            if not html:
                continue
            text = extract_main_text(html, max_chars=600)
            if text and len(text.strip()) >= 50:
                bullet = f"• [{title}]({url}): {text[:300]}"
                results.append(bullet)
                _cache.set(key, bullet, CACHE_TTL.get("news_articles", 600))
        except Exception:
            continue
    return results


@retry_with_backoff(max_attempts=2, base_delay=0.5, max_delay=3.0)  # 2 tentatives pour robustesse
def scrape_actuf1() -> str:
    """Scrape ActuF1 - actualités F1 spécialisées (avec retry)."""
    html = fetch_url("https://www.actuf1.com/", timeout=6)  # Timeout augmenté 2s→6s (anti-bot)
    if not html:
        raise httpx.TimeoutException("ActuF1 inaccessible")
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Chercher les articles principaux
        articles = soup.find_all("article")[:3]  # Top 3 articles
        contents = []
        for article in articles:
            title = article.find("h2") or article.find("h3")
            summary = article.find("p")
            if title and summary:
                contents.append(f"{title.get_text().strip()}: {summary.get_text().strip()}")
        base = " | ".join(contents) if contents else extract_main_text(html, 600)
        # Suivi de liens internes (limité)
        if ENABLE_LINK_FOLLOW:
            links = _extract_article_links_actuf1(html)
            followed = _follow_and_extract(links, cache_prefix="actuf1", max_pages=2)
            if followed:
                base = (base + " | " + " | ".join(followed))[:900]
        return base
    except (httpx.HTTPError, AttributeError) as e:
        logger.warning(f"ActuF1 scraping failed: {type(e).__name__}: {str(e)[:100]}")
        return ""
    except Exception as e:
        logger.error(f"ActuF1 unexpected error: {type(e).__name__}: {str(e)[:100]}")
        return ""


@retry_with_backoff(max_attempts=2, base_delay=0.5, max_delay=3.0)  # 2 tentatives pour robustesse
def scrape_lequipe() -> str:
    """Scrape L'Équipe (section Formule 1) — titres + résumés (avec retry).

    Stratégie robuste:
    - Cherche <article> avec titres (h2/h3) et paragraphes
    - Fallback: extraction de texte principal si structure inattendue
    """
    html = fetch_url("https://www.lequipe.fr/Formule-1/", timeout=6)  # Timeout augmenté 2s→6s (anti-bot)
    if not html:
        raise httpx.TimeoutException("L'Équipe inaccessible")
    
    try:
        soup = BeautifulSoup(html, "html.parser")

        contents = []
        # Essai 1: blocs <article>
        for article in soup.find_all("article")[:3]:
            title = article.find(["h2", "h3"]) or article.find("a")
            summary = article.find("p") or article.find("span")
            if title:
                t = title.get_text(" ", strip=True)
                s = summary.get_text(" ", strip=True) if summary else ""
                if t:
                    contents.append(f"{t}: {s}".strip())

        # Essai 2: liens vers articles F1 si peu d'<article>
        if not contents:
            links = [
                a for a in soup.find_all("a", href=True)
                if "/Formule-1/" in a["href"] and a.get_text(strip=True)
            ][:5]
            for a in links[:3]:
                contents.append(a.get_text(strip=True))

        base = None
        if contents:
            joined = " | ".join([c[:160] for c in contents if c])
            base = joined[:600]

        # Fallback: texte principal
        base = base or extract_main_text(html, 600)
        # Suivi de liens internes (limité)
        if ENABLE_LINK_FOLLOW:
            links = _extract_article_links_lequipe(html)
            followed = _follow_and_extract(links, cache_prefix="lequipe", max_pages=2)
            if followed:
                base = (base + " | " + " | ".join(followed))[:900]
        return base
    except (httpx.HTTPError, AttributeError) as e:
        logger.warning(f"L'Équipe scraping failed: {type(e).__name__}: {str(e)[:100]}")
        return ""
    except Exception as e:
        logger.error(f"L'Équipe unexpected error: {type(e).__name__}: {str(e)[:100]}")
        return ""


@retry_with_backoff(max_attempts=2, base_delay=0.5, max_delay=3.0)  # 2 tentatives pour robustesse
def scrape_standf1() -> str:
    """Scrape StandF1 - classements et statistiques (avec retry)."""
    html = fetch_url("https://www.standf1.com/", timeout=6)  # Timeout augmenté 2s→6s (anti-bot)
    if not html:
        raise httpx.TimeoutException("StandF1 inaccessible")
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Extraire les tableaux de classements
        tables = soup.find_all("table")[:1]
        if tables:
            rows = tables[0].find_all("tr")[:10]  # Top 10 lignes
            data = " | ".join([" ".join([td.get_text().strip() for td in tr.find_all(["td", "th"])]) for tr in rows])
            return data[:600] if data else extract_main_text(html, 600)
        return extract_main_text(html, 600)
    except (httpx.HTTPError, AttributeError) as e:
        logger.warning(f"StandF1 scraping failed: {type(e).__name__}: {str(e)[:100]}")
        return ""
    except Exception as e:
        logger.error(f"StandF1 unexpected error: {type(e).__name__}: {str(e)[:100]}")
        return ""


@retry_with_backoff(max_attempts=2, base_delay=0.5, max_delay=3.0)  # 2 tentatives pour robustesse
def scrape_aurupteur() -> str:
    """Scrape Aurupteur - actualités F1 françaises (avec retry)."""
    html = fetch_url("https://aurupteur.com/", timeout=6)  # Timeout augmenté 2s→6s (anti-bot)
    if not html:
        raise httpx.TimeoutException("Aurupteur inaccessible")
    
    try:
        soup = BeautifulSoup(html, "html.parser")
        # Chercher les articles principaux
        articles = soup.find_all("article")[:3]  # Top 3 articles
        if not articles:
            # Fallback: chercher les titres h2/h3
            articles = soup.find_all(["h2", "h3"])[:3]
        
        contents = []
        for article in articles:
            title = article.find(["h2", "h3", "h1"])
            summary = article.find("p")
            if title:
                t = title.get_text().strip()
                s = summary.get_text().strip() if summary else ""
                if t:
                    contents.append(f"{t}: {s}" if s else t)
        
        return " | ".join(contents)[:600] if contents else extract_main_text(html, 600)
    except (httpx.HTTPError, AttributeError) as e:
        logger.warning(f"Aurupteur scraping failed: {type(e).__name__}: {str(e)[:100]}")
        return ""
    except Exception as e:
        logger.error(f"Aurupteur unexpected error: {type(e).__name__}: {str(e)[:100]}")
        return ""


# get_standf1_standings_summary déplacé vers backend/standings_utils.py


def scrape_fia_calendar() -> str:
    """Scrape FIA - Calendrier 2025."""
    try:
        html = fetch_url("https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship", timeout=3)  # Réduit 10s→3s
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        # Chercher les événements
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
        html = fetch_url("https://www.fia.com/regulation/category/110", timeout=3)  # Réduit 10s→3s
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        # Extraire les régulations
        regs = soup.find_all("a", class_=lambda x: x and "regulation" in x.lower())[:5]
        if regs:
            return " | ".join([reg.get_text().strip()[:80] for reg in regs])[:600]
        return extract_main_text(html, 600)
    except Exception:
        return ""


def get_news_summaries(limit: int = 1) -> List[NewsItem]:
    """Récupère et valide jusqu'à `limit` sources récentes (mix de sources avec liens).
    
    Optimisations:
    - Cache 10 min pour éviter appels répétés
    - Parallélisation ThreadPool pour récupération simultanée
    - Timeout intelligents (court pour news, long pour FIA)
    """
    # Vérifier le cache centralisé
    cached = _cache.get("news:summaries")
    if cached:
        logger.info(f"News depuis cache OptimizedCache")
        return cached[:limit]
    
    summaries: List[NewsItem] = []
    
    # Mix de scrapers avec timeouts augmentés pour robustesse - TOUS les sites activés
    sources = [
        ("ActuF1", scrape_actuf1, "https://www.actuf1.com/", 6),  # Timeout augmenté 2s→6s (anti-bot)
        ("StandF1", scrape_standf1, "https://www.standf1.com/", 6),  # Timeout augmenté 2s→6s
        ("L'Équipe F1", scrape_lequipe, "https://www.lequipe.fr/Formule-1/", 6),  # Timeout augmenté 2s→6s
        ("Aurupteur", scrape_aurupteur, "https://aurupteur.com/", 6),  # Timeout augmenté 2s→6s
        ("FIA Calendar", scrape_fia_calendar, "https://www.fia.com/events/fia-formula-one-world-championship/season-2025/", 8),  # Calendrier officiel (site lent)
        ("FIA Regulations", scrape_fia_regulations, "https://www.fia.com/regulation/category/110", 8),  # Règlements officiels (site lent)
    ]

    # Paralléliser les appels avec ThreadPoolExecutor
    def fetch_source(source_name, scraper, source_url, timeout):
        try:
            logger.info(f"Fetching {source_name}")
            if scraper == extract_main_text and source_url:
                html = fetch_url(source_url, timeout=timeout)
                text = extract_main_text(html, max_chars=400)  # Réduit 600→400
            else:
                text = scraper()

            if text and len(text.strip()) >= 50:
                source_with_link = f"{source_name}" + (f" - [Lien]({source_url})" if source_url else "")
                return NewsItem(source=source_with_link, content=text)
        except Exception as e:
            logger.warning(f"{source_name} failed: {e}")
        return None

    # Exécuter en parallèle avec max 6 workers pour crawler tous les sites
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(fetch_source, name, scraper, url, timeout): name
            for name, scraper, url, timeout in sources
        }
        
        for future in as_completed(futures):
            if len(summaries) >= limit:  # Réduit limit*2→limit (pas besoin 2x)
                break
            result = future.result()
            if result:
                summaries.append(result)
    
    # Fallback si rien trouvé
    if not summaries:
        summaries.append(NewsItem(source="fallback", content="Aucune actualité récupérée (sources inaccessibles)."))
    
    # Mettre en cache centralisé
    _cache.set("news:summaries", summaries, CACHE_TTL["news_articles"])
    
    return summaries[:limit]


def web_search_general(query: str, limit: int = 3) -> List[NewsItem]:
    """Recherche générale sur internet avec les mots-clés de la question.
    
    IMPORTANT: Cette fonction est un FALLBACK de dernier recours.
    Elle est appelée uniquement si:
    - La Knowledge Base ne répond pas
    - La mémoire long terme ne répond pas
    - Le LLM donne une réponse incertaine/vide
    
    Stratégie:
    1. Tenter Google/Bing/DuckDuckGo (souvent bloqué par anti-bot)
    2. Fallback: retourner message explicite si aucun résultat
    
    Note: Les moteurs de recherche bloquent massivement le scraping.
    Privilégier TOUJOURS la Knowledge Base et les sources F1 spécialisées.
    """
    # Clé de cache basée sur la requête
    cache_key = f"web:search:{query.lower()[:50]}"
    
    # Vérifier cache centralisé
    cached = _cache.get(cache_key)
    if cached:
        logger.info(f"Résultats web depuis cache OptimizedCache pour: {query[:30]}")
        return cached[:limit]
    
    results: List[NewsItem] = []
    
    # Note: Les moteurs de recherche principaux (Google/Bing/DDG) bloquent le scraping
    # On garde le code pour compatibilité mais avec expectation de blocage
    
    logger.warning(f"⚠️ Web Search lancé en dernier recours pour: {query[:50]}")
    logger.info(f"💡 Conseil: Enrichir la Knowledge Base pour éviter le web scraping")
    
    # Essayer les moteurs (souvent bloqué)
    search_urls = [
        f"https://www.google.com/search?q={query.replace(' ', '+')}&num=10",
        f"https://duckduckgo.com/?q={query.replace(' ', '+')}&t=h&ia=web",
        f"https://www.bing.com/search?q={query.replace(' ', '+')}&count=10",
    ]
    
    def scrape_search_result(search_url, engine_name):
        try:
            html = fetch_url(search_url, timeout=6)
            if not html or len(html) < 100:
                logger.warning(f"❌ {engine_name}: HTML vide ou bloqué")
                return []
            
            soup = BeautifulSoup(html, "html.parser")
            items = []
            
            if "google" in engine_name.lower():
                # Google: plusieurs sélecteurs possibles (structure change souvent)
                for div in soup.find_all("div", class_=lambda x: x and ("g" in x.split() or "Gx5Zad" in x))[:5]:
                    h3 = div.find("h3") or div.find("div", {"role": "heading"})
                    link = div.find("a", href=True)
                    # Snippet peut être dans plusieurs balises
                    snippet = (div.find("span", class_="st") or 
                              div.find("div", class_="VwiC3b") or 
                              div.find("div", attrs={"data-snf": "nke7rc"}))
                    
                    if h3 and link:
                        title = h3.get_text().strip()
                        url = link["href"] if link else ""
                        text = snippet.get_text().strip() if snippet else title
                        
                        # Vérifier que l'URL est valide (pas un lien Google interne)
                        if url and not url.startswith("/search") and len(text) > 30:
                            items.append((title, text[:300], url))
                
                # Fallback: chercher tous les liens avec texte
                if not items:
                    for link in soup.find_all("a", href=True)[:10]:
                        if link["href"].startswith("http") and not "google.com" in link["href"]:
                            title = link.get_text().strip()
                            if len(title) > 20:
                                items.append((title, title[:300], link["href"]))
                                if len(items) >= 5:
                                    break
            
            elif "duckduckgo" in engine_name.lower():
                # DuckDuckGo: plusieurs structures possibles
                for article in soup.find_all("article", attrs={"data-testid": "result"})[:5]:
                    title_tag = article.find("h2") or article.find("a")
                    snippet = article.find("span", attrs={"data-result": "snippet"})
                    link = article.find("a", href=True)
                    
                    if title_tag:
                        title = title_tag.get_text().strip()
                        text = snippet.get_text().strip() if snippet else title
                        url = link["href"] if link else ""
                        if len(text) > 30:
                            items.append((title, text[:300], url))
                
                # Fallback: anciennes classes
                if not items:
                    for div in soup.find_all("div", class_=lambda x: x and "result" in x.lower())[:5]:
                        title_tag = div.find("a")
                        if title_tag:
                            title = title_tag.get_text().strip()
                            if len(title) > 20:
                                items.append((title, title[:300], ""))
            
            elif "bing" in engine_name.lower():
                # Bing: li.b_algo
                for li in soup.find_all("li", class_="b_algo")[:5]:
                    h2 = li.find("h2") or li.find("h3")
                    p = li.find("p") or li.find("div", class_="b_caption")
                    link = li.find("a", href=True)
                    
                    if h2:
                        title = h2.get_text().strip()
                        text = p.get_text().strip() if p else title
                        url = link["href"] if link else ""
                        if len(text) > 30:
                            items.append((title, text[:300], url))
            
            if items:
                logger.info(f"✅ {engine_name}: {len(items)} résultats trouvés")
            else:
                logger.warning(f"⚠️ {engine_name}: Aucun résultat (structure HTML changée?)")
            
            return items
        except httpx.TimeoutException:
            logger.warning(f"⏱️ {engine_name}: Timeout (bloqué ou lent)")
            return []
        except Exception as e:
            logger.warning(f"❌ {engine_name} erreur: {type(e).__name__} - {str(e)[:100]}")
            return []
    
    # Paralléliser les recherches
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(scrape_search_result, url, f"Engine{i}"): i
            for i, url in enumerate(search_urls)
        }
        
        for future in as_completed(futures):
            items = future.result()
            for title, text, url in items:
                if len(results) >= limit * 2:
                    break
                source_text = f"{title}" + (f" - {url}" if url else "")
                try:
                    results.append(NewsItem(source=source_text[:100], content=text))
                except:
                    pass
    
    # Fallback si aucun résultat
    if not results:
        logger.warning(f"❌ Web Search échoué: moteurs bloquent le scraping (anti-bot)")
        results.append(NewsItem(
            source="Web Search indisponible", 
            content="Les moteurs de recherche bloquent le scraping. Réponse basée sur la Knowledge Base et sources F1 spécialisées uniquement."
        ))
    
    # Mettre en cache centralisé
    _cache.set(cache_key, results, CACHE_TTL["web_search"])
    
    return results[:limit]




# Construction du prompt final avec monitoring overflow
def estimate_tokens(text: str) -> int:
    """Estimation rapide tokens : ~1 token = 4 chars pour LLaMA 3.2"""
    return len(text) // 4


def smart_clamp(text: str, max_len: int) -> str:
    """Coupe intelligemment à la dernière phrase complète avant max_len"""
    if len(text) <= max_len:
        return text
    
    # Chercher dernière phrase complète (. ou \n)
    truncated = text[:max_len]
    last_period = truncated.rfind('. ')
    last_newline = truncated.rfind('\n\n')
    
    cut_point = max(last_period, last_newline)
    
    # Si on garde au moins 70% du texte, couper proprement
    if cut_point > max_len * 0.7:
        return text[:cut_point + 1]
    
    # Sinon fallback coupe brutale
    return text[:max_len] + "..."


def _clamp(text: str, max_len: int) -> str:
    """Alias pour compatibilité - utilise smart_clamp"""
    return smart_clamp(text, max_len)


def build_prompt(news_summary: str, user_question: str, history_text: str = "") -> str:
    """Construction prompt avec monitoring overflow et stratégie réduction intelligente
    
    DÉPRÉCIÉ: Utiliser OptimizedPromptBuilder.build_f1_question() à la place.
    Conservé pour compatibilité legacy.

    Qwen 2.5 3B context: 8192 tokens max
    Target: <3000 tokens (ultra-rapide) pour vitesse maximale
    """
    # Limites par défaut - DRASTIQUEMENT RÉDUITES pour vitesse
    MAX_TOKENS = 3000  # Réduit de 6000→3000 pour inférence 2x plus rapide
    WARNING_THRESHOLD = 2500  # Réduit de 5000→2500
    
    # Utiliser le prompt système centralisé depuis optimized_prompts.py
    from backend.optimized_prompts import OptimizedPromptBuilder
    system_template = OptimizedPromptBuilder.SYSTEM_PROMPT
    
    # Estimation initiale (concaténer pour compter)
    combined_text = news_summary + user_question + history_text + system_template
    total_tokens = estimate_tokens(combined_text)
    
    # Stratégie réduction si nécessaire
    if total_tokens > MAX_TOKENS:
        logger.warning(f"⚠️ Prompt overflow: {total_tokens} tokens (max {MAX_TOKENS})")
        logger.info(f"🔧 Application stratégie réduction...")
        
        # Priorité: Question > Système > History > KB > News
        news_summary = smart_clamp(news_summary, 400)   # Réduit 600 → 400 pour ultra-vitesse
        history_text = smart_clamp(history_text, 300)   # Réduit 500 → 300 pour ultra-vitesse
        
        # Recalcul
        combined_text = news_summary + user_question + history_text + system_template
        total_tokens = estimate_tokens(combined_text)
        logger.info(f"✅ Prompt réduit: {total_tokens} tokens")
    
    elif total_tokens > WARNING_THRESHOLD:
        logger.info(f"⚠️ Prompt large: {total_tokens} tokens (seuil warning {WARNING_THRESHOLD})")
    
    # Borner les blocs (limites normales si pas overflow) - RÉDUITES pour vitesse
    news_summary = smart_clamp(news_summary, 600)  # Réduit de 1200→600
    history_text = smart_clamp(history_text, 400)  # Réduit de 600→400
    
    prompt = f"""{system_template}

CONTEXTE CONVERSATION (si utile) :
{history_text if history_text else "(aucun contexte)"}

SOURCES :
{news_summary if news_summary else "(aucune actualité)"}

QUESTION : {user_question}

Réponds maintenant (direct et concis):
"""
    prompt = textwrap.dedent(prompt).strip()
    
    # Sécurité finale
    final_tokens = estimate_tokens(prompt)
    if final_tokens > MAX_TOKENS:
        logger.error(f"❌ Prompt toujours trop long ({final_tokens} tokens), troncature d'urgence")
        prompt = smart_clamp(prompt, MAX_TOKENS * 4)  # *4 car 1 token ≈ 4 chars
    
    return prompt


# Appel Ollama
def call_ollama(prompt: str, min_response_length: int = 15) -> str:
    """Appel HTTP à Ollama (daemon) avec paramètres ULTRA-RAPIDES. 
    
    Args:
        prompt: Le prompt à envoyer
        min_response_length: Longueur minimale attendue de la réponse (défaut: 15 chars)
        
    Returns:
        str: Réponse de l'LLM ou message d'erreur
        
    Fallback subprocess si l'API échoue.
    Valide que la réponse n'est pas trop courte ou vide.
    """
    # Payload avec paramètres optimisés pour vitesse <3s
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.05,      # ULTRA-MINIMAL pour réponses déterministes
            "top_p": 0.75,            # Focus strict
            "num_ctx": 256,           # Context minimal
            "num_predict": 100,       # 100 tokens = 3-4 phrases courtes
            "top_k": 3,               # 3 choix max
            "repeat_penalty": 1.0,    # Désactiver
        }
    }
    try:
        r = httpx.post(OLLAMA_URL, json=payload, timeout=OLLAMA_TIMEOUT, follow_redirects=True)
        r.raise_for_status()
        response = (r.json().get("response") or "").strip()
        
        # Validation: réponse non vide et longueur minimale
        if not response:
            logger.warning("Ollama returned empty response - trying fallback")
            raise Exception("Empty response from Ollama")
        if len(response) < min_response_length:
            logger.warning(f"Ollama response too short ({len(response)} chars) - trying fallback")
            raise Exception(f"Response too short ({len(response)} chars)")
        
        return response
    except httpx.TimeoutException:
        logger.warning(f"Ollama HTTP timeout ({OLLAMA_TIMEOUT}s) - trying subprocess fallback")
        # Fallback subprocess
        try:
            cmd = [OLLAMA_PATH, "run", OLLAMA_MODEL, prompt]
            logger.debug(f"{' '.join(cmd)}")
            start_time = time.time()
            kwargs = {
                "capture_output": True,
                "text": True,
                "encoding": "utf-8",
                "errors": "replace",
                "timeout": OLLAMA_TIMEOUT,
                "shell": False,
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.run(cmd, **kwargs)
            if proc.returncode == 0:
                response = proc.stdout.strip()
                # Validation aussi pour subprocess
                if not response or len(response) < min_response_length:
                    logger.warning(f"Subprocess response too short ({len(response)} chars)")
                    return "[ERREUR] Réponse incomplète de l'IA"
                return response
            logger.error(f"Ollama subprocess failed with code {proc.returncode}: {proc.stderr.strip()[:100]}")
            return f"[ERREUR OLLAMA] {proc.stderr.strip() or 'retcode != 0'}"
        except subprocess.TimeoutExpired:
            logger.error("Ollama subprocess timeout - forcer réponse partielle")
            # Plutôt que de bloquer, retourner une réponse vague mais rapide
            return "Je prépare ma réponse... 🤔 Réessaie dans 2-3 secondes!"
        except FileNotFoundError:
            logger.error(f"Ollama not found at {OLLAMA_PATH}")
            return f"[ERREUR] Ollama introuvable à {OLLAMA_PATH}"
        except Exception as exc:
            logger.error(f"Ollama subprocess error: {type(exc).__name__}: {str(exc)[:100]}")
            return f"J'ai besoin d'une seconde... Pose-moi ta question à nouveau! 😊"


# Pipeline principal : à appeler depuis /chat

# REMOVED: _is_probably_english() and _translate_to_french() - dead code never used
# These functions were defined but never called. Removed to reduce maintenance burden.

def _is_f1_question(q: str) -> bool:
    """Détecte si la question concerne la F1 de manière stricte."""
    ql = q.lower()
    f1_keywords = [
        "f1", "formula 1", "formule 1", "grand prix", "gp",
        # Pilotes modernes
        "verstappen", "hamilton", "leclerc", "alonso", "perez", "sainz", "norris", "piastri",
        "russell", "ocon", "gasly", "tsunoda", "bottas", "zhou", "stroll", "hulkenberg", "magnussen",
        # Pilotes historiques fréquents
        "schumacher", "michael schumacher", "senna", "ayrton senna", "prost", "alain prost", "lauda", "niki lauda",
        "vettel", "raikkonen", "massa", "rosberg", "nico rosberg", "mansell", "piquet", "berger", "hill",
        "jackie stewart", "jim clark", "fangio", "hunt", "villeneuve", "gilles villeneuve", "button",
        "mercedes", "ferrari", "red bull", "mclaren", "aston martin", "alpine", "williams", "haas", "sauber",
        "circuit", "piste", "champion", "victoire", "course", "pilote", "constructeur",
        "pole position", "podium", "drs", "kers", "qualif", "essai", "essais libres",
        "monza", "spa", "monaco", "silverstone", "imola", "suzuka", "interlagos",
        "gagn", "gagne", "gangé", "perdu", "perd", "classement", "position", "résultat",
        "victoire", "victoires", "points", "total", "somme", "addition"
    ]
    return any(k in ql for k in f1_keywords)


def _is_general_question(q: str) -> bool:
    """Détecte si la question est une question générale (non-F1)."""
    ql = q.lower()
    general_indicators = [
        "qui est", "c'est quoi", "qu'est-ce que", "comment",
        "pourquoi", "où", "quand", "définition", "expliquer",
        "que signifie", "quel est", "quelle est", "calcule",
        "combien font", "bonjour", "salut", "ça va", "tu vas bien",
        "ton nom", "qui es-tu", "raconte une blague", "aide-moi"
    ]
    # Question générale si présence d'indicateurs généraux ET que ce n'est pas clairement F1
    if any(ind in ql for ind in general_indicators):
        return not _is_f1_question(q)
    # Ne pas classer automatiquement comme général si la requête est courte mais F1 (ex: "prost", "senna")
    if len(ql.split()) < 4:
        return not _is_f1_question(q)
    return False


def _is_circuit_question(question: str) -> bool:
    """Détecte si la question est spécifiquement sur les circuits"""
    keywords = ['circuit', 'long', 'distance', 'piste', 'tracé', 'km', 'longueur']
    return any(k in question.lower() for k in keywords)


def _is_kb_result_relevant(query: str, result: str, min_keyword_match: int = 1) -> bool:
    """Vérifier si le résultat KB est vraiment pertinent pour la requête.
    
    Évite les faux positifs comme "Qui est Colin ?" qui retourne la FAQ F1.
    Utilise word boundaries pour des matches exacts (pas des sous-chaînes).
    """
    import re
    query_lower = query.lower()
    # Filtrer les mots très courts (de, qu, etc) et garder seulement les noms/mots significatifs
    query_words = [word for word in query_lower.split() if len(word) > 3]
    
    if not query_words:  # Si aucun mot > 3 caractères, trop vague
        return False
    
    result_lower = result.lower()
    
    # Compter les matches exacts avec word boundaries
    matches = 0
    for word in query_words:
        # Chercher le mot comme mot complet (pas sous-chaîne)
        if re.search(r'\b' + re.escape(word) + r'\b', result_lower):
            matches += 1
    
    # Au minimum 1 mot-clé doit matcher comme mot complet
    return matches >= min_keyword_match


def _format_history(history) -> str:
    """Formate les derniers tours de conversation pour donner du contexte.
    Accepte une liste de dict ou d'objets avec attributes role/content.
    """
    if not history:
        return ""
    lines = []
    try:
        for item in list(history)[-6:]:  # derniers tours
            role = getattr(item, "role", None) or (item.get("role") if isinstance(item, dict) else "")
            content = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else "")
            if role and content:
                lines.append(f"{role}: {content}")
    except Exception:
        return ""
    return "\n".join(lines)


def _history_mentions_f1_entities(history_text: str) -> bool:
    """Détecte des entités F1 (pilotes/équipes/circuits) dans l'historique."""
    if not history_text:
        return False
    tl = history_text.lower()
    tokens = [
        # Pilotes (échantillon)
        "verstappen", "hamilton", "leclerc", "alonso", "perez", "sainz", "norris", "piastri",
        "russell", "ocon", "gasly", "tsunoda", "bottas", "zhou", "stroll", "hulkenberg", "magnussen",
        "schumacher", "senna", "prost", "vettel", "raikkonen",
        # Équipes
        "ferrari", "mercedes", "red bull", "mclaren", "aston martin", "alpine", "williams", "haas", "sauber",
        # Circuits
        "monza", "spa", "monaco", "silverstone", "suzuka", "interlagos"
    ]
    return any(t in tl for t in tokens)


def _is_followup_reference(question: str) -> bool:
    """Détecte une relance référentielle (pronoms, 'plus', 'détails')."""
    ql = question.lower()
    pronouns = ["il", "elle", "lui", "son", "sa", "ses", "ce pilote", "ce circuit", "cette équipe", "cette ecurie", "écurie"]
    followups = ["plus", "encore", "détails", "detail", "approfondis", "continue", "développe", "developpe", "plus d'infos", "plus sur", "plus sur lui"]
    return any(p in ql for p in pronouns) or any(f in ql for f in followups)


def _was_recently_on_f1(history_text: str) -> bool:
    """Détecte si l'historique récent concerne la F1 pour persister le sujet.
    Cherche des mots-clés F1 dans le contexte entremêlé (utilisateur/assistant)."""
    if not history_text:
        return False
    tl = history_text.lower()
    f1_tokens = [
        "f1", "formule 1", "grand prix", "gp", "pilote", "constructeur",
        "verstappen", "hamilton", "leclerc", "alonso", "perez", "sainz", "norris",
        "classement", "points", "podium", "pole", "drs", "monza", "spa", "monaco", "silverstone"
    ]
    return any(t in tl for t in f1_tokens)

def perform_background_learning(user_message: str, assistant_response: str):
    """Extrait des connaissances de l'échange via le LLM en arrière-plan."""
    try:
        from backend.optimized_prompts import OptimizedPromptBuilder
        from backend.long_term_memory import long_term_memory
        import json

        prompt = OptimizedPromptBuilder.build_fact_extraction_prompt(user_message, assistant_response)
        raw_response = call_ollama(prompt)

        if not raw_response or "RIEN" in raw_response.upper():
            return

        # Tentative de parser le JSON
        try:
            # Nettoyer la réponse si le LLM a ajouté du texte avant/après
            start = raw_response.find("{")
            end = raw_response.rfind("}") + 1
            if start != -1 and end != 0:
                json_str = raw_response[start:end]
                data = json.loads(json_str)
                
                if "facts" in data and isinstance(data["facts"], list):
                    for fact in data["facts"]:
                        long_term_memory.add_learned_fact_from_llm(fact)
                
                if "preferences" in data and isinstance(data["preferences"], dict):
                    long_term_memory.update_preferences_from_llm(data["preferences"])
                    
                logger.info(f"Apprentissage réussi : {len(data.get('facts', []))} faits, {len(data.get('preferences', {}))} prefs")
        except Exception as e:
            # Si pas JSON, peut-être juste du texte
            if len(raw_response) > 10 and len(raw_response) < 200:
                long_term_memory.add_learned_fact_from_llm(raw_response)
                logger.info(f"Apprentissage (texte) : {raw_response}")

    except Exception as e:
        logger.warning(f"Erreur lors de l'apprentissage en arrière-plan : {e}")


def answer_f1_question(user_question: str, history=None, rag_only: Optional[bool] = None, username: Optional[str] = None) -> Tuple[str, List[str]]:
    """Entry point for answering questions with long term memory storage.

    Returns:
        Tuple[str, List[str]]: (response, sources_list)
    """
    response, sources = _answer_f1_question_internal(user_question, history, rag_only, username)

    # Stocker dans la mémoire long terme
    if response and not response.startswith("❌") and not response.startswith("[ERREUR"):
        long_term_memory.store_conversation(user_question, response)

    return response, sources


def _answer_f1_question_internal(user_question: str, history=None, rag_only: Optional[bool] = None, username: Optional[str] = None) -> Tuple[str, List[str]]:
    """
    Pipeline optimisé - ORDRE LOGIQUE:

    Returns:
        Tuple[str, List[str]]: (response, sources_list)
    
    PHASE 1: CONTEXTE (0ms)
    - Historique conversationnel
    - Mémoire long terme
    
    PHASE 2: ROUTAGE RAPIDE (<100ms)
    - Intent Router (regex)
    - Si confiance ≥70% → Handlers rapides
    
    PHASE 3: HANDLERS RAPIDES (<100ms)
    - StandF1 (classements)
    - FIA (calendrier)
    - CSV circuits
    
    PHASE 4: DONNÉES LOCALES (<500ms)
    - Knowledge Base (2233 docs)
    - CSV saisons (parallèle)
    
    PHASE 5: DONNÉES TEMPS RÉEL (<2s)
    - Ergast API (standings actuels)
    
    PHASE 6: ACTUALITÉS (2-3s)
    - Scraping news (motorsport, autosport)
    
    PHASE 7: SYNTHÈSE LLM (2-5s)
    - Ollama LLaMA 3.2 3B avec tout le contexte
    """
    try:
        # CONTEXTE
        user_question = user_question.strip()
        sources = []  # Liste pour tracker les sources utilisées

        if not user_question:
            return "Veuillez poser une question.", sources

        logger.info(f"Question reçue: {user_question}")

        # 1. Récupérer historique conversationnel
        history_text = _format_history(history) if history else ""
        
        # 2. Récupérer contexte mémoire long terme
        lt_context = long_term_memory.get_relevant_context(user_question)
        if lt_context:
            logger.info("Contexte long terme récupéré")

        # ROUTAGE RAPIDE 
        # 3. Intent Router - Détection d'intention sans LLM
        try:
            router = get_router()
            intent = router.detect_intent(user_question)
            # Si confiance élevée et pas besoin LLM → Handler rapide
            if intent and not intent.requires_llm and intent.confidence >= 0.7:
                handler = FAST_HANDLERS.get(intent.name)
                if handler:
                    logger.info(f"⚡ Intent rapide: {intent.name} (conf={intent.confidence:.2f})")
                    return handler()
        except Exception as e:
            logger.warning(f"Routage échoué: {e}")

        # CAS SPÉCIAUX : Détection rapide basée sur le contexte
        q_lower = user_question.lower()
        
        # Date du jour
        if any(keyword in q_lower for keyword in ["date", "aujourd'hui", "quel jour", "quelle date", "jour sommes"]):
            current_date = OptimizedPromptBuilder.get_current_date()
            return f"On est le **{current_date}** ! 📅 Tu veux savoir ce qui se passe en F1 en ce moment ? 🏎️", sources

        # Référence à l'historique
        history_keywords = [
            "première question", "premiere question", "1ere question", "1ère question",
            "question précédente", "question precedente", "dernière question",
            "avant", "tout à l'heure", "ma question", "mes question",
            "j'ai demandé", "conversation", "historique", "contexte",
            "répond", "répondre à", "c'était quoi"
        ]
        if any(keyword in q_lower for keyword in history_keywords):
            if history and len(history) > 0:
                prompt = OptimizedPromptBuilder.build_f1_question(
                    question=user_question,
                    conversation_history=history_text,
                    long_term_context=lt_context
                )
                response = call_ollama(prompt)
                if response and not response.startswith("[ERREUR"):
                    return response, sources
            return "On vient de commencer à discuter, j'ai pas encore d'historique !  C'est quoi ta question sur la F1 ? 🏎️", sources

        # Réponses contextuelles courtes (oui, non, pourquoi, etc.)
        short_responses = ["oui", "non", "ok", "pourquoi", "comment", "quand", "où", "qui", "quoi",
                          "raconte", "explique", "dis moi", "parle moi", "plus", "encore", "détails"]
        if len(q_lower.split()) <= 3 and any(resp in q_lower for resp in short_responses):
            if history and len(history) > 0:
                prompt = OptimizedPromptBuilder.build_f1_question(
                    question=user_question,
                    conversation_history=history_text,
                    long_term_context=lt_context
                )
                response = call_ollama(prompt)
                if response and not response.startswith("[ERREUR"):
                    return response

        # DÉTECTION TYPE DE QUESTION
        rag_mode = RAG_ONLY if rag_only is None else rag_only
        force_f1 = _history_mentions_f1_entities(history_text) and _is_followup_reference(user_question)

        is_f1 = _is_f1_question(user_question)
        is_general = _is_general_question(user_question)
        is_circuit = _is_circuit_question(user_question)

        if force_f1 and not is_f1:
            logger.info("Relance référentielle détectée avec contexte F1 — forçage F1")
            is_f1 = True
            is_general = False

        logger.info(f"F1? {is_f1}, Générale? {is_general}, Circuit? {is_circuit}")

        # Persistance de sujet: si la requête semble générale mais que l'historique récent est F1,
        # basculer vers le pipeline F1 pour éviter d'élargir hors sujet.
        if is_general and not is_f1 and _was_recently_on_f1(history_text):
            logger.info("Relance courte avec historique F1 — persistance sur F1")
            is_f1 = True

        # QUESTIONS SUR CIRCUITS - Chercher dans CSV (prioritaire pour circuits)
        if is_circuit:
            logger.info("Recherche circuit CSV")
            q_lower = user_question.lower()

            # Cas spécial: "circuit le plus long"
            if 'plus long' in q_lower or 'longest' in q_lower:
                circuit = find_longest_circuit()
                if circuit:
                    sources.append("Base de données circuits CSV")
                    return (
                        f"🏎️ Le circuit le plus long en F1 est **{circuit['nom']}** "
                        f"({circuit['lieu']}) avec **{circuit['longueur']}**. {circuit['info']}"
                    ), sources

            # Recherche générale de circuit
            query = (
                user_question
                .replace('circuit', '')
                .replace('piste', '')
                .replace('long', '')
                .strip()
            )
            circuit = search_circuit(query)
            if circuit and circuit['nom']:
                name = circuit.get('nom') or "Ce circuit"
                lieu = circuit.get('lieu') or ""
                courses = circuit.get('courses') or ""
                annees = circuit.get('années') or ""
                nb_gp = circuit.get('nb_gp') or ""

                details = []
                if lieu:
                    details.append(f"à {lieu}")
                if nb_gp:
                    details.append(f"{nb_gp} Grands Prix")
                if courses:
                    details.append(courses)
                if annees:
                    details.append(annees)

                detail_text = " — ".join(details) if details else ""
                sources.append("Base de données circuits CSV")
                return f"🏎️ {name} {detail_text}", sources

        # QUESTIONS F1 - COLLECTE DE CONTEXTE ET CASCADE
        if is_f1:
            logger.info("Pipeline F1 optimisé")
            
            kb_content = None
            ergast_summary = None
            openf1_data = None
            wiki_data = None
            season_csv_summary = None

            # ÉTAPE 1: Knowledge Base (PRIORITAIRE - CHARGEMENT RAPIDE)
            try:
                kb = get_knowledge_base()
                # OPTIMISÉ: top_k=5 (réduit de 15) pour récupérer SEULEMENT les meilleurs, min_score=0.45 (plus strict)
                kb_results = kb.search(user_question, top_k=5, min_score=0.45)
                if kb_results:
                    # Prendre SEULEMENT les meilleurs résultats (limité 3000 chars)
                    kb_content = "\n\n".join(kb_results)[:3000]  # Réduit de 5000→3000
                    logger.info(f"✅ KB PRIORITAIRE: {len(kb_results)} chunks utilisés (score ≥0.45)")
                    sources.append("Knowledge Base F1 (base de connaissances locale)")
                else:
                    logger.info(f"KB: Aucun résultat (score <0.45)")
            except Exception as e:
                logger.warning(f"KB search failed: {e}")

            # ÉTAPE 1.5: Données locales CSV des saisons (f1_wiki_csv)
            # Détection: présence d'une année (1950–2026) ou mot-clé saison/season
            try:
                import re
                year_match = re.search(r"\b(19[5-9]\d|20[0-2]\d|2026)\b", user_question)
                saison_indicators = any(k in q_lower for k in ["saison", "season", "championnat", "classement "])  # espace volontaire après classement
                if year_match or saison_indicators:
                    csv_entries = search_f1_wiki_data(user_question)
                    if csv_entries:
                        # Construire un résumé compact des premières entrées
                        lines = []
                        wiki_link_line = None
                        # Essayer de dériver un lien Wikipedia à partir du dossier source
                        try:
                            from backend.wiki_utils import normalize_wiki_title_from_dir, build_wiki_url_from_title, fetch_wiki_extract_by_title
                            source_dirs = [e.get('source_dir') for e in csv_entries if e.get('source_dir')]
                            source_dirs = [d for d in source_dirs if d]
                            if source_dirs:
                                title = normalize_wiki_title_from_dir(source_dirs[0])
                                url = build_wiki_url_from_title(title)
                                extract = fetch_wiki_extract_by_title(title) or ""
                                if url:
                                    wiki_link_line = f"Page Wiki: [Lien]({url}) — {extract[:200]}"
                        except Exception:
                            pass
                        for entry in csv_entries[:5]:
                            # Afficher fichier source et 2-3 paires clé/valeur courtes
                            src = entry.get('source_file', '')
                            kvs = []
                            for k, v in entry.items():
                                if k == 'source_file':
                                    continue
                                val = str(v).strip()
                                if val:
                                    kvs.append(f"{k}: {val[:60]}")
                                if len(kvs) >= 3:
                                    break
                            line = (src + " — " + "; ".join(kvs)) if kvs else src
                            if line:
                                lines.append(line[:160])
                        if lines:
                            season_csv_summary = "\n".join(lines)
                            if wiki_link_line:
                                season_csv_summary = wiki_link_line + "\n" + season_csv_summary
                                sources.append("Wikipedia F1")
                            sources.append("Données historiques CSV")
                            logger.info(f"Saisons CSV: {len(csv_entries)} entrées (résumé {len(lines)})")
            except Exception as e:
                logger.warning(f"Saison CSV search failed: {e}")

            # ÉTAPE 2: Memory Long Terme (PRIORITÉ #2 après KB)
            # Récupérer contexte mémoire ENRICHI si KB insuffisant
            memory_context = None
            if lt_context:  # lt_context déjà récupéré en début de fonction
                memory_context = lt_context
                logger.info(f"✅ MEMORY: Contexte long terme récupéré ({len(lt_context)} chars)")
            
            # ÉTAPE 3: Standings via StandF1 (sans Ergast)
            standings_keywords = [
                "classement", "classements", "standing", "standings", "points",
                "pilotes", "drivers", "constructeurs", "teams", "team", "équipe", "ecurie", "écurie", "top 10",
                "leader", "premier", "deuxieme", "troisieme", "champion"
            ]
            if any(kw in q_lower for kw in standings_keywords):
                # Choisir pilotes vs constructeurs selon mots-clés
                asks_constructors = any(k in q_lower for k in ["constructeur", "constructeurs", "team", "teams", "équipe", "ecurie", "écurie"]) 
                if asks_constructors:
                    ergast_summary = get_standf1_constructors_summary(top_n=10)
                else:
                    ergast_summary = get_standf1_standings_summary(top_n=10)
                if ergast_summary:
                    logger.info("✅ Standings récupérés via StandF1")
                    sources.append("StandF1.com - Classements en temps réel")
                else:
                    logger.info("Impossible de récupérer les standings via StandF1")

            # ÉTAPE 4: Appel LLM avec PRIORITÉ KB + Memory (PAS de Web Search sauf échec)
            # Construire prompt avec KB + Memory en PRIORITÉ
            prompt = OptimizedPromptBuilder.build_f1_question(
                question=user_question,
                kb_content=kb_content,
                standings=ergast_summary,
                news_summary=season_csv_summary,
                conversation_history=history_text,
                long_term_context=memory_context  # Memory context en priorité
            )
            
            response = call_ollama(prompt)
            
            # ÉTAPE 5: Web Search OPTIONNEL si échec (avec timeout court)
            # Critères d'échec: réponse vide, erreur ou incertaine
            if not response or response.startswith("[ERREUR") or "désolé" in response.lower() or "je n'ai pas" in response.lower() or len(response) < 40:
                logger.info("⚠️ LLM incertain, tentative Web Search (fallback Wikipedia)...")
                
                # Chercher Wikipedia (timeout TRÈS réduit pour respecter <3s)
                wiki_content = []
                try:
                    search_queries = [f"F1 {user_question}"]
                    for search_q in search_queries[:1]:  # Limité à 1 seule requête
                        wiki_params = {"list": "search", "srsearch": search_q, "srlimit": 1}  # 1 seul résultat
                        data = fetch_wikimedia_api("query", params=wiki_params)
                        if data and "query" in data and "search" in data["query"]:
                            for r in data["query"]["search"][:1]:  # Max 1 résultat
                                wiki_content.append(f"{r['title']}: {r['snippet'][:200]}")
                    wiki_data = " | ".join(wiki_content[:1])  # Max 1 snippet
                except Exception as e:
                    logger.warning(f"Web Search échoué: {e}")
                    wiki_data = None

                # Nouveau prompt avec Web Search SEULEMENT si wiki_data existe
                if wiki_data:
                    prompt = OptimizedPromptBuilder.build_f1_question(
                        question=user_question,
                        kb_content=kb_content,
                        standings=ergast_summary,
                        news_summary=wiki_data,
                        conversation_history=history_text,
                        long_term_context=memory_context
                    )
                    response = call_ollama(prompt)
                    sources.append("Recherche web (Wikipedia)")
                    logger.info(f"✅ Web Search utilisé en fallback")

            if response and not response.startswith("[ERREUR"):
                return response, sources

            # Fallback final si toujours rien
            return "Désolé, j'ai cherché dans ma base et sur le web mais je n'ai pas trouvé de détails précis sur ça... 😕 Tu peux me demander autre chose sur la F1 ? 🏎️", sources

        # QUESTIONS GÉNÉRALES (non-F1)
        if is_general and not is_f1:
            logger.info("Question générale (non-F1) — mode libre rapide (pas de KB)")
            # OPTIMISÉ: Pas de recherche KB pour questions générales (trop lent)
            # Mode libre direct sans contexte local
            kb_content = ""

            prompt = OptimizedPromptBuilder.build_general_question(
                question=user_question,
                conversation_history=history_text,
                long_term_context=lt_context
            )

            response = call_ollama(prompt)
            if response and not response.startswith("[ERREUR"):
                return response, sources
            return "Je ne suis pas sûr de comprendre ta question, mais si ça parle de F1, je peux sûrement t'aider !", sources

        # Hors F1 explicite — mode libre
        if not is_f1 and not is_circuit:
            logger.info("Question hors F1 — mode libre")
            # Continuer vers le catch-all intelligent

        # AUTRES QUESTIONS (CATCH-ALL INTELLIGENT)
        logger.info("Question non catégorisée, utilisation du LLM direct")

        prompt = OptimizedPromptBuilder.build_f1_question(
            question=user_question,
            conversation_history=history_text,
            long_term_context=lt_context
        )

        response = call_ollama(prompt)
        if response and not response.startswith("[ERREUR"):
            return response, sources

        # Détecter les salutations pour une réponse de secours chaleureuse
        q_lower_check = user_question.lower()
        if any(salut in q_lower_check for salut in ["bonjour", "salut", "hello", "hi", "hey", "coucou"]):
            return "Salut ! Content de te voir ! Je suis ton assistant F1 personnel. Tu veux qu'on parle de quoi ? Le dernier GP ? Les classements ? Un pilote en particulier ? 🏎️💨", sources

        return "Hey ! Je suis spécialisé dans la Formule 1. Si tu as des questions sur les pilotes, les courses, les circuits, les classements... je suis ton expert ! Qu'est-ce qui t'intéresse ? 😊🏁", sources

    except Exception as exc:
        logger.error(f"answer_f1_question: {exc}")
        import traceback
        traceback.print_exc()
        return "❌ Une erreur s'est produite lors du traitement de votre question. Veuillez réessayer.", []


def load_f1_wiki_csv_data() -> List[Dict]:
    """Charge les données depuis les fichiers CSV dans le dossier f1_wiki_csv."""
    base_path = Path(__file__).parent.parent / "knowledge_base" / "f1_wiki_csv"
    data = []

    for csv_file in base_path.rglob("*.csv"):
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append({
                        'source_file': csv_file.name,
                        'source_dir': csv_file.parent.name,
                        **row
                    })
        except Exception as e:
            logger.warning(f"Erreur lors du chargement de {csv_file}: {e}")

    return data


def search_f1_wiki_data(query: str) -> List[Dict]:
    """Recherche dans les données chargées depuis f1_wiki_csv."""
    data = load_f1_wiki_csv_data()
    query_lower = query.lower().strip()

    if not query_lower:
        return []

    results = []
    for entry in data:
        if any(query_lower in str(value).lower() for value in entry.values()):
            results.append(entry)

    return results


# Scraping helpers for recommended sites
def fetch_openf1_data(endpoint: str, params: Optional[Dict] = None) -> Dict:
    """Fetch data from OpenF1 API."""
    base_url = "https://openf1.org/api"
    try:
        response = http_client.get(f"{base_url}/{endpoint}", params=params, timeout=3)  # Réduit 10s→3s
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        logger.warning(f"OpenF1 API request failed: {e}")
        return {}


def fetch_jolpica_data(endpoint: str, params: Optional[Dict] = None) -> Dict:
    """Fetch data from Jolpica API."""
    base_url = "https://api.jolpi.ca/ergast/f1"
    try:
        response = http_client.get(f"{base_url}/{endpoint}", params=params, timeout=3)  # Réduit 10s→3s
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        logger.warning(f"Jolpica API request failed: {e}")
        return {}


def fetch_wikimedia_api(endpoint: str, params: Optional[Dict] = None) -> Dict:
    """Fetch data from Wikimedia API with proper User-Agent."""
    base_url = "https://en.wikipedia.org/w/api.php"
    try:
        # Wikipedia nécessite un User-Agent valide (sinon 403)
        headers = {
            "User-Agent": "F1ChatBot/1.0 (formula1-assistant; +http://localhost:8002)"
        }
        response = httpx.get(
            base_url, 
            params={**params, "action": "query", "format": "json"}, 
            headers=headers,
            timeout=3
        )
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        logger.warning(f"Wikimedia API request failed: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Wikimedia API error: {e}")
        return {}


def fetch_wikidata_sparql(query: str) -> Dict:
    """Fetch data from Wikidata Query Service using SPARQL."""
    base_url = "https://query.wikidata.org/sparql"
    try:
        response = http_client.get(base_url, params={"query": query, "format": "json"}, timeout=3)  # Réduit 10s→3s
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as e:
        logger.warning(f"Wikidata SPARQL query failed: {e}")
        return {}


def fetch_wikinews_articles(language: str = "en") -> List[Dict]:
    """Fetch recent Formula 1 articles from Wikinews."""
    base_url = f"https://{language}.wikinews.org/w/api.php"
    try:
        response = http_client.get(base_url, params={"action": "query", "list": "categorymembers", "cmtitle": "Category:Formula_One", "format": "json"}, timeout=3)  # Réduit 10s→3s
        response.raise_for_status()
        return response.json().get("query", {}).get("categorymembers", [])
    except httpx.RequestError as e:
        logger.warning(f"Wikinews API request failed: {e}")
        return {}
