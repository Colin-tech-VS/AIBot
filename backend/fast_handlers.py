"""
Handlers rapides pour F1 sans LLM
Répondent en <100ms pour les questions simples
"""

from typing import Dict, Any
import requests
from backend.optimized_cache import get_cache, CACHE_TTL


class F1DataHandler:
    """Handlers pour données F1 rapides"""
    
    ERGAST_BASE = "http://ergast.com/api/f1"
    
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
            # Récupérer standings actuels
            url = f"{F1DataHandler.ERGAST_BASE}/current/driverStandings.json?limit=10"
            resp = requests.get(url, timeout=3)
            data = resp.json()
            
            standings = data.get("MRData", {}).get("StandingsTable", {}).get("Standings", [{}])[0]
            drivers = standings.get("DriverStandings", [])
            
            # Format ultra-compact
            lines = ["🏎️ **Classement Pilotes 2025** :\n"]
            for i, driver in enumerate(drivers[:5], 1):
                driver_info = driver.get("Driver", {})
                name = f"{driver_info.get('givenName')} {driver_info.get('familyName')}"
                points = driver.get("points")
                lines.append(f"{i}. **{name}** - {points} pts")
            
            result = "\n".join(lines)
            cache.set(cache_key, result, CACHE_TTL["ergast_standings"])
            return result
        
        except Exception as e:
            return f"⚠️ Impossible de récupérer les classements: {e}"
    
    @staticmethod
    def get_next_race() -> str:
        """Prochain GP - ultra-rapide"""
        cache = get_cache()
        cache_key = "next_race"
        
        cached = cache.get(cache_key)
        if cached:
            return f"🏁 (depuis cache)\n\n{cached}"
        
        try:
            url = f"{F1DataHandler.ERGAST_BASE}/current.json"
            resp = requests.get(url, timeout=3)
            data = resp.json()
            
            races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
            next_race = next((r for r in races if "Results" not in r), races[-1])
            
            name = next_race.get("name", "GP")
            date = next_race.get("date", "TBD")
            circuit = next_race.get("Circuit", {}).get("circuitName", "Unknown")
            
            result = f"🏁 **Prochain Grand Prix**\n\n{name}\n📍 {circuit}\n📅 {date}"
            cache.set(cache_key, result, CACHE_TTL["ergast_race"])
            return result
        
        except Exception as e:
            return f"⚠️ Impossible de récupérer le prochain GP: {e}"
    
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
    cache = get_cache()
    cache_key = "standings_teams"
    
    cached = cache.get(cache_key)
    if cached:
        return f"📊 (depuis cache)\n\n{cached}"
    
    try:
        url = f"http://ergast.com/api/f1/current/constructorStandings.json?limit=10"
        resp = requests.get(url, timeout=3)
        data = resp.json()
        
        standings = data.get("MRData", {}).get("StandingsTable", {}).get("Standings", [{}])[0]
        constructors = standings.get("ConstructorStandings", [])
        
        lines = ["🏭 **Classement Constructeurs 2025** :\n"]
        for i, constructor in enumerate(constructors[:5], 1):
            name = constructor.get("Constructor", {}).get("name", "Unknown")
            points = constructor.get("points")
            lines.append(f"{i}. **{name}** - {points} pts")
        
        result = "\n".join(lines)
        cache.set(cache_key, result, CACHE_TTL["ergast_standings"])
        return result
    
    except Exception as e:
        return f"⚠️ Erreur: {e}"


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
        url = "http://ergast.com/api/f1/current.json"
        resp = requests.get(url, timeout=3)
        data = resp.json()
        
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        
        lines = ["📅 **Calendrier F1 2025** :\n"]
        for race in races[:3]:
            name = race.get("name", "GP")
            date = race.get("date", "TBD")
            lines.append(f"• {name} ({date})")
        
        result = "\n".join(lines) + "\n\n... (voir Ergast pour calendrier complet)"
        cache.set(cache_key, result, CACHE_TTL["ergast_race"])
        return result
    
    except Exception as e:
        return f"⚠️ Erreur: {e}"


# Mappage intent -> handler
FAST_HANDLERS = {
    "standings_drivers": handle_standings_drivers,
    "standings_teams": handle_standings_teams,
    "next_race": handle_next_race,
    "rules": handle_rules,
    "calendar": handle_calendar,
}
