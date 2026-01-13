"""
Handlers rapides pour F1 sans LLM
Répondent en <100ms pour les questions simples
"""

from typing import Dict, Any, Optional
import requests
from bs4 import BeautifulSoup
from backend.optimized_cache import get_cache, CACHE_TTL
from backend.standings_utils import get_standf1_standings_summary


# En-têtes HTTP simples pour scraping
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _fetch_url(url: str, timeout: int = 8) -> str:
    """Récupère HTML en gérant les erreurs silencieusement."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""


class F1DataHandler:
    """Handlers pour données F1 rapides"""
    # Ergast retiré: n'utiliser que des sources publiques (FIA/StandF1)
    
    @staticmethod
    def get_standings() -> str:
        """Classements drivers - ultra-rapide avec cache"""
        cache = get_cache()
        cache_key = "standings_drivers"
        
        # Vérifier cache
        cached = cache.get(cache_key)
        if cached:
            return f"📊 (depuis cache)\n\n{cached}"
        
        try:
            summary = get_standf1_standings_summary(top_n=10)
            if summary:
                result = "🏎️ **Classement Pilotes (top 10)** :\n\n" + summary
                cache.set(cache_key, result, CACHE_TTL.get("news_articles", 600))
                return result
            return "⚠️ Classements indisponibles pour le moment (StandF1)."
        except Exception as e:
            return f"⚠️ Impossible de récupérer les classements (StandF1): {e}"
    
    @staticmethod
    def get_next_race() -> str:
        """Prochain GP - ultra-rapide sans Ergast (FIA)"""
        cache = get_cache()
        cache_key = "next_race"
        
        cached = cache.get(cache_key)
        if cached:
            return f"🏁 (depuis cache)\n\n{cached}"
        
        try:
            # Scraper FIA calendrier 2025
            url = "https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship"
            html = _fetch_url(url, timeout=8)
            if not html:
                raise RuntimeError("source FIA indisponible")

            soup = BeautifulSoup(html, "html.parser")
            events = soup.find_all("div", class_=lambda x: x and "event" in x.lower())
            # Prendre le premier événement listé comme prochain GP (approximation)
            if not events:
                raise RuntimeError("Aucun événement FIA détecté")

            text = events[0].get_text(" ", strip=True)
            # Essayer de formater: extraire nom et date heuristiquement
            name = text.split(" - ")[0] if " - " in text else text[:80]
            # Date heuristique: chercher motif JJ mois AAAA
            date = "TBD"
            try:
                import re
                m = re.search(r"(\d{1,2}\s+[A-Za-zéûôîàè]+\s+20\d{2})", text)
                if m:
                    date = m.group(1)
            except Exception:
                pass

            result = f"🏁 **Prochain Grand Prix**\n\n{name}\n📅 {date}\n🔗 Source FIA"
            cache.set(cache_key, result, CACHE_TTL.get("ergast_race", 600))
            return result
        except Exception as e:
            return f"⚠️ Impossible de récupérer le prochain GP (FIA): {e}"
    
    @staticmethod
    def get_rules() -> str:
        """Règles F1 simples - sans API"""
        cache = get_cache()
        cache_key = "rules_basic"
        
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        rules = """📋 **Règles F1 2025**

**Points au podium** :
1️⃣ = 25pts | 2️⃣ = 18pts | 3️⃣ = 15pts | 4️⃣ = 12pts | 5️⃣ = 10pts
6️⃣ = 8pts | 7️⃣ = 6pts | 8️⃣ = 4pts | 9️⃣ = 2pts | 🔟 = 1pt

**Meilleur tour** : +1 point (si dans top 10)

**Distance** : ~307 km (~2h)

**Sécurité** : Halo, KERS, DRS"""
        
        cache.set(cache_key, rules, CACHE_TTL["ergast_standings"])
        return rules


def handle_standings_drivers() -> str:
    """Handler: Classement drivers"""
    return F1DataHandler.get_standings()


def handle_standings_teams() -> str:
    """Handler: Classement teams"""
    # Indisponible sans source fiable stable après retrait Ergast
    return "🏭 **Classement Constructeurs** : Indisponible temporairement (source Ergast retirée)."


def handle_next_race() -> str:
    """Handler: Prochain GP"""
    return F1DataHandler.get_next_race()


def handle_rules() -> str:
    """Handler: Règles F1"""
    return F1DataHandler.get_rules()


def handle_calendar() -> str:
    """Handler: Calendrier (sommaire)"""
    cache = get_cache()
    cache_key = "calendar"
    
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    try:
        # Scraper FIA pour un extrait (3 premiers événements)
        url = "https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship"
        html = _fetch_url(url, timeout=8)
        if not html:
            raise RuntimeError("source FIA indisponible")
        soup = BeautifulSoup(html, "html.parser")
        events = soup.find_all("div", class_=lambda x: x and "event" in x.lower())[:3]
        lines = ["📅 **Calendrier F1 (extrait)** :\n"]
        for ev in events:
            text = ev.get_text(" ", strip=True)
            lines.append(f"• {text[:120]}")
        result = "\n".join(lines) + "\n\n🔗 Source: FIA"
        cache = get_cache()
        cache.set(cache_key, result, CACHE_TTL.get("ergast_race", 600))
        return result
    except Exception as e:
        return f"⚠️ Erreur (FIA): {e}"


# Mappage intent -> handler
FAST_HANDLERS = {
    "standings_drivers": handle_standings_drivers,
    "standings_teams": handle_standings_teams,
    "next_race": handle_next_race,
    "rules": handle_rules,
    "calendar": handle_calendar,
}
