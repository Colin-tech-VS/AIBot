from __future__ import annotations
import asyncio
import os
import sys
import textwrap
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import Knowledge Base
from backend.knowledge_base import get_knowledge_base

# Import Optimized Prompt Builder
from backend.optimized_prompts import OptimizedPromptBuilder

# Import Long Term Memory
from backend.long_term_memory import long_term_memory

# Import CSV parser
import csv


# Configuration Ollama (multiplateforme)
# -----------------------------------
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
OLLAMA_MODEL = "llama3.2:3b"  # Llama 3.2 3B pour performances optimales
OLLAMA_TIMEOUT = 300  # secondes

# Mode RAG strict : pas de scraping web général
# Mettre à True pour forcer le RAG (KB + sources structurées) et éviter le scraping
RAG_ONLY = False

# Cache Ergast (5 min TTL)
_ergast_cache: Dict = {}
_ergast_cache_time = 0
ERGAST_CACHE_TTL = 300  # 5 minutes

# Cache news (10 min TTL pour éviter trop d'appels)
_news_cache: List[NewsItem] = []
_news_cache_time = 0
NEWS_CACHE_TTL = 600  # 10 minutes

# Cache recherche web générale (15 min TTL)
_web_search_cache: Dict[str, List[NewsItem]] = {}
_web_search_cache_time: Dict[str, float] = {}
WEB_SEARCH_CACHE_TTL = 900  # 15 minutes


def resolve_ollama_path() -> str:
    """Retourne un chemin valide vers ollama (multiplateforme)."""
    for p in OLLAMA_PATHS:
        if p == "ollama":
            # Vérifier si ollama est accessible via PATH
            cmd = ["which", "ollama"] if sys.platform != "win32" else ["where", "ollama"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return "ollama"
            continue
        if isinstance(p, Path) and p.exists():
            return str(p)
    # Retourner "ollama" en dernier recours (laisse le système le trouver via PATH)
    return "ollama"


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
# Circuits F1 (CSV)
# -----------------------------------

def load_circuits_from_csv() -> List[Dict]:
    """Charge les circuits depuis circuits.csv"""
    circuits = []
    csv_path = Path(__file__).parent.parent / "knowledge_base" / "circuits.csv"
    
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
        print(f"[WARN] Erreur chargement circuits CSV: {e}")
    
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


# -----------------------------------
# News Sources
# -----------------------------------
# Sources recommandées
NEWS_SOURCES = [
    "https://openf1.org/",  # OpenF1 API
    "https://api.jolpi.ca/ergast/f1/",  # Jolpica API
    "https://en.wikipedia.org/w/api.php",  # Wikimedia API
    "https://query.wikidata.org/",  # Wikidata SPARQL
    "https://dumps.wikimedia.org/",  # Wikimedia dumps
    "https://en.wikinews.org/wiki/Category:Formula_One",  # Wikinews EN
    "https://fr.wikinews.org/wiki/Cat%C3%A9gorie:Formule_1",  # Wikinews FR
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
def fetch_url(url: str, timeout: int = 8) -> str:
    """Récupère le contenu HTML d'une URL avec gestion d'erreur."""
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
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


def scrape_actuf1() -> str:
    """Scrape ActuF1 - actualités F1 spécialisées."""
    try:
        html = fetch_url("https://www.actuf1.com/", timeout=8)
        soup = BeautifulSoup(html, "html.parser")
        # Chercher les articles principaux
        articles = soup.find_all("article")[:3]  # Top 3 articles
        contents = []
        for article in articles:
            title = article.find("h2") or article.find("h3")
            summary = article.find("p")
            if title and summary:
                contents.append(f"{title.get_text().strip()}: {summary.get_text().strip()}")
        return " | ".join(contents) if contents else extract_main_text(html, 600)
    except Exception as e:
        print(f"[WARN] ActuF1 scraping failed: {e}")
        return ""


def scrape_standf1() -> str:
    """Scrape StandF1 - classements et statistiques."""
    try:
        html = fetch_url("https://www.standf1.com/", timeout=8)
        soup = BeautifulSoup(html, "html.parser")
        # Extraire les tableaux de classements
        tables = soup.find_all("table")[:1]
        if tables:
            rows = tables[0].find_all("tr")[:10]  # Top 10 lignes
            data = " | ".join([" ".join([td.get_text().strip() for td in tr.find_all(["td", "th"])]) for tr in rows])
            return data[:600] if data else extract_main_text(html, 600)
        return extract_main_text(html, 600)
    except Exception as e:
        print(f"[WARN] StandF1 scraping failed: {e}")
        return ""


def get_news_summaries(limit: int = 1) -> List[NewsItem]:
    """Récupère et valide jusqu'à `limit` sources récentes (mix de sources avec liens).
    
    Optimisations:
    - Cache 10 min pour éviter appels répétés
    - Parallélisation ThreadPool pour récupération simultanée
    - Timeout intelligents (court pour news, long pour FIA)
    """
    global _news_cache, _news_cache_time
    
    # Vérifier le cache
    if _news_cache and time.time() - _news_cache_time < NEWS_CACHE_TTL:
        print(f"[INFO] News depuis cache (TTL {NEWS_CACHE_TTL}s)")
        return _news_cache[:limit]
    
    summaries: List[NewsItem] = []
    
    # Mix de scrapers avec timeouts adaptés
    sources = [
        ("Motorsport.com", extract_main_text, "https://www.motorsport.com/f1/news/", 6),
        ("Autosport.com", extract_main_text, "https://www.autosport.com/f1/news/", 6),
        ("ActuF1", scrape_actuf1, None, 8),
        ("StandF1", scrape_standf1, None, 8),
    ]
    
    # Paralléliser les appels avec ThreadPoolExecutor
    def fetch_source(source_name, scraper, source_url, timeout):
        try:
            print(f"[INFO] Fetching {source_name}")
            if scraper == extract_main_text and source_url:
                html = fetch_url(source_url, timeout=timeout)
                text = extract_main_text(html, max_chars=600)
            else:
                text = scraper()
            
            if text and len(text.strip()) >= 50:
                source_with_link = f"{source_name}" + (f" - [Lien]({source_url})" if source_url else "")
                return NewsItem(source=source_with_link, content=text)
        except Exception as e:
            print(f"[WARN] {source_name} failed: {e}")
        return None
    
    # Exécuter en parallèle avec max 5 workers
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_source, name, scraper, url, timeout): name
            for name, scraper, url, timeout in sources
        }
        
        for future in as_completed(futures):
            if len(summaries) >= limit * 2:  # Collecte 2x pour meilleur choix
                break
            result = future.result()
            if result:
                summaries.append(result)
    
    # Fallback si rien trouvé
    if not summaries:
        summaries.append(NewsItem(source="fallback", content="Aucune actualité récupérée (sources inaccessibles)."))
    
    # Mettre en cache
    _news_cache = summaries
    _news_cache_time = time.time()
    
    return summaries[:limit]


