from typing import Optional, List
from bs4 import BeautifulSoup
from backend.optimized_cache import get_cache, CACHE_TTL
from backend.logger import get_logger
import httpx
<<<<<<< HEAD
import random
=======
import logging

logger = logging.getLogger(__name__)
>>>>>>> frontend

logger = get_logger(__name__)

# User-Agents rotatifs pour éviter blocage anti-bot (harmonisé avec f1_bot.py)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

def get_random_headers():
    """Retourne des headers avec User-Agent rotatif pour éviter blocage."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


<<<<<<< HEAD
def _fetch_url(url: str, timeout: int = 6) -> str:  # Timeout augmenté 4s→6s (anti-bot)
    """Récupère une URL avec headers rotatifs et gestion d'erreurs."""
=======
def get_ergast_driver_standings(top_n: int = 10) -> Optional[str]:
    """Récupère le classement des pilotes depuis Jolpica F1 API (successeur d'Ergast)"""
    cache = get_cache()
    cache_key = f"standings:jolpica:top{top_n}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        # Jolpica F1 API - successeur d'Ergast depuis 2024
        url = "https://api.jolpi.ca/ergast/f1/current/driverStandings"
        response = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
        response.raise_for_status()

        data = response.json()
        standings_list = data['MRData']['StandingsTable']['StandingsLists'][0]['DriverStandings']

        summary_items = []
        for standing in standings_list[:top_n]:
            driver_info = standing['Driver']
            name = f"{driver_info['givenName']} {driver_info['familyName']}"
            points = int(standing['points'])
            position = int(standing['position'])
            summary_items.append(f"{position}. {name} — {points} pts")

        if not summary_items:
            return None

        summary = "\n".join(summary_items)
        # Cacher 7 jours pour widgets (604800 sec)
        cache.set(cache_key, summary, CACHE_TTL.get("widget_standings", 604800))
        return summary
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des standings depuis Jolpica: {e}")
        return None


def _fetch_url(url: str, timeout: int = 4) -> str:  # Timeout réduit 8s→4s
>>>>>>> frontend
    try:
        headers = get_random_headers()  # Headers rotatifs à chaque requête
        resp = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except httpx.TimeoutException as e:
        logger.warning(f"Timeout fetching {url}: {e}")
        return ""
    except httpx.HTTPStatusError as e:
        logger.warning(f"HTTP error {e.response.status_code} fetching {url}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error fetching {url}: {type(e).__name__}: {str(e)[:100]}")
        return ""


def get_standf1_standings_summary(top_n: int = 10) -> Optional[str]:
    """Récupère et formate un résumé des classements (pilotes) via StandF1.

    Renvoie une liste markdown: "1. Nom — NN pts" (top_n). Met en cache 7 jours.
    """
    cache = get_cache()
    cache_key = f"standings:standf1:top{top_n}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        html = _fetch_url("https://www.standf1.com/", timeout=6)  # Timeout augmenté 4s→6s (anti-bot)
        if not html:
            logger.warning("StandF1 returned empty HTML")
            return None
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if not table:
            logger.warning("StandF1: No table found in HTML")
            return None

        rows = table.find_all("tr")
        if not rows or len(rows) < 2:
            logger.warning("StandF1: Table has insufficient rows")
            return None

        header_cells = rows[0].find_all(["th", "td"]) if rows else []
        headers = [c.get_text().strip().lower() for c in header_cells] if header_cells else []

        try:
            driver_idx = (headers.index("pilote") if "pilote" in headers else
                          headers.index("driver") if "driver" in headers else 1)
        except ValueError:
            driver_idx = 1
        try:
            points_idx = (headers.index("points") if "points" in headers else
                          headers.index("pt") if "pt" in headers else -1)
        except ValueError:
            points_idx = -1

        summary_items: List[str] = []
        rank = 1
        for tr in rows[1:]:
            cells = tr.find_all("td")
            if not cells:
                continue

            name = None
            pts = None

            if 0 <= driver_idx < len(cells):
                name = cells[driver_idx].get_text().strip()
            elif len(cells) >= 2:
                name = cells[1].get_text().strip()

            if 0 <= points_idx < len(cells):
                pts = cells[points_idx].get_text().strip()
            elif len(cells) >= 3:
                pts = cells[-1].get_text().strip()

            if name:
                if pts:
                    try:
                        pts_clean = ''.join(ch for ch in pts if ch.isdigit())
                        pts = pts_clean if pts_clean else pts
                    except Exception:
                        pass
                summary_items.append(f"{rank}. {name} — {pts} pts" if pts else f"{rank}. {name}")
                rank += 1
                if len(summary_items) >= top_n:
                    break

        if not summary_items:
            logger.warning("StandF1: No standings data extracted")
            return None

        summary = "\n".join(summary_items)
