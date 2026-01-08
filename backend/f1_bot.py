from __future__ import annotations
import asyncio
import os
import sys
import textwrap
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError


# -----------------------------------
# Configuration Ollama (Windows-first)
# -----------------------------------
OLLAMA_PATHS = [
    r"C:\\Users\\cococ\\AppData\\Local\\Programs\\Ollama\\ollama.exe",  # chemin par défaut
    r"C:\\Program Files\\Ollama\\ollama.exe",  # alternative
    "ollama",  # fallback : PATH
]
OLLAMA_MODEL = "llama2"
OLLAMA_FALLBACK_MODEL = "mistral"  # modèle rapide en fallback
OLLAMA_TIMEOUT = 300  # secondes
OLLAMA_SLOW_THRESHOLD = 90  # Si > 90s, basculer sur mistral

# Cache Ergast (5 min TTL)
_ergast_cache: Dict = {}
_ergast_cache_time = 0
ERGAST_CACHE_TTL = 300  # 5 minutes

# Mémorisation du modèle rapide pour la session
_preferred_model = OLLAMA_MODEL
_model_decided = False


def resolve_ollama_path() -> str:
    """Retourne un chemin valide vers ollama.exe ou 'ollama' (PATH)."""
    for p in OLLAMA_PATHS:
        if p == "ollama":
            return p
        if Path(p).exists():
            return p
    return OLLAMA_PATHS[0]


OLLAMA_PATH = resolve_ollama_path()


# -----------------------------------
# Modèles Pydantic (validation des données)
# -----------------------------------

class NewsItem(BaseModel):
    source: str
    content: str = Field(min_length=50, max_length=1500)


class ErgastTop3Result(BaseModel):
    position: str
    givenName: str
    familyName: str
    constructor: str
    points: str


class ErgastDriverStanding(BaseModel):
    position: str
    givenName: str
    familyName: str
    points: str
    constructor: str


class ErgastSummary(BaseModel):
    raceName: str
    circuitName: str
    date: str
    top3: List[ErgastTop3Result]
    driverTop5: List[ErgastDriverStanding]