def web_search_general(query: str, limit: int = 3) -> List[NewsItem]:
    """Recherche générale sur internet avec les mots-clés de la question.
    
    Utilise Google/DuckDuckGo scraping pour chercher partout sur internet.
    Optimisations:
    - Cache 15 min par requête
    - Parallélisation
    - Extraction intelligente du contenu
    """
    global _web_search_cache, _web_search_cache_time
    
    # Clé de cache basée sur la requête
    cache_key = query.lower()[:50]
    
    # Vérifier cache
    if cache_key in _web_search_cache and time.time() - _web_search_cache_time.get(cache_key, 0) < WEB_SEARCH_CACHE_TTL:
        print(f"[INFO] Résultats web depuis cache pour: {query[:30]}")
        return _web_search_cache[cache_key][:limit]
    
    results: List[NewsItem] = []
    
    # Essayer plusieurs moteurs de recherche
    search_urls = [
        f"https://www.google.com/search?q={query.replace(' ', '+')}&num=10",
        f"https://duckduckgo.com/?q={query.replace(' ', '+')}&t=h&ia=web",
        f"https://www.bing.com/search?q={query.replace(' ', '+')}&count=10",
    ]
    
    def scrape_search_result(search_url, engine_name):
        try:
            html = fetch_url(search_url, timeout=6)
            soup = BeautifulSoup(html, "html.parser")
            
            items = []
            
            if "google" in engine_name.lower():
                # Google: chercher div.g avec h3
                for div in soup.find_all("div", class_="g")[:5]:
                    h3 = div.find("h3")
                    link = div.find("a", href=True)
                    snippet = div.find("span", class_="st")
                    
                    if h3 and snippet:
                        title = h3.get_text().strip()
                        text = snippet.get_text().strip()
                        url = link["href"] if link else ""
                        if text and len(text) > 50:
                            items.append((title, text[:300], url))
            
            elif "duckduckgo" in engine_name.lower():
                # DuckDuckGo: div.result
                for div in soup.find_all("div", class_="result")[:5]:
                    title_tag = div.find("a", class_="result__url")
                    snippet = div.find("a", class_="result__snippet")
                    
                    if title_tag and snippet:
                        title = title_tag.get_text().strip()
                        text = snippet.get_text().strip()
                        if text and len(text) > 50:
                            items.append((title, text[:300], ""))
            
            elif "bing" in engine_name.lower():
                # Bing: li.b_algo
                for li in soup.find_all("li", class_="b_algo")[:5]:
                    h2 = li.find("h2")
                    p = li.find("p")
                    
                    if h2 and p:
                        title = h2.get_text().strip()
                        text = p.get_text().strip()
                        if text and len(text) > 50:
                            items.append((title, text[:300], ""))
            
            return items
        except Exception as e:
            print(f"[WARN] Recherche {engine_name} échouée: {e}")
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
    
    # Fallback si rien trouvé
    if not results:
        results.append(NewsItem(source="Aucun résultat", content="La recherche n'a retourné aucun résultat pertinent."))
    
    # Mettre en cache
    _web_search_cache[cache_key] = results
    _web_search_cache_time[cache_key] = time.time()
    
    return results[:limit]


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


