"""
Backend FastAPI - Chatbot Ollama Local (Multiplateforme)
Reçoit les messages utilisateur, appelle Ollama (Llama 3.2 3B) et retourne les réponses.
Communication frontend ↔ backend ↔ Ollama fonctionnelle.
Compatible: Windows, macOS, Linux
"""

import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Literal, Dict
import os
from pathlib import Path
import subprocess
import threading
import sys
import socket

from backend.f1_bot import answer_f1_question, perform_background_learning, get_news_summaries, fetch_url, extract_main_text
from backend.knowledge_base import get_knowledge_base, reload_knowledge_base, KnowledgeDoc
from backend.optimized_prompts import ConversationMemory
from backend.input_validator import sanitize_user_input
from backend.standings_utils import get_standf1_standings_summary, get_standf1_constructors_summary
from bs4 import BeautifulSoup
import re

# Import logger structuré
from backend.logger import get_logger
logger = get_logger(__name__)

# Configuration
app = FastAPI(title="Chatbot Ollama Local (Multiplateforme)")

# Déterminer les chemins relatifs au répertoire du projet
BASE_DIR = Path(__file__).parent.absolute()
POSSIBLE_TEMPLATES = BASE_DIR / "frontend" / "templates"
if POSSIBLE_TEMPLATES.is_dir():
    TEMPLATES_DIR = POSSIBLE_TEMPLATES
else:
    TEMPLATES_DIR = BASE_DIR / "frontend"

STATIC_DIR = BASE_DIR / "frontend" / "static"

# Configuration Ollama (multiplateforme)
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
    # Fallback
    "ollama",
]

# Déterminer le chemin valide vers ollama
OLLAMA_PATH = None
for path in OLLAMA_PATHS:
    if path == "ollama":
        OLLAMA_PATH = "ollama"
        print(f"OK Ollama: utilisant PATH variable")
        break
    elif isinstance(path, Path) and path.exists():
        OLLAMA_PATH = str(path)
        print(f"OK Ollama trouve : {OLLAMA_PATH}")
        break

if OLLAMA_PATH is None:
    print("ATTENTION: Ollama.exe non trouve aux chemins connus")
    print("   Chemins vérifiés :")
    for p in OLLAMA_PATHS[:-1]:
        print(f"   - {p}")
    print("   Veuillez ajouter le chemin correct dans OLLAMA_PATHS")
    OLLAMA_PATH = OLLAMA_PATHS[0]  # Utiliser le chemin par défaut de toute façon

# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# URL API Ollama (Windows par défaut)
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"  # Qwen 2.5 3B - Rapide et performant

# MODELS
class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatMessage(BaseModel):
    message: str
    conversation_id: str = "default"

class ChatResponse(BaseModel):
    user_message: str
    bot_response: str
    history: List[HistoryItem]
    sources: List[str] = []  # Liste des sources utilisées

# HISTORIQUE & MÉMOIRE CONVERSATIONNELLE
# Dictionnaire des historiques par conversation_id (sans authentification)
sessions_history: Dict[str, List[HistoryItem]] = {}
MAX_HISTORY = 6  # 3 derniers échanges max

def get_history_for_session(conv_id: str) -> List[HistoryItem]:
    if conv_id not in sessions_history:
        sessions_history[conv_id] = []
    return sessions_history[conv_id]

# Mémoire conversationnelle persistante
conversation_memory = ConversationMemory(max_history=10, memory_file="conversation_memory.json")


# OLLAMA API CALL
def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False  # Streaming désactivé pour compatibilité Windows
    }

    try:
        response = httpx.post(OLLAMA_URL, json=payload, timeout=10, follow_redirects=True)  # Réduit de 15s→10s
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except httpx.TimeoutException:
        return "[ERREUR] Timeout Ollama"
    except Exception as e:
        return f"[ERREUR Ollama] {e}"

