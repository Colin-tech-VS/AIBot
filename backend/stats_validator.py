"""
Validateur et consolidateur de statistiques F1
Assure la cohérence des données entre sources (CSV, scraping, cache)
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from collections import defaultdict
import re

from backend.logger import get_logger

logger = get_logger(__name__)


# ============================================================================
# DONNÉES DE RÉFÉRENCE (dynamique selon l'année courante)
# ============================================================================

from datetime import datetime

CURRENT_YEAR = datetime.now().year

# Nombre de courses disputées par saison (à mettre à jour selon la saison)
SEASON_DATA = {
    2024: {
        "total_scheduled": 24,
        "completed": 24,  # Saison terminée
        "last_race": "Abu Dhabi",
        "champion_driver": "Verstappen",
        "champion_team": "McLaren"
    },
    2025: {
        "total_scheduled": 24,
        "completed": 24,  # À mettre à jour si on revient en 2025
        "last_race": "Abu Dhabi",
        "champion_driver": "Verstappen",  # À confirmer
        "champion_team": "TBD"
    },
    2026: {
        "total_scheduled": 24,  # Nombre total de GP prévus en 2026
        "completed": 0,  # À mettre à jour après chaque course
        "last_race": None,  # Nom du dernier GP terminé
        "last_update": "2026-01-14"
    }
}

# Compatibilité avec l'ancien code
RACES_2025 = SEASON_DATA.get(2025, SEASON_DATA[2026])

# Statistiques maximales théoriques par saison
MAX_STATS_PER_SEASON = {
    "wins": lambda races: races,  # Max victoires = nb courses
    "podiums": lambda races: races,  # Max podiums = nb courses
    "poles": lambda races: races,  # Max poles = nb courses
    "points_per_race_max": 26,  # 25 pts victoire + 1 pt meilleur tour
    "points_per_race_sprint": 34,  # Avec sprint (25+8+1)
}

# Pilotes actuels 2025 (liste de référence)
CURRENT_DRIVERS_2025 = {
    "verstappen": {"team": "Red Bull", "number": 1},
    "perez": {"team": "Red Bull", "number": 11},
    "hamilton": {"team": "Ferrari", "number": 44},
    "leclerc": {"team": "Ferrari", "number": 16},
    "norris": {"team": "McLaren", "number": 4},
    "piastri": {"team": "McLaren", "number": 81},
    "russell": {"team": "Mercedes", "number": 63},
    "antonelli": {"team": "Mercedes", "number": 12},
    "alonso": {"team": "Aston Martin", "number": 14},
    "stroll": {"team": "Aston Martin", "number": 18},
    "gasly": {"team": "Alpine", "number": 10},
    "doohan": {"team": "Alpine", "number": 61},
    "tsunoda": {"team": "Racing Bulls", "number": 22},
    "lawson": {"team": "Racing Bulls", "number": 30},
    "albon": {"team": "Williams", "number": 23},
    "sainz": {"team": "Williams", "number": 55},
    "hulkenberg": {"team": "Sauber", "number": 27},
    "bortoleto": {"team": "Sauber", "number": 5},
    "magnussen": {"team": "Haas", "number": 20},
    "bearman": {"team": "Haas", "number": 87},
}

# Équipes 2025
CURRENT_TEAMS_2025 = [
    "Red Bull", "Ferrari", "McLaren", "Mercedes", "Aston Martin",
    "Alpine", "Racing Bulls", "Williams", "Sauber", "Haas"
]


# ============================================================================
# FONCTIONS DE VALIDATION
# ============================================================================

def validate_stat_value(stat_type: str, value: Any, year: int = 2025, races_completed: int = None) -> Tuple[bool, str]:
    """
    Valide une valeur statistique pour détecter les incohérences.
    
    Returns:
        (is_valid, message) - True si valide, message d'erreur sinon
    """
    if races_completed is None:
        races_completed = RACES_2025.get("completed", 0)
    
    try:
        val = int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return False, f"Valeur non numérique: {value}"
    
    if val < 0:
        return False, f"Valeur négative invalide: {val}"
    
    # Validation par type de stat
    if stat_type in ["wins", "victoires"]:
        max_possible = races_completed if year == 2025 else 24
        if val > max_possible:
            return False, f"{val} victoires impossibles ({max_possible} courses max en {year})"
    
    elif stat_type in ["podiums", "podium"]:
        max_possible = races_completed if year == 2025 else 24
        if val > max_possible:
            return False, f"{val} podiums impossibles ({max_possible} courses max en {year})"
    
    elif stat_type in ["poles", "pole_positions"]:
        max_possible = races_completed if year == 2025 else 24
        if val > max_possible:
            return False, f"{val} poles impossibles ({max_possible} courses max en {year})"
    
    elif stat_type == "points":
        # Points max théoriques pour une saison
        max_points = MAX_STATS_PER_SEASON["points_per_race_sprint"] * (races_completed if year == 2025 else 24)
        if val > max_points:
            return False, f"{val} points impossible (max ~{max_points} en {year})"
    
    return True, "OK"


def normalize_driver_name(name: str) -> str:
    """Normalise un nom de pilote pour comparaison."""
    if not name:
        return ""
    
    name = name.lower().strip()
    # Enlever titres, espaces multiples
    name = re.sub(r'\s+', ' ', name)
    name = name.replace("jr.", "").replace("jr", "").strip()
    
    # Mapper les variantes communes
    aliases = {
        "max verstappen": "verstappen",
        "lewis hamilton": "hamilton",
        "charles leclerc": "leclerc",
        "carlos sainz": "sainz",
        "lando norris": "norris",
        "oscar piastri": "piastri",
        "george russell": "russell",
        "kimi antonelli": "antonelli",
        "fernando alonso": "alonso",
        "lance stroll": "stroll",
        "pierre gasly": "gasly",
        "jack doohan": "doohan",
        "yuki tsunoda": "tsunoda",
        "liam lawson": "lawson",
        "alexander albon": "albon",
        "alex albon": "albon",
        "nico hulkenberg": "hulkenberg",
        "gabriel bortoleto": "bortoleto",
        "kevin magnussen": "magnussen",
        "oliver bearman": "bearman",
        "sergio perez": "perez",
        "checo perez": "perez",
    }
    
    for full, short in aliases.items():
        if full in name or name == short:
            return short
    
    # Si pas d'alias, retourner le nom de famille (dernier mot)
    parts = name.split()
    return parts[-1] if parts else name


def cross_validate_standings(standings_data: List[Dict], source: str = "unknown") -> Tuple[List[Dict], List[str]]:
    """
    Valide et nettoie les données de classement.
    
    Returns:
        (cleaned_data, warnings) - Données nettoyées et liste d'avertissements
    """
    warnings = []
    cleaned = []
    
    seen_positions = set()
    seen_drivers = set()
    
    for entry in standings_data:
        driver = normalize_driver_name(entry.get("driver", "") or entry.get("Driver", "") or entry.get("nom", ""))
        position = entry.get("position") or entry.get("Position") or entry.get("pos")
        points = entry.get("points") or entry.get("Points") or entry.get("pts")
        
        # Vérifier doublons
        if position and position in seen_positions:
            warnings.append(f"[{source}] Position dupliquée: {position}")
        if driver and driver in seen_drivers:
            warnings.append(f"[{source}] Pilote dupliqué: {driver}")
            continue  # Skip le doublon
        
        # Valider les points
        if points:
            is_valid, msg = validate_stat_value("points", points)
            if not is_valid:
                warnings.append(f"[{source}] {driver}: {msg}")
        
        if position:
            seen_positions.add(position)
        if driver:
            seen_drivers.add(driver)
        
        cleaned.append(entry)
    
    return cleaned, warnings


def consolidate_driver_stats(csv_data: Dict, scraped_data: Dict, cache_data: Dict = None) -> Dict:
    """
    Consolide les statistiques d'un pilote depuis plusieurs sources.
    Priorise: Cache récent > Scraped > CSV (données historiques).
    
    Returns:
        Dictionnaire consolidé avec les meilleures données disponibles
    """
    consolidated = {}
    sources_used = []
    
    # Champs à consolider
    stat_fields = ["wins", "podiums", "poles", "points", "championships", "fastest_laps"]
    
    for field in stat_fields:
        values = []
        
        # Collecter valeurs de chaque source
        if cache_data and field in cache_data:
            values.append(("cache", cache_data[field]))
        if scraped_data and field in scraped_data:
            values.append(("scraped", scraped_data[field]))
        if csv_data and field in csv_data:
            values.append(("csv", csv_data[field]))
        
        if not values:
            continue
        
        # Si une seule source, l'utiliser
        if len(values) == 1:
            consolidated[field] = values[0][1]
            sources_used.append(values[0][0])
            continue
        
        # Plusieurs sources: prioriser cache > scraped > csv
        # Mais vérifier la cohérence
        cache_val = next((v for s, v in values if s == "cache"), None)
        scraped_val = next((v for s, v in values if s == "scraped"), None)
        csv_val = next((v for s, v in values if s == "csv"), None)
        
        # Utiliser le cache s'il est valide
        if cache_val is not None:
            is_valid, _ = validate_stat_value(field, cache_val)
            if is_valid:
                consolidated[field] = cache_val
                sources_used.append("cache")
                continue
        
        # Sinon scraped
        if scraped_val is not None:
            is_valid, _ = validate_stat_value(field, scraped_val)
            if is_valid:
                consolidated[field] = scraped_val
                sources_used.append("scraped")
                continue
        
        # Sinon CSV (données historiques)
        if csv_val is not None:
            consolidated[field] = csv_val
            sources_used.append("csv")
    
    consolidated["_sources"] = list(set(sources_used))
    return consolidated


def format_stats_with_context(stats: Dict, driver_name: str, year: int = 2025) -> str:
    """
    Formate les statistiques avec contexte temporel.
    Ajoute des précisions sur la période des données.
    """
    lines = [f"**{driver_name}** - Statistiques"]
    
    races_completed = RACES_2025.get("completed", 0)
    
    if year == 2025:
        if races_completed == 0:
            lines.append(f"⚠️ *La saison 2025 n'a pas encore commencé*")
        else:
            lines.append(f"📊 *Après {races_completed} courses sur {RACES_2025['total_scheduled']}*")
    
    # Formater chaque stat
    stat_labels = {
        "wins": "🏆 Victoires",
        "podiums": "🥇 Podiums",
        "poles": "⏱️ Pole positions",
        "points": "📈 Points",
        "championships": "🏅 Championnats",
        "fastest_laps": "⚡ Meilleurs tours"
    }
    
    for key, label in stat_labels.items():
        if key in stats and stats[key]:
            val = stats[key]
            # Ajouter contexte si 2025
            if year == 2025 and races_completed > 0 and key in ["wins", "podiums", "poles"]:
                lines.append(f"{label}: **{val}** (sur {races_completed} courses)")
            else:
                lines.append(f"{label}: **{val}**")
    
    # Sources
    if "_sources" in stats:
        lines.append(f"\n*Sources: {', '.join(stats['_sources'])}*")
    
    return "\n".join(lines)


def detect_temporal_inconsistency(question: str, response: str) -> Optional[str]:
    """
    Détecte les incohérences temporelles dans une réponse.
    Ex: donner des stats 2024 quand on demande 2025.
    
    Returns:
        Message de correction si incohérence, None sinon
    """
    q_lower = question.lower()
    r_lower = response.lower()
    
    # Extraire l'année demandée
    year_match = re.search(r"\b(202[4-6]|2025)\b", q_lower)
    asked_year = int(year_match.group(1)) if year_match else 2025
    
    # Vérifier si la réponse parle d'une autre année
    response_years = re.findall(r"\b(202[0-6])\b", r_lower)
    
    if asked_year == 2025:
        # Si on demande 2025 mais la réponse parle principalement de 2024
        if response_years.count("2024") > response_years.count("2025"):
            return "⚠️ **Note:** Ces statistiques concernent la saison 2024. La saison 2025 est en cours."
        
        # Si pas encore de courses en 2025
        if RACES_2025.get("completed", 0) == 0:
            stat_keywords = ["victoire", "podium", "points", "classement", "gagné", "remporté"]
            if any(kw in q_lower for kw in stat_keywords):
                return "⚠️ **Note:** La saison 2025 n'a pas encore commencé. Les statistiques affichées sont celles de 2024."
    
    return None


def add_coherence_disclaimer(response: str, question: str) -> str:
    """
    Ajoute un disclaimer de cohérence si nécessaire.
    """
    disclaimer = detect_temporal_inconsistency(question, response)
    if disclaimer:
        return f"{response}\n\n{disclaimer}"
    return response


# ============================================================================
# MISE À JOUR DES DONNÉES DE SAISON
# ============================================================================

def update_season_progress(races_completed: int, last_race: str = None):
    """Met à jour le nombre de courses disputées en 2025."""
    global RACES_2025
    RACES_2025["completed"] = races_completed
    RACES_2025["last_race"] = last_race
    RACES_2025["last_update"] = datetime.now().strftime("%Y-%m-%d")
    logger.info(f"Saison 2025 mise à jour: {races_completed} courses, dernier GP: {last_race}")


def get_season_context() -> str:
    """Retourne le contexte de la saison actuelle."""
    completed = RACES_2025.get("completed", 0)
    total = RACES_2025.get("total_scheduled", 24)
    last_race = RACES_2025.get("last_race", "N/A")
    
    if completed == 0:
        return "La saison 2025 n'a pas encore commencé."
    elif completed == total:
        return f"La saison 2025 est terminée ({total} courses)."
    else:
        return f"Saison 2025: {completed}/{total} courses disputées (dernier GP: {last_race})."