def get_last_position_result(results: Dict) -> Optional[str]:
    """Retourne le dernier classé du dernier GP depuis la réponse Ergast."""
    try:
        races = results.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        if not races:
            return None
        race = races[0]
        res_list = race.get("Results", [])
        if not res_list:
            return None
        last = res_list[-1]
        driver = last.get("Driver", {})
        constructor = last.get("Constructor", {})
        position = last.get("position", "?")
        status = last.get("status", "")
        name = f"{driver.get('givenName', '')} {driver.get('familyName', '')}".strip()
        team = constructor.get("name", "")
        if name:
            return f"{name} ({team}), position {position}, statut: {status}"
    except Exception:
        return None
    return None


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
        return "Stats indisponibles (donnée Ergast manquante) - [Source: Ergast API](http://ergast.com/api/f1)"
    block = [
        f"🏁 **Dernier Grand Prix** : {summary.raceName} 🏎️",
        f"🏟️ **Circuit** : {summary.circuitName}",
        f"📅 **Date** : {summary.date}",
        f"🔗 **Source** : [Ergast API](http://ergast.com/api/f1)",
        "",
        "🏆 **Top 3 Course** :",
        *[
            f"  {r.position}. 🏅 **{r.givenName} {r.familyName}** ({r.constructor}) - **{r.points}** pts"
            for r in summary.top3
        ],
        "",
        "📊 **Classement Pilotes (Top 5)** :",
        *[
            f"  {s.position}. **{s.givenName} {s.familyName}** - **{s.points}** pts ({s.constructor})"
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


def build_prompt(news_summary: str, ergast_block: str, user_question: str, history_text: str = "") -> str:
    # Borner les blocs pour éviter un prompt trop volumineux
    news_summary = _clamp(news_summary, 1200)
    ergast_block = _clamp(ergast_block, 600)
    history_text = _clamp(history_text, 600)
    
    prompt = f"""Tu es un assistant expert. Réponds EN FRANÇAIS de manière DIRECTE et CONCISE.

INSTRUCTIONS :
1. Répondre directement à la question - pas d'infos inutiles
2. Utiliser les sources fournies si pertinent
3. Si pas assez d'infos: dire "Je n'ai pas trouvé de réponse"
4. Toujours en FRANÇAIS!

CONTEXTE CONVERSATION (si utile) :
{history_text if history_text else "(aucun contexte)"}

SOURCES :
{news_summary if news_summary else "(aucune actualité)"}

{ergast_block if ergast_block else ""}

QUESTION : {user_question}

Réponds maintenant (direct et concis):
"""
    prompt = textwrap.dedent(prompt).strip()
    return _clamp(prompt, 3000)


# -----------------------------------
# Appel Ollama
# -----------------------------------
def call_ollama(prompt: str) -> str:
    try:
        cmd = [OLLAMA_PATH, "run", OLLAMA_MODEL, prompt]
        print(f"DEBUG: {' '.join(cmd)}")
        
        start_time = time.time()
        
        # Configuration multiplateforme
        kwargs = {
            "capture_output": True,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": OLLAMA_TIMEOUT,
            "shell": False,
        }
        # Appliquer creationflags uniquement sur Windows
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        
        proc = subprocess.run(cmd, **kwargs)
        elapsed = time.time() - start_time
        
        if proc.returncode == 0:
            response = proc.stdout.strip()
            return response
        
        return f"[ERREUR OLLAMA] {proc.stderr.strip() or 'retcode != 0'}"
    except subprocess.TimeoutExpired:
        return "[ERREUR] Ollama a dépassé le timeout"
    except FileNotFoundError:
        return f"[ERREUR] Ollama introuvable à {OLLAMA_PATH}"
    except Exception as exc:
        return f"[ERREUR] {type(exc).__name__}: {exc}"


# -----------------------------------
# Pipeline principal : à appeler depuis /chat
# -----------------------------------
def _is_probably_english(text: str) -> bool:
    """Heuristique simple pour détecter une réponse majoritairement en anglais."""
    tl = text.lower()
    eng_tokens = [" the ", " and ", " is ", " are ", " with ", " of ", " to ", " in ", " for "]
    fr_tokens = [" le ", " la ", " les ", " des ", " est ", " et ", " à ", " de ", " un ", " une "]
    eng = sum(tl.count(t) for t in eng_tokens)
    fr = sum(tl.count(t) for t in fr_tokens)
    return eng >= 2 and eng > fr * 1.2


def _translate_to_french(text: str) -> str:
    """Demande à l'LLM une traduction fidèle en français, en conservant le Markdown."""
    prompt = (
        "Tu es un traducteur professionnel. Traduire FIDÈLEMENT en FRANÇAIS, "
        "sans ajouter ni omettre d'information, en conservant le formatage Markdown, les listes et les liens.\n\n"
        "Texte à traduire:\n\n" + text
    )
    return call_ollama(prompt)


def _is_f1_question(q: str) -> bool:
    """Détecte si la question concerne la F1 de manière stricte."""
    ql = q.lower()
    f1_keywords = [
        "f1", "formula 1", "formule 1", "grand prix", "gp",
        "verstappen", "hamilton", "leclerc", "alonso", "perez", "sainz", "norris", "piastri",
        "mercedes", "ferrari", "red bull", "mclaren", "aston martin", "alpine", "williams", "haas", "sauber",
        "circuit", "piste", "champion", "victoire", "course", "pilote", "constructeur",
        "pole position", "podium", "drs", "kers", "qualif", "essai", "essais libres",
        "monza", "spa", "monaco", "silverstone", "imola", "suzuka", "interlagos",
        "gagn", "gagne", "gangé", "perdu", "perd", "classement", "position", "résultat"
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
    # Question générale si présence d'indicateurs généraux
    # On autorise même si il y a des mots F1 pour être plus souple sur la conversation
    return any(ind in ql for ind in general_indicators) or len(ql.split()) < 4


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


def answer_f1_question(user_question: str, history=None, rag_only: Optional[bool] = None) -> str:
    """Entry point for answering questions with long term memory storage."""
    response = _answer_f1_question_internal(user_question, history, rag_only)
    
    # Stocker dans la mémoire long terme
    if response and not response.startswith("❌") and not response.startswith("[ERREUR"):
        long_term_memory.store_conversation(user_question, response)
        
    return response


def _answer_f1_question_internal(user_question: str, history=None, rag_only: Optional[bool] = None) -> str:
    """
    Pipeline optimisé avec cascade de sources stricte:

    QUESTIONS F1:
    1. Chercher dans Knowledge Base (prioritaire)
    2. Si pas de réponse pertinente: OpenF1 API
    3. Si pas de réponse: Jolpica/Ergast API
    4. Si pas de réponse: Wikipedia/Wikidata API
    5. Si pas de réponse: Wikinews
    6. Si toujours rien: "Je n'ai pas trouvé de réponse"

    QUESTIONS GÉNÉRALES (non-F1):
    1. Chercher dans Knowledge Base
    2. Si pas de réponse: "Cette question n'est pas liée à la F1. Je suis spécialisé en F1."

    QUESTIONS HORS SCOPE:
    - Refuser poliment et rediriger vers F1
    """
    try:
        # Nettoyer la question
        user_question = user_question.strip()
        if not user_question:
            return "Veuillez poser une question."

        print(f"[INFO] Question reçue: {user_question}")

        # Récupérer le contexte de la mémoire long terme
        lt_context = long_term_memory.get_relevant_context(user_question)
        if lt_context:
            print("[INFO] Contexte long terme récupéré")

        # CAS SPÉCIAL : Question sur la date du jour
        q_lower = user_question.lower()
        if any(keyword in q_lower for keyword in ["date", "aujourd'hui", "quel jour", "quelle date", "jour sommes"]):
            current_date = OptimizedPromptBuilder.get_current_date()
            return f"On est le **{current_date}** ! 📅 Tu veux savoir ce qui se passe en F1 en ce moment ? 🏎️"

        # CAS SPÉCIAL : Question faisant référence à l'historique
        # Détecte si la question fait référence au contexte/historique (tolérant aux fautes de frappe)
        history_keywords = [
            "première question", "premiere question", "prmeière", "prmeiere", "1ere question", "1ère question",
            "question précédente", "question precedente", "dernière question", "dernier question",
            "avant", "tout à l'heure", "tout a l'heure", "ma question", "mes question",
            "j'ai demandé", "j'ai demande", "jai demandé", "jai demande",
            "conversation", "historique", "contexte",
            "répond", "repond", "répondre à", "repondre a", "répondre a", "reponds",
            "c'était quoi", "cetait quoi", "c'etait quoi", "cétait quoi"
        ]

        if any(keyword in q_lower for keyword in history_keywords):
            if history and len(history) > 0:
                # Formatter l'historique complet pour le LLM
                history_text = _format_history(history)

                # Construire un prompt qui demande au LLM d'analyser l'historique et répondre
                prompt = f"""Tu es un assistant expert F1 intelligent. Analyse l'historique de conversation et réponds de manière naturelle.

HISTORIQUE DE CONVERSATION :
{history_text}

QUESTION ACTUELLE : {user_question}

INSTRUCTIONS :
- Si l'utilisateur demande "ma première question c'était quoi ?" : Identifie la toute première question User dans l'historique et cite-la directement
- Si l'utilisateur demande "réponds à ma première question" : Trouve la première question ET réponds-y maintenant de manière complète
- Si l'utilisateur pose une question contextuelle sur une réponse précédente : Réponds en utilisant le contexte de l'historique
- Si l'utilisateur demande des calculs ou questions générales : Réponds directement
- IMPORTANT : Sois naturel, conversationnel et précis. Ne liste pas bêtement l'historique, COMPRENDS la demande et réponds intelligemment
- Réponds TOUJOURS en français, de manière concise mais complète

Analyse la question et réponds maintenant :"""

                response = call_ollama(prompt)
                if response and not response.startswith("[ERREUR"):
                    return response

            return "On vient de commencer à discuter, j'ai pas encore d'historique ! 😊 C'est quoi ta question sur la F1 ? 🏎️"

        # CAS SPÉCIAL : Réponses contextuelles courtes (oui, non, ok, etc.)
        # Détecte si c'est une réponse courte qui nécessite le contexte précédent
        short_responses = ["oui", "non", "ok", "d'accord", "daccord", "pourquoi", "pourquoi pas",
                          "comment", "quand", "où", "qui", "quoi", "lequel", "laquelle",
                          "raconte", "explique", "dis moi", "dis-moi", "parle moi", "parle-moi"]

        if len(q_lower.split()) <= 3 and any(resp in q_lower for resp in short_responses):
            if history and len(history) > 0:
                # Utiliser le contexte pour répondre intelligemment
                history_text = _format_history(history)

                prompt = f"""Tu es un assistant F1 conversationnel. L'utilisateur répond à ta question précédente avec une réponse courte.

HISTORIQUE DE CONVERSATION :
{history_text}

RÉPONSE COURTE DE L'UTILISATEUR : {user_question}

INSTRUCTIONS :
- Analyse le contexte : qu'est-ce que TU as demandé/proposé juste avant ?
- Si tu as proposé plusieurs sujets (GP, classements, pilote), réponds selon ce que l'utilisateur choisit
- Si l'utilisateur dit "oui", continue sur le sujet que tu as proposé
- Si l'utilisateur dit "non", propose autre chose
- Sois naturel et enthousiaste comme un pote qui parle de F1
- Réponds en français, de manière conversationnelle

Réponds maintenant en continuant la conversation naturellement :"""

                response = call_ollama(prompt)
                if response and not response.startswith("[ERREUR"):
                    return response

        # Déterminer le type de question et formatter l'historique
        rag_mode = RAG_ONLY if rag_only is None else rag_only
        is_f1 = _is_f1_question(user_question)
        is_general = _is_general_question(user_question)
        is_circuit = _is_circuit_question(user_question)
        history_text = _format_history(history)
        print(f"[INFO] F1? {is_f1}, Générale? {is_general}, Circuit? {is_circuit}")

        # ═══════════════════════════════════════════════════════════════
        # CAS 0 : QUESTIONS SUR CIRCUITS - Chercher dans CSV (prioritaire pour circuits)
        # ═══════════════════════════════════════════════════════════════
        if is_circuit:
            print("[INFO] Recherche circuit CSV")
            q_lower = user_question.lower()

            # Cas spécial: "circuit le plus long"
            if 'plus long' in q_lower or 'longest' in q_lower:
                circuit = find_longest_circuit()
                if circuit:
                    return (
                        f"🏎️ Le circuit le plus long en F1 est **{circuit['nom']}** "
                        f"({circuit['lieu']}) avec **{circuit['longueur']}**. {circuit['info']}"
                    )

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
                return f"🏎️ {name} {detail_text}"

        # ═══════════════════════════════════════════════════════════════
        # CAS 1 : QUESTIONS F1 - CASCADE DE SOURCES
        # ═══════════════════════════════════════════════════════════════
        if is_f1:
            print("[INFO] Pipeline F1 avec cascade de sources")

            # ÉTAPE 1: Knowledge Base (prioritaire) - RECHERCHE EXHAUSTIVE
            print("[INFO] Étape 1/5: Recherche Knowledge Base (exhaustive)")
            kb = get_knowledge_base()

            # Rechercher dans TOUS les documents de la KB (pas seulement top 2)
            kb_results = kb.search(user_question, top_k=10)  # Augmenté à 10 pour plus de contexte

            if kb_results and len(kb_results) > 0:
                # Combiner tous les résultats pertinents
                kb_content = "\n\n".join(kb_results)
                print(f"[INFO] KB: {len(kb_results)} résultats trouvés")

                # Ne pas filtrer strictement - laisser le LLM décider
                prompt = OptimizedPromptBuilder.build_f1_question(
                    question=user_question,
                    kb_content=kb_content[:3000],  # Limiter à 3000 chars pour éviter overflow
                    conversation_history=history_text,
                    long_term_context=lt_context
                )
                response = call_ollama(prompt)
                if response and not response.startswith("[ERREUR") and len(response) > 50:
                    print("[INFO] ✓ Réponse trouvée dans Knowledge Base")
                    return response

            print("[INFO] KB non pertinente ou vide, passage à OpenF1 API")

            # ÉTAPE 2: OpenF1 API (données temps réel + historique) - EXHAUSTIF
            print("[INFO] Étape 2/5: Tentative OpenF1 API (exhaustive)")
            openf1_content = []
            try:
                # Récupérer plusieurs endpoints OpenF1
                endpoints = [
                    ("sessions", {"limit": 5}),
                    ("drivers", {"limit": 10}),
                    ("meetings", {"limit": 3}),
                ]

                for endpoint, params in endpoints:
                    try:
                        data = fetch_openf1_data(endpoint, params=params)
                        if data and isinstance(data, list) and len(data) > 0:
                            openf1_content.append(f"OpenF1 {endpoint}: {str(data)[:500]}")
                            print(f"[INFO] ✓ OpenF1 {endpoint}: {len(data)} items")
                    except Exception as e:
                        print(f"[WARN] OpenF1 {endpoint} échouée: {e}")

                if openf1_content:
                    combined_openf1 = "\n".join(openf1_content)
                    prompt = OptimizedPromptBuilder.build_f1_question(
                        question=user_question,
                        news_summary=combined_openf1[:2000],
                        conversation_history=history_text,
                        long_term_context=lt_context
                    )
                    response = call_ollama(prompt)
                    if response and not response.startswith("[ERREUR") and len(response) > 50:
                        return response
            except Exception as e:
                print(f"[WARN] OpenF1 API globale échouée: {e}")

            print("[INFO] OpenF1 non pertinente, passage à Jolpica/Ergast")

            # ÉTAPE 3: Jolpica/Ergast API (historique F1)
            print("[INFO] Étape 3/5: Tentative Jolpica/Ergast API")
            try:
                results, standings_data = _get_ergast_data()
                if results or standings_data:
                    ergast_summary = format_ergast_data(results, standings_data)
                    if ergast_summary and "indisponibles" not in ergast_summary:
                        print("[INFO] ✓ Jolpica/Ergast data disponible")

                        prompt = OptimizedPromptBuilder.build_f1_question(
                            question=user_question,
                            standings=ergast_summary,
                            conversation_history=history_text,
                            long_term_context=lt_context
                        )
                        response = call_ollama(prompt)
                        if response and not response.startswith("[ERREUR"):
                            return response
            except Exception as e:
                print(f"[WARN] Jolpica/Ergast échouée: {e}")

            print("[INFO] Jolpica/Ergast non pertinente, passage à Wikipedia/Wikidata")

            # ÉTAPE 4: Wikipedia/Wikidata API - EXHAUSTIF
            print("[INFO] Étape 4/5: Tentative Wikipedia/Wikidata API (exhaustive)")
            wiki_content = []
            try:
                # Recherche Wikipedia multiple
                search_queries = [
                    f"Formula 1 {user_question}",
                    f"F1 {user_question}",
                    user_question
                ]

                for search_q in search_queries:
                    try:
                        wiki_params = {
                            "list": "search",
                            "srsearch": search_q,
                            "srlimit": 5
                        }
                        wiki_data = fetch_wikimedia_api("query", params=wiki_params)

                        if wiki_data and "query" in wiki_data and "search" in wiki_data["query"]:
                            search_results = wiki_data["query"]["search"]
                            if len(search_results) > 0:
                                for result in search_results[:3]:
                                    wiki_content.append(f"{result['title']}: {result['snippet']}")
                                print(f"[INFO] ✓ Wikipedia: {len(search_results)} résultats pour '{search_q[:30]}...'")
                    except Exception as e:
                        print(f"[WARN] Wikipedia search '{search_q[:30]}' échouée: {e}")

                if wiki_content:
                    wiki_text = " | ".join(wiki_content[:5])  # Top 5 résultats
                    prompt = OptimizedPromptBuilder.build_f1_question(
                        question=user_question,
                        news_summary=wiki_text[:2000],
                        conversation_history=history_text,
                        long_term_context=lt_context
                    )
                    response = call_ollama(prompt)
                    if response and not response.startswith("[ERREUR") and len(response) > 50:
                        return response
            except Exception as e:
                print(f"[WARN] Wikipedia/Wikidata globale échouée: {e}")

            print("[INFO] Wikipedia/Wikidata non pertinente, passage à Wikinews")

            # ÉTAPE 5: Wikinews (actualités F1)
            print("[INFO] Étape 5/5: Tentative Wikinews")
            try:
                wikinews_articles = fetch_wikinews_articles(language="fr")
                if wikinews_articles and len(wikinews_articles) > 0:
                    articles_text = " | ".join([f"{art['title']}" for art in wikinews_articles[:3]])
                    print(f"[INFO] ✓ Wikinews data: {articles_text[:100]}...")

                    prompt = OptimizedPromptBuilder.build_f1_question(
                        question=user_question,
                        news_summary=articles_text,
                        conversation_history=history_text,
                        long_term_context=lt_context
                    )
                    response = call_ollama(prompt)
                    if response and not response.startswith("[ERREUR"):
                        return response
            except Exception as e:
                print(f"[WARN] Wikinews échouée: {e}")

            # Aucune source n'a répondu
            print("[INFO] ✗ Aucune source n'a fourni de réponse")
            return "Désolé, j'ai cherché partout mais je n'ai pas trouvé d'info sur ça... 😕 Tu peux reformuler ta question autrement ? Ou me demander autre chose sur la F1 ? 🏎️"

        # ═══════════════════════════════════════════════════════════════
        # CAS 2 : QUESTIONS GÉNÉRALES (non-F1)
        # ═══════════════════════════════════════════════════════════════
        if is_general:
            print("[INFO] Question générale (non-F1)")

            # Chercher dans KB
            kb = get_knowledge_base()
            kb_results = kb.search(user_question, top_k=2)
            kb_content = "\n".join(kb_results[:2]) if kb_results else ""

            # Prompt pour question générale (permet au LLM d'utiliser ses connaissances)
            prompt = OptimizedPromptBuilder.build_f1_question(
                question=user_question,
                kb_content=kb_content if kb_content and _is_kb_result_relevant(user_question, kb_content) else None,
                conversation_history=history_text,
                long_term_context=lt_context
            )
            
            response = call_ollama(prompt)
            if response and not response.startswith("[ERREUR"):
                return response

            # Fallback si Ollama échoue
            return "Je ne suis pas sûr de comprendre ta question, mais si ça parle de F1, je peux sûrement t'aider ! 🏎️"

        # ═══════════════════════════════════════════════════════════════
        # CAS 3 : AUTRES QUESTIONS (CATCH-ALL INTELLIGENT)
        # ═══════════════════════════════════════════════════════════════
        print("[INFO] Question non catégorisée, utilisation du LLM direct")

        prompt = OptimizedPromptBuilder.build_f1_question(
            question=user_question,
            conversation_history=history_text,
            long_term_context=lt_context
        )
        
        response = call_ollama(prompt)
        if response and not response.startswith("[ERREUR"):
            return response

        # Détecter les salutations pour une réponse de secours chaleureuse
        q_lower_check = user_question.lower()
        if any(salut in q_lower_check for salut in ["bonjour", "salut", "hello", "hi", "hey", "coucou"]):
            return "Salut ! 👋 Content de te voir ! Je suis ton assistant F1 personnel. Tu veux qu'on parle de quoi ? Le dernier GP ? Les classements ? Un pilote en particulier ? 🏎️💨"

        return "Hey ! Je suis spécialisé dans la Formule 1. Si tu as des questions sur les pilotes, les courses, les circuits, les classements... je suis ton expert ! Qu'est-ce qui t'intéresse ? 😊🏁"

    except Exception as exc:
        print(f"[ERROR] answer_f1_question: {exc}")
        import traceback
        traceback.print_exc()
        return "❌ Une erreur s'est produite lors du traitement de votre question. Veuillez réessayer."


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
                        **row
                    })
        except Exception as e:
            print(f"[WARN] Erreur lors du chargement de {csv_file}: {e}")

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


# -----------------------------------
# Scraping helpers for recommended sites
# -----------------------------------

def fetch_openf1_data(endpoint: str, params: Optional[Dict] = None) -> Dict:
    """Fetch data from OpenF1 API."""
    base_url = "https://openf1.org/api"
    try:
        response = requests.get(f"{base_url}/{endpoint}", params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[WARN] OpenF1 API request failed: {e}")
        return {}


def fetch_jolpica_data(endpoint: str, params: Optional[Dict] = None) -> Dict:
    """Fetch data from Jolpica API."""
    base_url = "https://api.jolpi.ca/ergast/f1"
    try:
        response = requests.get(f"{base_url}/{endpoint}", params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[WARN] Jolpica API request failed: {e}")
        return {}


def fetch_wikimedia_api(endpoint: str, params: Optional[Dict] = None) -> Dict:
    """Fetch data from Wikimedia API."""
    base_url = "https://en.wikipedia.org/w/api.php"
    try:
        response = requests.get(base_url, params={**params, "action": "query", "format": "json"}, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[WARN] Wikimedia API request failed: {e}")
        return {}


def fetch_wikidata_sparql(query: str) -> Dict:
    """Fetch data from Wikidata Query Service using SPARQL."""
    base_url = "https://query.wikidata.org/sparql"
    try:
        response = requests.get(base_url, params={"query": query, "format": "json"}, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[WARN] Wikidata SPARQL query failed: {e}")
        return {}


def fetch_wikinews_articles(language: str = "en") -> List[Dict]:
    """Fetch recent Formula 1 articles from Wikinews."""
    base_url = f"https://{language}.wikinews.org/w/api.php"
    try:
        response = requests.get(base_url, params={"action": "query", "list": "categorymembers", "cmtitle": "Category:Formula_One", "format": "json"}, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json().get("query", {}).get("categorymembers", [])
    except requests.exceptions.RequestException as e:
        print(f"[WARN] Wikinews API request failed: {e}")
        return {}