# ROUTES
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Chatbot F1"}
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(chat_msg: ChatMessage, background_tasks: BackgroundTasks):
    user_message = chat_msg.message.strip()
    conv_id = chat_msg.conversation_id
    
    if not user_message:
        return JSONResponse(status_code=400, content={"detail": "Message vide"})

    # SANITIZATION - Protection contre injection prompts (Niveau 1)
    try:
        user_message, is_safe = sanitize_user_input(user_message)
        logger.info(f"Input sanitized: safe={is_safe}, length={len(user_message)}")
    except ValueError as e:
        logger.warning(f"Input blocked: {e}")
        return JSONResponse(status_code=400, content={"detail": str(e)})

    # GESTION DES COMMANDES SPÉCIALES
    if user_message.startswith("/learn"):
        from backend.long_term_memory import long_term_memory
        bot_response = long_term_memory.force_learn(user_message)

        # On retourne une réponse courte sans passer par le LLM
        return ChatResponse(
            user_message=user_message,
            bot_response=bot_response,
            history=get_history_for_session(conv_id),
            sources=[]
        )

    # Récupérer l'historique spécifique à cette session
    current_history = get_history_for_session(conv_id)

    try:
        # Appeler le pipeline F1 (news + stats + Ollama) avec historique
        bot_response, sources = answer_f1_question(user_message, history=current_history, rag_only=None, username=None)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"Erreur backend: {exc}"})

    # Historique en mémoire (session)
    current_history.append(HistoryItem(role="user", content=user_message))
    current_history.append(HistoryItem(role="assistant", content=bot_response))
    if len(current_history) > MAX_HISTORY:
        sessions_history[conv_id] = current_history[-MAX_HISTORY:]

    # Mémoire persistante (fichier JSON global pour apprentissage)
    conversation_memory.add_to_memory(user_message, bot_response)

    # Lancer l'apprentissage automatique en arrière-plan
    background_tasks.add_task(perform_background_learning, user_message, bot_response)

    return ChatResponse(
        user_message=user_message,
        bot_response=bot_response,
        history=current_history,
        sources=sources if sources else []
    )

@app.get("/history")
async def get_history(conversation_id: str = "default"):
    return {"history": get_history_for_session(conversation_id)}

@app.post("/clear_history")
async def clear_history(conversation_id: str = "default"):
    if conversation_id in sessions_history:
        sessions_history[conversation_id].clear()
    
    return {"message": f"Historique '{conversation_id}' effacé", "history": []}

# Knowledge Base Endpoints
@app.get("/kb/docs")
async def get_kb_documents():
    kb = get_knowledge_base()
    docs = kb.get_all_docs()
    return {
        "total": len(docs),
        "documents": [
            {"id": doc.doc_id, "title": doc.title, "category": doc.category, "preview": doc.content[:150]}
            for doc in docs
        ]
    }

@app.get("/kb/search")
async def search_kb(q: str):
    if not q or len(q) < 3:
        return {"error": "Query trop court (min 3 caractères)", "results": []}
    kb = get_knowledge_base()
    results = kb.search(q, top_k=3)
    return {"query": q, "results": [{"content": r[:200]+"..." if len(r)>200 else r} for r in results]}

class KBDocumentRequest(BaseModel):
    doc_id: str
    title: str
    content: str
    category: str = "custom"

@app.post("/kb/add")
async def add_kb_document(doc: KBDocumentRequest):
    try:
        kb = get_knowledge_base()
        new_doc = KnowledgeDoc(doc_id=doc.doc_id, title=doc.title, content=doc.content, category=doc.category)
        kb.add_document(new_doc)
        return {"status": "success", "message": f"Document '{doc.title}' ajouté à la KB", "doc_id": doc.doc_id}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": f"Erreur lors de l'ajout: {str(e)}"})