# -----------------------------------
# Sources d'actualités F1 (pages récentes)
# -----------------------------------
NEWS_SOURCES = [
    "https://www.motorsport.com/f1/news/",
    "https://www.autosport.com/f1/news/",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# -----------------------------------
# Scraping helpers
# -----------------------------------
def fetch_url(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=8)
    resp.raise_for_status()
    return resp.text


def extract_main_text(html: str, max_chars: int = 1500) -> str:
    """Nettoie le HTML, extrait le texte principal, tronque à max_chars."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(
        ["script", "style", "noscript", "header", "footer", "form", "svg", "nav", "aside"]
    ):
        tag.decompose()

    # privilégier les paragraphes
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    text = " ".join(paragraphs)
    text = " ".join(text.split())  # normaliser espaces

    # Sécuriser la plage 1000–1500 caractères
    upper = max(1000, min(max_chars, 1500))
    return text[:upper]


def get_news_summaries(limit: int = 1) -> List[NewsItem]:
    """Récupère et valide jusqu'à `limit` sources récentes (timeouts courts)."""
    summaries: List[NewsItem] = []
    for url in NEWS_SOURCES:
        if len(summaries) >= limit:
            break
        try:
            print(f"[INFO] Fetch {url}")
            html = fetch_url(url)
            text = extract_main_text(html, max_chars=600)
            try:
                item = NewsItem(source=url, content=text)
                summaries.append(item)
            except ValidationError as ve:
                print(f"[WARN] NewsItem invalide pour {url}: {ve.errors()} ({len(text)} chars)")
                continue
        except Exception as exc:  # pragma: no cover - robustesse réseau
            print(f"[WARN] Impossible de récupérer {url}: {exc}")
    if not summaries:
        summaries.append(NewsItem(source="fallback", content="Aucune actualité récupérée (sources inaccessibles)."))
    return summaries[:limit]


# -----------------------------------
# Ergast API (dernier GP + standings)
# -----------------------------------
ERGAST_BASE = "http://ergast.com/api/f1"


def get_last_race_results() -> Dict:
    url = f"{ERGAST_BASE}/current/last/results.json"
    try:
        return requests.get(url, timeout=8).json()
    except Exception as exc:  # pragma: no cover - réseau
        print(f"[WARN] Ergast results error: {exc}")
        return {}


def get_current_standings() -> Dict:
    url = f"{ERGAST_BASE}/current/driverStandings.json"
    try:
        return requests.get(url, timeout=8).json()
    except Exception as exc:  # pragma: no cover - réseau
        print(f"[WARN] Ergast standings error: {exc}")
        return {}


def _get_ergast_data() -> Tuple[Dict, Dict]:
    """Récupère ou retourne du cache Ergast (5 min TTL)."""
    global _ergast_cache, _ergast_cache_time
    now = time.time()
    if _ergast_cache and (now - _ergast_cache_time) < ERGAST_CACHE_TTL:
        print("[INFO] Cache Ergast utilisé")
        return _ergast_cache["results"], _ergast_cache["standings"]
    
    print("[INFO] Fetch Ergast (résultats + standings)...")
    results = get_last_race_results()
    standings = get_current_standings()
    
    _ergast_cache = {"results": results, "standings": standings}
    _ergast_cache_time = now
    return results, standings


def _parse_ergast(results: Dict, standings: Dict) -> ErgastSummary | None:
    """Construit une ErgastSummary validée. Retourne None si invalide."""
    try:
        race = results["MRData"]["RaceTable"]["Races"][0]
        top3_models: List[ErgastTop3Result] = []
        for r in race.get("Results", [])[:3]:
            top3_models.append(
                ErgastTop3Result(
                    position=str(r.get("position", "")),
                    givenName=str(r.get("Driver", {}).get("givenName", "")),
                    familyName=str(r.get("Driver", {}).get("familyName", "")),
                    constructor=str(r.get("Constructor", {}).get("name", "")),
                    points=str(r.get("points", "")),
                )
            )

        standings_list = (
            standings
            .get("MRData", {})
            .get("StandingsTable", {})
            .get("StandingsLists", [{}])[0]
            .get("DriverStandings", [])
        )[:5]
        top5_models: List[ErgastDriverStanding] = []
        for s in standings_list:
            drv = s.get("Driver", {})
            cons = s.get("Constructors", [{}])[0]
            top5_models.append(
                ErgastDriverStanding(
                    position=str(s.get("position", "")),
                    givenName=str(drv.get("givenName", "")),
                    familyName=str(drv.get("familyName", "")),
                    points=str(s.get("points", "")),
                    constructor=str(cons.get("name", "")),
                )
            )

        summary = ErgastSummary(
            raceName=str(race.get("raceName", "")),
            circuitName=str(race.get("Circuit", {}).get("circuitName", "")),
            date=str(race.get("date", "")),
            top3=top3_models,
            driverTop5=top5_models,
        )
        return summary
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] Parse Ergast invalide: {exc}")
        return None


def format_ergast_data(results: Dict, standings: Dict) -> str:
    summary = _parse_ergast(results, standings)
    if not summary:
        return "Stats indisponibles (donnée Ergast manquante)"
    block = [
        f"Dernier Grand Prix : {summary.raceName} ({summary.circuitName}) le {summary.date}",
        "Top 3 course :",
        *[
            f"{r.position}. {r.givenName} {r.familyName} ({r.constructor}) - {r.points} pts"
            for r in summary.top3
        ],
        "Classement pilotes (Top 5) :",
        *[
            f"{s.position}. {s.givenName} {s.familyName} - {s.points} pts ({s.constructor})"
            for s in summary.driverTop5
        ],
    ]
    return "\n".join(block)


