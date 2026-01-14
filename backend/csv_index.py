"""Index inverse pour recherche rapide dans les CSV F1."""
from pathlib import Path
from typing import Dict, List, Set, Optional
from collections import defaultdict
import csv
import re

from backend.logger import get_logger

logger = get_logger(__name__)

_CSV_DATA: List[Dict] = []
_INVERTED_INDEX: Dict[str, Set[int]] = defaultdict(set)
_PRIORITY_INDEX: Dict[str, Set[int]] = defaultdict(set)
_LOADED = False

CSV_DIR = Path(__file__).parent.parent / "knowledge_base" / "f1_wiki_csv"

STOP_WORDS = {
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "qui", "que",
    "quoi", "est", "sont", "a", "ont", "fait", "faire", "pour", "par", "sur",
    "dans", "avec", "sans", "plus", "moins", "aussi", "bien", "mal",
    "tout", "tous", "cette", "ces", "mon", "ton", "son", "notre", "votre",
    "leur", "quel", "quelle", "quels", "quelles", "comment", "pourquoi",
    "quand", "combien", "parle", "moi", "dit", "dis", "donne", "infos"
}

SYNONYMS = {
    "champion": ["titre", "championship", "wdc", "wcc"],
    "victoire": ["win", "wins", "gagne", "victory"],
    "grand prix": ["gp", "course", "race"],
    "pole": ["pole position", "poles"],
    "podium": ["podiums", "top3"],
    "ecurie": ["team", "equipe", "constructor"],
    "pilote": ["driver", "coureur"],
    "points": ["pts", "score"],
    "saison": ["season", "year"],
}

PRIORITY_FIELDS = {"Driver", "Team", "Pilote", "Constructor", "Name", "Nom"}
STATS_FIELDS = {"Race wins", "Podiums", "Pole positions", "Points", "Championships"}


def load_csv_index():
    global _CSV_DATA, _INVERTED_INDEX, _PRIORITY_INDEX, _LOADED
    
    if _LOADED:
        return
    
    import time
    start = time.time()
    
    _CSV_DATA = []
    _INVERTED_INDEX = defaultdict(set)
    _PRIORITY_INDEX = defaultdict(set)
    
    if not CSV_DIR.exists():
        logger.warning(f"Dossier CSV non trouve: {CSV_DIR}")
        _LOADED = True
        return
    
    csv_files = list(CSV_DIR.rglob("*.csv"))
    
    for csv_file in csv_files:
        try:
            with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    idx = len(_CSV_DATA)
                    row["_source_file"] = str(csv_file.name)
                    _CSV_DATA.append(row)
                    
                    for field, value in row.items():
                        if not value or field.startswith("_"):
                            continue
                        tokens = _tokenize(str(value))
                        for token in tokens:
                            if len(token) >= 2:
                                _INVERTED_INDEX[token].add(idx)
                                if field in PRIORITY_FIELDS:
                                    _PRIORITY_INDEX[token].add(idx)
        except Exception as e:
            logger.warning(f"Erreur lecture {csv_file}: {e}")
    
    elapsed = time.time() - start
    logger.info(f"Index CSV charge: {len(_CSV_DATA)} entrees, {len(_INVERTED_INDEX)} mots-cles ({elapsed:.2f}s)")
    _LOADED = True


def _tokenize(text):
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    tokens = text.split()
    return [t for t in tokens if t and t not in STOP_WORDS]


def _expand_query(query):
    tokens = _tokenize(query)
    expanded = set(tokens)
    for token in tokens:
        for base, syns in SYNONYMS.items():
            if token == base or token in syns:
                expanded.add(base)
                expanded.update(syns)
    return list(expanded)


def search_csv(query, max_results=50):
    if not _LOADED:
        load_csv_index()
    if not _CSV_DATA:
        return []
    
    tokens = _expand_query(query)
    if not tokens:
        return []
    
    scores = defaultdict(float)
    
    for token in tokens:
        if token in _PRIORITY_INDEX:
            for idx in _PRIORITY_INDEX[token]:
                scores[idx] += 10
        if token in _INVERTED_INDEX:
            for idx in _INVERTED_INDEX[token]:
                scores[idx] += 2
        for indexed_token in _INVERTED_INDEX:
            if indexed_token.startswith(token) and indexed_token != token:
                for idx in _INVERTED_INDEX[indexed_token]:
                    scores[idx] += 1
    
    for idx in scores:
        row = _CSV_DATA[idx]
        for field in STATS_FIELDS:
            if row.get(field):
                scores[idx] += 5
                break
    
    sorted_indices = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    
    results = []
    seen_names = set()
    
    for idx in sorted_indices[:max_results * 2]:
        row = _CSV_DATA[idx]
        name = row.get("Driver") or row.get("Team") or row.get("Pilote") or ""
        name_key = name.lower().strip()
        if name_key and name_key in seen_names:
            continue
        if name_key:
            seen_names.add(name_key)
        results.append(row)
        if len(results) >= max_results:
            break
    
    return results


def get_driver_info(name):
    results = search_csv(name, max_results=1)
    return results[0] if results else None


def get_season_results(year):
    return search_csv(str(year), max_results=30)


def search_csv_by_field(field, value):
    if not _LOADED:
        load_csv_index()
    results = []
    value_lower = value.lower()
    for row in _CSV_DATA:
        if field in row and value_lower in str(row[field]).lower():
            results.append(row)
    return results[:50]


def get_index_stats():
    if not _LOADED:
        load_csv_index()
    return {
        "total_entries": len(_CSV_DATA),
        "unique_keywords": len(_INVERTED_INDEX),
        "priority_names": len(_PRIORITY_INDEX),
        "loaded": _LOADED
    }


def format_csv_results_for_llm(results, max_results=10):
    if not results:
        return ""
    
    lines = ["Donnees F1 trouvees:\n"]
    
    for r in results[:max_results]:
        name = r.get("Driver") or r.get("Team") or r.get("Pilote") or r.get("Constructor") or ""
        if name:
            lines.append(f"**{name}**")
        
        champ = r.get("Drivers Championships") or r.get("Championships")
        if champ:
            lines.append(f"  - Championnats: {champ}")
        
        wins = r.get("Race wins") or r.get("Wins")
        if wins:
            lines.append(f"  - Victoires: {wins}")
        
        podiums = r.get("Podiums")
        if podiums:
            lines.append(f"  - Podiums: {podiums}")
        
        poles = r.get("Pole positions") or r.get("Poles")
        if poles:
            lines.append(f"  - Poles: {poles}")
        
        fastest = r.get("Fastest laps")
        if fastest:
            lines.append(f"  - Meilleurs tours: {fastest}")
        
        points = r.get("Points") or r.get("Career points")
        if points:
            lines.append(f"  - Points: {points}")
        
        seasons = r.get("Seasons") or r.get("Active years")
        if seasons:
            lines.append(f"  - Saisons: {seasons}")
        
        year = r.get("Year") or r.get("Season")
        if year:
            lines.append(f"  - Annee: {year}")
        
        pos = r.get("Position") or r.get("Pos")
        if pos:
            lines.append(f"  - Position: {pos}")
        
        team = r.get("Team") or r.get("Constructor")
        if team and name != team:
            lines.append(f"  - Equipe: {team}")
        
        lines.append("")
    
    return "\n".join(lines)