@app.post("/kb/reload")
async def reload_kb():
    """Recharger la knowledge base (vide le cache et recharge depuis les fichiers)"""
    try:
        kb = reload_knowledge_base()
        return {
            "status": "success",
            "message": "Knowledge base rechargée avec succès",
            "docs_count": len(kb.docs)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Erreur lors du rechargement: {str(e)}"})

@app.get("/memory/summary")
async def get_memory_summary():
    from backend.long_term_memory import long_term_memory
    return long_term_memory.get_learning_summary()


@app.get("/next_race_countdown")
async def get_next_race_countdown():
    """Récupère le compte à rebours du prochain GP depuis plusieurs sources (Aurupteur, Ergast API)"""
    from datetime import datetime, timezone
    import json

    # Essayer d'abord l'API Ergast (source fiable officielle)
    try:
        response = httpx.get("https://ergast.com/api/f1/current/next.json", timeout=3)
        if response.status_code == 200:
            data = response.json()
            if "MRData" in data and "RaceTable" in data["MRData"] and "Races" in data["MRData"]["RaceTable"]:
                races = data["MRData"]["RaceTable"]["Races"]
                if races and len(races) > 0:
                    next_race = races[0]
                    race_name = next_race.get("raceName", "")
                    race_date = next_race.get("date", "")
                    race_time = next_race.get("time", "00:00:00Z")
                    circuit_name = next_race.get("Circuit", {}).get("circuitName", "")

                    # Calculer le temps restant
                    if race_date:
                        race_datetime_str = f"{race_date}T{race_time}"
                        race_datetime = datetime.fromisoformat(race_datetime_str.replace("Z", "+00:00"))
                        now = datetime.now(timezone.utc)
                        time_diff = race_datetime - now

                        days = time_diff.days
                        hours = time_diff.seconds // 3600
                        minutes = (time_diff.seconds % 3600) // 60

                        # Formater le compte à rebours
                        if days > 0:
                            countdown_text = f"Dans {days} jour{'s' if days > 1 else ''}, {hours}h{minutes:02d}min"
                        elif hours > 0:
                            countdown_text = f"Dans {hours}h{minutes:02d}min"
                        else:
                            countdown_text = f"Dans {minutes} minute{'s' if minutes > 1 else ''}"

                        return {
                            "countdown": countdown_text,
                            "race_name": race_name,
                            "circuit": circuit_name,
                            "date": race_date,
                            "source": "Ergast API (officiel)"
                        }
    except Exception as e:
        logger.warning(f"Ergast API indisponible: {e}")

    # Fallback: Aurupteur (scraping)
    try:
        html = fetch_url("https://aurupteur.com/", timeout=3)
        if not html:
            return {"countdown": None, "race_name": None, "source": None}

        soup = BeautifulSoup(html, "html.parser")

        # Chercher le compte à rebours (plusieurs stratégies)
        countdown_text = None
        race_name = None

        # Stratégie 1: Chercher des éléments avec "countdown" ou "prochain"
        countdown_divs = soup.find_all(["div", "span", "p"], class_=lambda x: x and ("countdown" in x.lower() or "prochain" in x.lower() if x else False))
        if countdown_divs:
            for div in countdown_divs:
                text = div.get_text(strip=True)
                if any(word in text.lower() for word in ["prochain", "grand prix", "gp", "jour", "heure"]):
                    countdown_text = text
                    break

        # Stratégie 2: Chercher dans le texte principal
        if not countdown_text:
            main_content = soup.find("main") or soup.find("body")
            if main_content:
                text = main_content.get_text()
                # Regex pour trouver "X jours Y heures" ou "Prochain GP"
                match = re.search(r'(Prochain.*?Grand Prix.*?:\s*.*?(?:\d+\s*jours?.*?\d+\s*heures?)|(\d+\s*jours?\s*\d+\s*heures?))', text, re.IGNORECASE)
                if match:
                    countdown_text = match.group(0)

        # Chercher le nom de la course
        if countdown_text:
            race_match = re.search(r'Grand Prix\s+(?:de\s+)?([A-Za-zÀ-ÿ\s]+)', countdown_text, re.IGNORECASE)
            if race_match:
                race_name = race_match.group(1).strip()

        return {
            "countdown": countdown_text,
            "race_name": race_name,
            "source": "Aurupteur.com"
        }
    except Exception as e:
        logger.warning(f"Erreur récupération countdown: {e}")
        return {"countdown": None, "race_name": None, "source": None}


# Health check
@app.get("/health")
async def health_check():
    try:
        # Tester Ollama via API minimal
        r = httpx.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": "Ping", "stream": False}, timeout=5, follow_redirects=True)
        ollama_ok = r.status_code == 200
    except Exception:
        ollama_ok = False
    kb = get_knowledge_base()
    return {
        "status": "ok",
        "backend": "FastAPI + Ollama + Knowledge Base",
        "ollama_available": ollama_ok,
        "model": OLLAMA_MODEL,
        "knowledge_base": {"available": True, "documents_count": len(kb.docs)}
    }

@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools_silence():
    return {}

# MAIN
if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("Chatbot F1 - FASTAPI")
    # Paramètres serveur via variables d'environnement
    HOST = os.environ.get("HOST", "127.0.0.1")
    PORT = int(os.environ.get("PORT", "8001"))
    print(f"URL: http://{HOST}:{PORT}")
    print(f"Modele : {OLLAMA_MODEL}")
    print("=" * 60)

    # Disable automatic reload by default to avoid infinite restart loops
    dev_reload = os.environ.get("DEV_RELOAD", "0").lower() in ("1", "true", "yes")
    print(f"Reload enabled: {dev_reload}")

    # Vérifier que le port est disponible, sinon fallback sur 8002
    def _port_available(host: str, port: int) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.close()
            return True
        except OSError:
            return False

    if not _port_available(HOST, PORT):
        alt = 8002 if PORT != 8002 else 8003
        logger.warning(f"Port {PORT} indisponible. Bascule sur {alt}.")
        PORT = alt

    def launch_auto_train():
        """Lancer le script auto_train.py dans un thread séparé."""
        AUTO_TRAIN_ENABLED = os.environ.get("AUTO_TRAIN", "0").lower() in ("1", "true", "yes")
        script_path = BASE_DIR / "backend" / "auto_train.py"
        if not AUTO_TRAIN_ENABLED:
            logger.info("auto_train désactivé (AUTO_TRAIN=0).")
            return
        if not script_path.exists():
            logger.warning(f"auto_train.py introuvable: {script_path}")
            return

        def run_script():
            try:
                subprocess.run([sys.executable, str(script_path)], check=False)
            except Exception as e:
                logger.warning(f"auto_train erreur: {e}")

        thread = threading.Thread(target=run_script, daemon=True)
        thread.start()

    # Lancer auto_train.py au démarrage si activé et présent
    launch_auto_train()

    # PRÉ-CHARGEMENT DU CACHE au démarrage (optimisation vitesse première requête)
    def preload_cache():
        """Pré-charge les données fréquentes en cache pour accélérer les premières requêtes."""
        try:
            logger.info("🚀 Pré-chargement du cache...")
            # 1. Pré-charger knowledge base
            kb = get_knowledge_base()
            logger.info(f"✅ KB chargée: {len(kb.docs)} documents")

            # 2. Pré-charger classements (en background)
            def load_standings():
                try:
                    get_standf1_standings_summary(top_n=10)
                    get_standf1_constructors_summary(top_n=10)
                    logger.info("✅ Classements pré-chargés")
                except Exception as e:
                    logger.warning(f"⚠️ Classements non disponibles: {e}")

            # 3. Pré-charger actualités (en background)
            def load_news():
                try:
                    get_news_summaries(limit=1)
                    logger.info("✅ Actualités pré-chargées")
                except Exception as e:
                    logger.warning(f"⚠️ Actualités non disponibles: {e}")

            # Lancer en threads séparés pour ne pas bloquer le démarrage
            threading.Thread(target=load_standings, daemon=True).start()
            threading.Thread(target=load_news, daemon=True).start()

            logger.info("🎯 Cache pré-chargé avec succès")
        except Exception as e:
            logger.warning(f"⚠️ Erreur pré-chargement cache: {e}")

    preload_cache()

    uvicorn.run("app:app", host=HOST, port=PORT, reload=dev_reload)
