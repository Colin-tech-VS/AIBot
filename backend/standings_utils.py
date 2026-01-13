from typing import Optional, List
from bs4 import BeautifulSoup
from backend.optimized_cache import get_cache, CACHE_TTL
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _fetch_url(url: str, timeout: int = 8) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""


def get_standf1_standings_summary(top_n: int = 10) -> Optional[str]:
    """Récupère et formate un résumé des classements (pilotes) via StandF1.

    Renvoie une liste markdown: "1. Nom — NN pts" (top_n). Met en cache ~10 min.
    """
    cache = get_cache()
    cache_key = f"standings:standf1:top{top_n}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    try:
        html = _fetch_url("https://www.standf1.com/", timeout=8)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        table = soup.find("table")
        if not table:
            return None

        rows = table.find_all("tr")
        if not rows or len(rows) < 2:
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
            return None

        summary = "\n".join(summary_items)
        cache.set(cache_key, summary, CACHE_TTL.get("news_articles", 600))
        return summary
    except Exception as e:
        print(f"[WARN] StandF1 standings parse failed: {e}")
        return None


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
        html = _fetch_url("https://www.standf1.com/", timeout=8)
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        tables = soup.find_all("table")
        if not tables:
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
            return None

        rows = target_table.find_all("tr")
        if not rows or len(rows) < 2:
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
            return None

        summary = "\n".join(summary_items)
        cache.set(cache_key, summary, CACHE_TTL.get("news_articles", 600))
        return summary
    except Exception as e:
        print(f"[WARN] StandF1 constructors parse failed: {e}")
        return None