<<<<<<< HEAD
        cache.set(cache_key, summary, CACHE_TTL.get("news_articles", 600))
        logger.info(f"StandF1 standings cached: {len(summary_items)} drivers")
=======
        # Cacher 7 jours pour widgets (604800 sec)
        cache.set(cache_key, summary, CACHE_TTL.get("widget_standings", 604800))
>>>>>>> frontend
        return summary
    except Exception as e:
        logger.error(f"StandF1 standings parse failed: {type(e).__name__}: {str(e)[:100]}")
        return None


def get_lequipe_standings_summary(top_n: int = 10) -> Optional[str]:
    """Récupère le classement pilotes depuis L'Équipe F1 (fallback).
    
    Renvoie markdown: "1. Nom — NN pts" (top_n). Met en cache 7 jours.
    """
    cache = get_cache()
    cache_key = f"standings:lequipe:top{top_n}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        html = _fetch_url("https://www.lequipe.fr/Formule-1/f1-classement-pilotes.html", timeout=5)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        summary_items: List[str] = []

        # Structure L'Équipe: tbody tr avec cellules [Position, Nom, Points, Victoires]
        rows = soup.select("tbody tr")
        
        for tr in rows:
            cells = tr.find_all("td")
            if len(cells) < 3:
                continue

            # Cellules: [0]=Position, [1]=Nom, [2]=Points, [3]=Victoires
            try:
                position = cells[0].get_text(strip=True)
                name = cells[1].get_text(strip=True)
                pts = cells[2].get_text(strip=True)
                
                # Vérifier que c'est une vraie ligne de données
                if not position.isdigit():
                    continue
                if not pts.isdigit():
                    continue
                    
                rank = int(position)
                summary_items.append(f"{rank}. {name} — {pts} pts")
                
                if len(summary_items) >= top_n:
                    break
            except (IndexError, ValueError):
                continue

        if not summary_items:
            return None

        summary = "\n".join(summary_items)
        # Cacher 7 jours pour widgets (604800 sec)
        cache.set(cache_key, summary, CACHE_TTL.get("widget_standings", 604800))
        return summary
    except Exception as e:
        print(f"[WARN] L'Équipe standings parse failed: {e}")
        return None


def get_driver_standings(top_n: int = 10) -> Optional[str]:
    """Récupère le classement pilotes avec fallbacks Jolpica → StandF1 → L'Équipe."""
    # 1. Essayer Jolpica F1 API (successeur d'Ergast)
    result = get_ergast_driver_standings(top_n)
    if result:
        return result

    # 2. Fallback StandF1
    result = get_standf1_standings_summary(top_n)
    if result:
        return result

    # 3. Fallback L'Équipe
    result = get_lequipe_standings_summary(top_n)
    if result:
        return result

    # 4. Données du classement F1 2024 (dernier classement officiel disponible)
    # Source: Classement final Pilotes 2024
    mock_standings = [
        "1. Max Verstappen — 437 pts",
        "2. Lando Norris — 374 pts",
        "3. Charles Leclerc — 356 pts",
        "4. Oscar Piastri — 292 pts",
        "5. Carlos Sainz — 290 pts",
        "6. George Russell — 245 pts",
        "7. Lewis Hamilton — 223 pts",
        "8. Sergio Pérez — 152 pts",
        "9. Fernando Alonso — 70 pts",
        "10. Pierre Gasly — 42 pts",
    ]
    return "\n".join(mock_standings[:top_n])


