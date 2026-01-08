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

# Import Knowledge Base
from backend.knowledge_base import get_knowledge_base


# Configuration Ollama (Windows-first)
# -----------------------------------
OLLAMA_PATHS = [
    r"C:\\Users\\cococ\\AppData\\Local\\Programs\\Ollama\\ollama.exe",  # chemin par défaut
    r"C:\\Program Files\\Ollama\\ollama.exe",  # alternative
    "ollama",  # fallback : PATH
]
OLLAMA_MODEL = "llama2:3b"  # Llama 3.2 3B pour performances optimales
OLLAMA_TIMEOUT = 300  # secondes

# Cache Ergast (5 min TTL)
_ergast_cache: Dict = {}
_ergast_cache_time = 0
ERGAST_CACHE_TTL = 300  # 5 minutes


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
    "https://www.actuf1.com/",  # Actualités F1
    "https://www.standf1.com/",  # Classements/Stats
]

# Sources complémentaires (officiel FIA)
FIA_SOURCES = [
    "https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship",  # Calendrier 2025
    "https://www.fia.com/regulation/category/110",  # Régulations
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


def scrape_fia_calendar() -> str:
    """Scrape FIA - Calendrier 2025."""
    try:
        html = fetch_url("https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship", timeout=10)
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
    except Exception as e:
        print(f"[WARN] FIA Calendar scraping failed: {e}")
        return ""


def scrape_fia_regulations() -> str:
    """Scrape FIA - Régulations F1."""
    try:
        html = fetch_url("https://www.fia.com/regulation/category/110", timeout=10)
        soup = BeautifulSoup(html, "html.parser")
        # Extraire les régulations
        regs = soup.find_all("a", class_=lambda x: x and "regulation" in x.lower())[:5]
        if regs:
            return " | ".join([reg.get_text().strip()[:80] for reg in regs])[:600]
        return extract_main_text(html, 600)
    except Exception as e:
        print(f"[WARN] FIA Regulations scraping failed: {e}")
        return ""


def get_news_summaries(limit: int = 1) -> List[NewsItem]:
    """Récupère et valide jusqu'à `limit` sources récentes (mix de sources avec liens)."""
    summaries: List[NewsItem] = []
    
    # Mix de scrapers génériques et spécialisés avec URLs complètes
    sources = [
        ("https://www.motorsport.com/f1/news/", extract_main_text, "https://www.motorsport.com/f1/news/"),
        ("https://www.autosport.com/f1/news/", extract_main_text, "https://www.autosport.com/f1/news/"),
        ("ActuF1 (Spécialisé)", scrape_actuf1, "https://www.actuf1.com/"),
        ("StandF1 (Classements)", scrape_standf1, "https://www.standf1.com/"),
        ("FIA Calendrier 2025", scrape_fia_calendar, "https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship"),
        ("FIA Régulations", scrape_fia_regulations, "https://www.fia.com/regulation/category/110"),
    ]
    
    for source_name, scraper, source_url in sources:
        if len(summaries) >= limit:
            break
        try:
            print(f"[INFO] Scraping {source_name}")
            
            if scraper == extract_main_text:
                # Scraper générique
                html = fetch_url(source_url, timeout=8)
                text = extract_main_text(html, max_chars=600)
            else:
                # Scraper spécialisé
                text = scraper()
            
            if text and len(text.strip()) >= 50:
                try:
                    # Ajouter le lien à la source pour le LLM
                    source_with_link = f"{source_name} - [Lien]({source_url})"
                    item = NewsItem(source=source_with_link, content=text)
                    summaries.append(item)
                except ValidationError as ve:
                    print(f"[WARN] NewsItem invalide pour {source_name}: {len(text)} chars")
                    continue
        except Exception as exc:
            print(f"[WARN] Impossible de récupérer {source_name}: {exc}")
    
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


def build_prompt(news_summary: str, ergast_block: str, user_question: str) -> str:
    # Borner les blocs pour éviter un prompt trop volumineux
    news_summary = _clamp(news_summary, 1600)
    ergast_block = _clamp(ergast_block, 800)
    
    # Ajouter contexte de la knowledge base
    kb = get_knowledge_base()
    # Ne prendre que le document le plus pertinent (évite de mélanger plusieurs fichiers)
    kb_results = kb.search(user_question, top_k=1)
    kb_context = "\n".join([f"📚 {doc[:300]}..." for doc in kb_results]) if kb_results else "Aucune connaissance supplémentaire."
    kb_context = _clamp(kb_context, 600)
    
    prompt = f"""
🏎️ **Tu es un expert F1 passionné. Réponds TOUJOURS en FRANÇAIS, concis et factuel.**

**Instructions CRUCIALES - RESPECTER L'ORDRE** :

1️⃣ **LANGAGE** : Réponds EN FRANÇAIS. Jamais en anglais. Toujours français!

2️⃣ **KNOWLEDGE BASE EST PRIORITAIRE** :
   - Si la KB contient une réponse directe → Utilise-la et cite la KB
   - Si la question parle de "Yves" ou "Epitech" → Cherche dans la KB!
   - La KB contient des infos perso, contactables, des profils → Utilise-les!

3️⃣ **Contenu à inclure** :
   ✅ Actualités F1 vérifiées si pertinent
   ✅ Stats officielles Ergast si dispo
   ✅ Infos de la **KNOWLEDGE BASE** en priorité
   ✅ **TOUJOURS citer sources avec liens** : [Texte](url)

4️⃣ **Qualité réponse** :
   ✅ Du **gras** pour infos clés
   ✅ Emojis F1 appropriés (🏎️ 🏁 🏆 🏅)
   ✅ Répondre directement - structuré en puces
   ✅ Si incertain → dire clairement "Je n'ai pas confirmé"
   ✅ Jamais inventer - priorité vérité!

[🏁 ACTUALITÉS RÉCENTES avec SOURCES]
{news_summary}

[📊 STATS OFFICIELLES - Ergast API]
{ergast_block}

[📚 KNOWLEDGE BASE (informations fiables - utiliser si pertinent!)]
{kb_context}

[❓ QUESTION UTILISATEUR]
{user_question}

**EXÉCUTION** :
1. Vérifier si la KB répond directement
2. Sinon, combiner actualités + stats + KB
3. Répondre EN FRANÇAIS avec sources et gras
4. Jamais utiliser l'anglais!
"""
    prompt = textwrap.dedent(prompt).strip()
    return _clamp(prompt, 4500)


# -----------------------------------
# Appel Ollama
# -----------------------------------
def call_ollama(prompt: str) -> str:
    try:
        cmd = [OLLAMA_PATH, "run", OLLAMA_MODEL, prompt]
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
    ql = q.lower()
    keywords = [
        "f1", "formula 1", "formule 1", "grand prix", "gp",
        "verstappen", "hamilton", "leclerc", "alonso", "perez",
        "mercedes", "ferrari", "red bull", "mclaren", "aston martin",
    ]
    return any(k in ql for k in keywords)


def answer_f1_question(user_question: str) -> str:
    try:
        # 1) Vérifier si c'est une question F1
        is_f1 = _is_f1_question(user_question)
        
        # 2) Si NON-F1, d'abord chercher dans la KB
        if not is_f1:
            kb = get_knowledge_base()
            kb_results = kb.search(user_question, top_k=1)
            if kb_results:
                return "📚 " + _clamp(kb_results[0], 900)
            
            # 2b) Si KB vide, chercher via Ollama sur les sources disponibles
            news_items = get_news_summaries(limit=3)
            if news_items:
                news_summary = "\n\n".join([f"🔗 **Source** : {item.source}\n{item.content}" for item in news_items])
                prompt = build_prompt(news_summary, "", user_question)
                response = call_ollama(prompt)
                try:
                    if _is_probably_english(response):
                        response = _translate_to_french(response)
                except Exception as _:
                    pass
                return response
            
            return "ℹ️ Aucune donnée trouvée pour cette question."
        
        # 3) Pour les questions F1: actualités + stats Ergast
        news_items = get_news_summaries(limit=1)
        results, standings = _get_ergast_data()
        
        news_items = get_news_summaries(limit=1)
        results, standings = _get_ergast_data()
        
        news_summary = (
            "\n\n".join([f"🔗 **Source** : {item.source}\n{item.content}" for item in news_items])
            if news_items
            else "❌ Aucune actualité récupérée."
        )

        # 4) Stats Ergast
        ergast_block = format_ergast_data(results, standings)

        # 5) Build prompt
        prompt = build_prompt(news_summary, ergast_block, user_question)

        # 6) Call Ollama
        response = call_ollama(prompt)
        
        # 7) Forcer le FRANÇAIS si la sortie semble anglaise
        try:
            if _is_probably_english(response):
                response = _translate_to_french(response)
        except Exception as _:
            pass

        # 8) Fallback KB si erreur Ollama (timeout, introuvable, etc.)
        low = response.lower()
        if low.startswith("[erreur") or "ollama a dépassé le timeout" in low or "ollama introuvable" in low:
            kb = get_knowledge_base()
            kb_results = kb.search(user_question, top_k=1)
            if kb_results:
                kb_answer = "📚 Réponse issue de la base de connaissances (document pertinent) :\n\n" + _clamp(kb_results[0], 900)
                return kb_answer
            # Si pas de KB pertinente, retourner l'erreur existante
            return response

        # 9) Ajouter emojis aux réponses pertinentes
        if "erreur" in low:
            response = f"❌ {response}"
        elif is_f1:
            response = f"🏎️ {response}"
        
        return response
    except Exception as exc:
        print(f"[ERROR] answer_f1_question: {exc}")
        return f"❌ **[ERREUR]** Impossible de traiter la demande: {exc}"


if __name__ == "__main__":
    q = "Quelles sont les dernières infos et qui mène le championnat ?"
    print("Question :", q)
    print("Génération en cours...\n")
    print(answer_f1_question(q))
