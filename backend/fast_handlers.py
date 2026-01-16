"""
Handlers rapides pour F1 sans LLM
Répondent en <100ms pour les questions simples
"""

from typing import Dict, Any, Optional, Tuple, List
import httpx
from bs4 import BeautifulSoup
from backend.optimized_cache import get_cache, CACHE_TTL
from backend.standings_utils import get_standf1_standings_summary, get_standf1_constructors_summary


# En-têtes HTTP simples pour scraping
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _fetch_url(url: str, timeout: int = 4) -> str:  # Timeout réduit 8s→4s
    """Récupère HTML en gérant les erreurs silencieusement."""
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return ""


class F1DataHandler:
    """Handlers rapides pour les questions F1 simples (classements, calendrier)."""
    
    @staticmethod
    def handle_standings_drivers() -> Tuple[str, List[str]]:
        """Classement pilotes (StandF1 temps réel)."""
        summary = get_standf1_standings_summary(top_n=10)
        sources = ["StandF1.com - Classements pilotes temps réel"]
        if summary:
            return summary, sources
        return "Impossible de récupérer le classement pilotes pour le moment. 😕", []
    
    @staticmethod
<<<<<<< HEAD
    def handle_standings_teams() -> Tuple[str, List[str]]:
        """Classement constructeurs (StandF1 temps réel)."""
        summary = get_standf1_constructors_summary(top_n=10)
        sources = ["StandF1.com - Classements constructeurs temps réel"]
        if summary:
            return summary, sources
        return "Impossible de récupérer le classement constructeurs pour le moment. 😕", []
=======
    def get_next_race() -> str:
        """Prochain GP - ultra-rapide via endpoint Aurupteur (ne pas scraper FIA)"""
        cache = get_cache()
        cache_key = "next_race"
        
        cached = cache.get(cache_key)
        if cached:
            return f"🏁 (depuis cache)\n\n{cached}"
        
        try:
            # Utiliser le endpoint /next_race_countdown qui scrape Aurupteur efficacement
            import httpx
            response = httpx.get("http://localhost:8001/next_race_countdown", timeout=3)
            if response.status_code == 200:
                data = response.json()
                if data.get("countdown") and data.get("race_name"):
                    result = f"🏁 **Prochain Grand Prix**\n\n{data['race_name']}\n⏱️ {data['countdown']}\n📅 {data.get('date', 'N/A')}\n🔗 Source: {data.get('source', 'Aurupteur')}"
                    cache.set(cache_key, result, CACHE_TTL.get("ergast_race", 600))
                    return result
            
            # Fallback si endpoint ne répond pas
            raise RuntimeError("endpoint /next_race_countdown indisponible")
        except Exception as e:
            return f"⏰ Prochain GP: Australie - 8 mars 2026 (données Aurupteur indisponibles: {str(e)[:50]})"
>>>>>>> frontend
    
    @staticmethod
    def handle_next_race() -> Tuple[str, List[str]]:
        """Prochaine course (calendrier)."""
        # TODO: implémenter récupération prochaine course
        return "Fonctionnalité 'prochaine course' en développement. 🚧", []
    
    @staticmethod
    def handle_calendar() -> Tuple[str, List[str]]:
        """Calendrier complet."""
        # TODO: implémenter calendrier complet
        return "Fonctionnalité 'calendrier' en développement. 🚧", []


# Réponse sensible pour vie privée pilotes
SENSITIVE_RESPONSE = """🙏 **Respect de la vie privée**

Cette question concerne un événement **hors contexte F1** et touche à la vie privée d'un pilote.

**Informations publiques disponibles** :
- **Michael Schumacher** : accident de ski en décembre 2013 à Méribel. Sa famille demande le respect de sa vie privée depuis 2014, et aucune information médicale publique récente n'est disponible.
- **Ayrton Senna** : décédé le 1er mai 1994 suite à un accident au GP de Saint-Marin (Imola). Son héritage inspire toujours la F1.
- **Niki Lauda** : accident au Nürburgring en 1976, retour héroïque 6 semaines plus tard. Décédé en 2019.

Par respect pour les personnes concernées et leurs familles, je privilégie les discussions sur les **carrières F1 légendaires** de ces pilotes.

📚 **Intéressé par leur palmarès ?** Demande-moi sur les **7 titres de Schumi**, les **41 victoires de Senna**, ou le **retour miraculeux de Lauda** ! 🏆🏎️
"""


# Mapping des handlers pour intent_router
FAST_HANDLERS = {
    "standings_drivers": F1DataHandler.handle_standings_drivers,
    "standings_teams": F1DataHandler.handle_standings_teams,
    "next_race": F1DataHandler.handle_next_race,
    "calendar": F1DataHandler.handle_calendar,
    "driver_personal_life": lambda: (SENSITIVE_RESPONSE, ["Knowledge Base - Pilotes Légendaires"]),
}