# -----------------------------------
# Construction du prompt final
# -----------------------------------
def _clamp(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n[… tronqué …]"


def build_prompt(news_summary: str, ergast_block: str, user_question: str) -> str:
    # Borner les blocs pour éviter un prompt trop volumineux
    news_summary = _clamp(news_summary, 1600)
    ergast_block = _clamp(ergast_block, 800)
    prompt = f"""
    Tu es un expert F1. Réponds en français, concis et factuel.
    Inclure :
    - Résumé des dernières actualités vérifiées
    - Résultats du dernier Grand Prix et classement pilotes
    - Répondre à la question utilisateur
    - Si une info est incertaine ou absente, dis-le clairement.
    - Si tu ne sais pas ou que l'information n'est pas disponible, dis explicitement "Je n'ai pas cette information" et propose des pistes (sources officielles, sites d'actualités). N'invente pas de faits.

    [ACTUALITÉS RÉCENTES]
    {news_summary}

    [STATS OFFICIELLES]
    {ergast_block}

    [QUESTION UTILISATEUR]
    {user_question}

    Donne la réponse directement, structurée en puces courtes si utile.
    """
    prompt = textwrap.dedent(prompt).strip()
    return _clamp(prompt, 4000)


# -----------------------------------
# Appel Ollama
# -----------------------------------
def call_ollama(prompt: str) -> str:
    try:
        global _preferred_model, _model_decided
        model = _preferred_model
        
        cmd = [OLLAMA_PATH, "run", model, prompt]
        print(f"DEBUG: {' '.join(cmd)}")
        
        start_time = time.time()
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=OLLAMA_TIMEOUT,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        elapsed = time.time() - start_time
        
        if proc.returncode == 0:
            response = proc.stdout.strip()
            
            # Détection de lenteur et bascule auto
            if not _model_decided and model == OLLAMA_MODEL and elapsed > OLLAMA_SLOW_THRESHOLD:
                print(f"[WARN] {OLLAMA_MODEL} trop lent ({elapsed:.1f}s > {OLLAMA_SLOW_THRESHOLD}s). Bascule sur {OLLAMA_FALLBACK_MODEL}.")
                _preferred_model = OLLAMA_FALLBACK_MODEL
                _model_decided = True
            
            return response
        
        # Si llama2 échoue et pas encore décidé, essayer mistral
        if model == OLLAMA_MODEL and not _model_decided:
            print(f"[WARN] {OLLAMA_MODEL} a échoué (retcode={proc.returncode}). Fallback sur {OLLAMA_FALLBACK_MODEL}...")
            _preferred_model = OLLAMA_FALLBACK_MODEL
            _model_decided = True
            return call_ollama(prompt)  # Recursif avec mistral
        
        return f"[ERREUR OLLAMA] {proc.stderr.strip() or 'retcode != 0'}"
    except subprocess.TimeoutExpired:
        if _preferred_model == OLLAMA_MODEL and not _model_decided:
            print(f"[WARN] {OLLAMA_MODEL} timeout. Fallback sur {OLLAMA_FALLBACK_MODEL}...")
            _preferred_model = OLLAMA_FALLBACK_MODEL
            _model_decided = True
            return call_ollama(prompt)
        return "[ERREUR] Ollama a dépassé le timeout"
    except FileNotFoundError:
        return f"[ERREUR] Ollama introuvable à {OLLAMA_PATH}"
    except Exception as exc:
        return f"[ERREUR] {type(exc).__name__}: {exc}"


# -----------------------------------
# Pipeline principal : à appeler depuis /chat
# -----------------------------------
def _is_f1_question(q: str) -> bool:
    ql = q.lower()
    keywords = [
        "f1", "formula 1", "formule 1", "grand prix", "gp",
        "verstappen", "hamilton", "leclerc", "alonso", "perez",
        "mercedes", "ferrari", "red bull", "mclaren", "aston martin",
    ]
    return any(k in ql for k in keywords)


def answer_f1_question(user_question: str) -> str:
    try:
        # 1) News scraping + Ergast (seulement pour questions F1)
        is_f1 = _is_f1_question(user_question)
        if is_f1:
            news_items = get_news_summaries(limit=1)
            results, standings = _get_ergast_data()
        else:
            news_items = []
            results, standings = {}, {}
        
        news_summary = (
            "\n\n".join([f"[Source] {item.source}\n{item.content}" for item in news_items])
            if news_items
            else (
                "Aucune actualité récupérée."
                if is_f1
                else "Question hors thématique F1. Actualités F1 non chargées pour réduire la latence."
            )
        )

        # 2) Stats Ergast
        ergast_block = format_ergast_data(results, standings)

        # 3) Build prompt
        prompt = build_prompt(news_summary, ergast_block, user_question)

        # 4) Call Ollama
        return call_ollama(prompt)
    except Exception as exc:
        print(f"[ERROR] answer_f1_question: {exc}")
        return f"[ERREUR] Impossible de traiter la demande: {exc}"


if __name__ == "__main__":
    q = "Quelles sont les dernières infos et qui mène le championnat ?"
    print("Question :", q)
    print("Génération en cours...\n")
    print(answer_f1_question(q))