def get_standf1_constructors_summary(top_n: int = 10) -> Optional[str]:
    """Récupère et formate un résumé des classements (constructeurs) via StandF1.

    Détecte la table des équipes par les en-têtes ('constructeur', 'équipe', 'team').
    Renvoie markdown: "1. Équipe — NN pts" (top_n). Met en cache ~10 min.
    """
    cache = get_cache()
    cache_key = f"standings:standf1:constructors:top{top_n}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        html = _fetch_url("https://www.standf1.com/", timeout=6)  # Timeout augmenté 4s→6s (anti-bot)
        if not html:
            logger.warning("StandF1 constructors returned empty HTML")
            return None
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table")
        if not tables:
            logger.warning("StandF1 constructors: No tables found")
            return None

        target_table = None
        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue
            header_cells = rows[0].find_all(["th", "td"]) if rows else []
            headers = [c.get_text().strip().lower() for c in header_cells] if header_cells else []
            header_text = " ".join(headers)
            if any(k in header_text for k in ["constructeur", "équipe", "team"]):
                target_table = table
                break

        # fallback: si pas trouvé par en-tête, prendre la 2e table si dispo
        if target_table is None and len(tables) >= 2:
            target_table = tables[1]

        if not target_table:
            logger.warning("StandF1 constructors: No suitable table found")
            return None

        rows = target_table.find_all("tr")
        if not rows or len(rows) < 2:
            logger.warning("StandF1 constructors: Table has insufficient rows")
            return None

        header_cells = rows[0].find_all(["th", "td"]) if rows else []
        headers = [c.get_text().strip().lower() for c in header_cells] if header_cells else []

        # indices probables
        try:
            team_idx = (headers.index("équipe") if "équipe" in headers else
                        headers.index("team") if "team" in headers else
                        headers.index("constructeur") if "constructeur" in headers else 1)
        except ValueError:
            team_idx = 1
        try:
            points_idx = (headers.index("points") if "points" in headers else
                          headers.index("pt") if "pt" in headers else -1)
        except ValueError:
            points_idx = -1

        summary_items: List[str] = []
        rank = 1
        for tr in rows[1:]:
            cells = tr.find_all("td")
            if not cells:
                continue

            team = None
            pts = None

            if 0 <= team_idx < len(cells):
                team = cells[team_idx].get_text().strip()
            elif len(cells) >= 2:
                team = cells[1].get_text().strip()

            if 0 <= points_idx < len(cells):
                pts = cells[points_idx].get_text().strip()
            elif len(cells) >= 3:
                pts = cells[-1].get_text().strip()

            if team:
                if pts:
                    try:
                        pts_clean = ''.join(ch for ch in pts if ch.isdigit())
                        pts = pts_clean if pts_clean else pts
                    except Exception:
                        pass
                summary_items.append(f"{rank}. {team} — {pts} pts" if pts else f"{rank}. {team}")
                rank += 1
                if len(summary_items) >= top_n:
                    break

        if not summary_items:
            logger.warning("StandF1 constructors: No data extracted")
            return None

        summary = "\n".join(summary_items)
        cache.set(cache_key, summary, CACHE_TTL.get("news_articles", 600))
        logger.info(f"StandF1 constructors cached: {len(summary_items)} teams")
        return summary
    except Exception as e:
        logger.error(f"StandF1 constructors parse failed: {type(e).__name__}: {str(e)[:100]}")
        return None
