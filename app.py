"""
Backend FastAPI - Chatbot Ollama Local (Multiplateforme)
Reçoit les messages utilisateur, appelle Ollama (Llama 3.2 3B) et retourne les réponses.
Communication frontend ↔ backend ↔ Ollama fonctionnelle.
Compatible: Windows, macOS, Linux
"""

import warnings
# Supprimer le warning Pydantic V1 de langchain-core (compatibilité Python 3.14)
warnings.filterwarnings("ignore", message=".*Pydantic V1.*", category=UserWarning)

import httpx
import uvicorn
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
import json
from datetime import datetime, timedelta

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
IMAGE_DIR = BASE_DIR / "frontend" / "image"

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
app.mount("/image", StaticFiles(directory=IMAGE_DIR), name="image")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# URL API Ollama (Windows par défaut)
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"  # Qwen 2.5 7B - Qualité GPT-like

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


@app.get("/top_drivers")
async def get_top_drivers(top_n: int = 3, force_refresh: bool = False):
    """Récupère le top N des pilotes F1 - Cache 7 jours (lundi refresh)"""
    from backend.standings_utils import get_driver_standings
    from backend.optimized_cache import get_cache, CACHE_TTL
    
    try:
        cache = get_cache()
        cache_key = f"top_drivers:{top_n}"
        
        # Vérifier cache si pas force_refresh
        if not force_refresh:
            cached = cache.get(cache_key)
            if cached:
                return cached
        
        standings = get_driver_standings(top_n=top_n)
        if standings:
            # Parser le format "1. Nom — NN pts"
            drivers = []
            for line in standings.split("\n"):
                if line.strip():
                    parts = line.split(" — ")
                    if len(parts) >= 2:
                        name_part = parts[0].split(". ", 1)
                        name = name_part[1] if len(name_part) > 1 else parts[0]
                        points = parts[1].replace(" pts", "")
                        drivers.append({"name": name, "points": points})
                    else:
                        drivers.append({"name": line, "points": ""})
            
            result = {"drivers": drivers[:top_n], "source": "F1 Standings"}
            # Cacher 7 jours pour widgets
            cache.set(cache_key, result, CACHE_TTL.get("widget_standings", 604800))
            return result
        return {"drivers": [], "source": None}
    except Exception as e:
        logger.warning(f"Erreur récupération classement: {e}")
        return {"drivers": [], "source": None}


@app.get("/next_race_countdown")
async def get_next_race_countdown_impl(force_refresh: bool = False):
    """Récupère le compte à rebours du prochain GP"""
    from datetime import datetime, timezone, timedelta
    from backend.optimized_cache import get_cache
    
    cache = get_cache()
    cache_key = "next_race_countdown"
    
    # Vérifier cache si pas force_refresh
    if not force_refresh:
        cached = cache.get(cache_key)
        if cached:
            return cached
    
    try:
        # Données mockées du calendrier F1 2026
        # Les GP viennent du calendrier officiel FIA
        races_2026 = [
            {"name": "GP de Bahreïn", "date": "2026-03-22", "time": "15:00:00"},
            {"name": "GP d'Australie", "date": "2026-03-29", "time": "14:10:00"},
            {"name": "GP de Chine", "date": "2026-04-19", "time": "13:00:00"},
            {"name": "GP du Japon", "date": "2026-04-26", "time": "14:00:00"},
            {"name": "GP d'Arabie Saoudite", "date": "2026-05-03", "time": "18:30:00"},
            {"name": "GP de Monaco", "date": "2026-05-24", "time": "14:00:00"},
            {"name": "GP du Canada", "date": "2026-06-14", "time": "19:00:00"},
            {"name": "GP de Silverstone", "date": "2026-07-05", "time": "14:00:00"},
            {"name": "GP de Hongrie", "date": "2026-07-19", "time": "15:00:00"},
            {"name": "GP de Spa-Francorchamps", "date": "2026-08-02", "time": "15:00:00"},
            {"name": "GP des Pays-Bas", "date": "2026-08-30", "time": "15:00:00"},
            {"name": "GP d'Italie", "date": "2026-09-06", "time": "15:00:00"},
            {"name": "GP de Singapour", "date": "2026-09-27", "time": "19:00:00"},
            {"name": "GP du Japon", "date": "2026-10-04", "time": "14:00:00"},
            {"name": "GP de Mexico", "date": "2026-10-25", "time": "20:00:00"},
            {"name": "GP de São Paulo", "date": "2026-11-08", "time": "17:00:00"},
            {"name": "GP d'Abu Dhabi", "date": "2026-11-29", "time": "13:00:00"},
        ]
        
        now = datetime.now(timezone.utc)
        next_race = None
        
        # Trouver le prochain GP
        for race in races_2026:
            try:
                race_datetime = datetime.strptime(
                    f"{race['date']} {race['time']}", 
                    "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
                
                if race_datetime > now:
                    next_race = race
                    break
            except:
                continue
        
        if not next_race:
            # Si pas de GP futur, montrer le dernier
            result = {"countdown": "Saison terminée", "race_name": "Fin de saison"}
            cache.set(cache_key, result, 3600)
            return result
        
        # Calculer le compte à rebours
        race_datetime = datetime.strptime(
            f"{next_race['date']} {next_race['time']}",
            "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        
        time_diff = race_datetime - now
        days = time_diff.days
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60
        
        # Formater le compte à rebours
        if days > 0:
            countdown_text = f"Dans {days}j {hours}h"
        elif hours > 0:
            countdown_text = f"Dans {hours}h {minutes}min"
        else:
            countdown_text = f"Dans {minutes}min"
        
        result = {
            "countdown": countdown_text,
            "race_name": next_race["name"],
        }
        
        # Cacher 1h
        cache.set(cache_key, result, 3600)
        return result
        
    except Exception as e:
        logger.warning(f"Erreur récupération countdown: {e}")
        result = {"countdown": "—", "race_name": "—"}
        cache.set(cache_key, result, 3600)
        return result


@app.get("/next_race_countdown")
async def get_next_race_countdown(force_refresh: bool = False):
    """Récupère le compte à rebours du prochain GP depuis Aurupteur - Cache 7 jours"""
    return await get_next_race_countdown_impl(force_refresh)


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

    # CRAWLING AUTOMATIQUE HEBDOMADAIRE
    def auto_crawl_if_needed():
        """Lance le crawling automatiquement si le dernier date de plus de 7 jours."""
        CRAWL_INTERVAL_DAYS = 7  # Crawl toutes les semaines
        CRAWL_META_FILE = BASE_DIR / "knowledge_base" / "crawled" / "_crawl_metadata.json"
        
        try:
            # Vérifier la date du dernier crawl
            should_crawl = False
            
            if not CRAWL_META_FILE.exists():
                logger.info("🕷️ Aucun crawl précédent détecté, lancement du crawling...")
                should_crawl = True
            else:
                try:
                    with open(CRAWL_META_FILE, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                    
                    last_crawl = meta.get("last_crawl", {})
                    if last_crawl:
                        # Prendre la date la plus récente
                        dates = [datetime.fromisoformat(d) for d in last_crawl.values() if d]
                        if dates:
                            latest = max(dates)
                            age_days = (datetime.now() - latest).days
                            if age_days >= CRAWL_INTERVAL_DAYS:
                                logger.info(f"🕷️ Dernier crawl il y a {age_days} jours, relancement...")
                                should_crawl = True
                            else:
                                logger.info(f"✅ Crawl récent ({age_days} jours), pas de re-crawl")
                        else:
                            should_crawl = True
                    else:
                        should_crawl = True
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"⚠️ Metadata crawl corrompue: {e}")
                    should_crawl = True
            
            if should_crawl:
                def run_crawler():
                    try:
                        crawler_script = BASE_DIR / "scripts" / "crawler_f1.py"
                        if crawler_script.exists():
                            logger.info("🕷️ Crawling en arrière-plan...")
                            result = subprocess.run(
                                [sys.executable, str(crawler_script)],
                                capture_output=True,
                                text=True,
                                timeout=600  # 10 minutes max
                            )
                            if result.returncode == 0:
                                logger.info("✅ Crawling terminé, rechargement KB...")
                                reload_knowledge_base()
                                logger.info("✅ Knowledge Base rechargée avec nouveaux fichiers")
                            else:
                                logger.warning(f"⚠️ Crawling terminé avec erreurs: {result.stderr[:200]}")
                        else:
                            logger.warning(f"⚠️ Script crawler non trouvé: {crawler_script}")
                    except subprocess.TimeoutExpired:
                        logger.warning("⚠️ Crawling timeout (>10min)")
                    except Exception as e:
                        logger.error(f"❌ Erreur crawling: {e}")
                
                # Lancer en arrière-plan pour ne pas bloquer le démarrage
                threading.Thread(target=run_crawler, daemon=True).start()
        
        except Exception as e:
            logger.warning(f"⚠️ Erreur vérification crawl: {e}")

    # Lancer le crawl auto si nécessaire
    AUTO_CRAWL_ENABLED = os.environ.get("AUTO_CRAWL", "1").lower() in ("1", "true", "yes")
    if AUTO_CRAWL_ENABLED:
        auto_crawl_if_needed()
    else:
        logger.info("🕷️ Auto-crawl désactivé (AUTO_CRAWL=0)")

    # PRÉ-CHARGEMENT DU CACHE au démarrage (optimisation vitesse première requête)
    def preload_cache():
        """Pré-charge les données fréquentes en cache pour accélérer les premières requêtes."""
        try:
            logger.info("🚀 Pré-chargement du cache...")
            # 1. Pré-charger knowledge base
            kb = get_knowledge_base()
            logger.info(f"✅ KB chargée: {len(kb.docs)} documents")
            
            # 1.5 Pré-charger l'index CSV F1 (43K+ entrées)
            try:
                from backend.csv_index import load_csv_index, get_index_stats
                count = load_csv_index()
                stats = get_index_stats()
                logger.info(f"✅ Index CSV chargé: {count} entrées, {stats['unique_keywords']} mots-clés")
            except Exception as e:
                logger.warning(f"⚠️ Index CSV non chargé: {e}")

            # 2. Pré-charger classements (en background)
            def load_standings():
                try:
                    get_standf1_standings_summary(top_n=10)
                    get_standf1_constructors_summary(top_n=10)
                    logger.info("✅ Classements pré-chargés")
                except Exception as e:
                    logger.warning(f"⚠️ Classements non disponibles: {e}")

            # 3. Pré-charger actualités (en background) - DÉSACTIVÉ pour éviter blocage
            def load_news():
                try:
                    # TEMPORAIREMENT DÉSACTIVÉ - cause problèmes de scraping
                    # get_news_summaries(limit=1)
                    # logger.info("✅ Actualités pré-chargées")
                    pass
                except Exception as e:
                    logger.warning(f"⚠️ Actualités non disponibles: {e}")

            # Lancer en threads séparés pour ne pas bloquer le démarrage
            # threading.Thread(target=load_standings, daemon=True).start()
            # threading.Thread(target=load_news, daemon=True).start()  # Désactivé

            logger.info("🎯 Cache pré-chargé avec succès")
        except Exception as e:
            logger.warning(f"⚠️ Erreur pré-chargement cache: {e}")

    # DÉSACTIVER preload_cache pour éviter blocage du démarrage
    # threading.Thread(target=preload_cache, daemon=True).start()

    # Démarrer le scheduler Monday (crawl widgets lundi uniquement)
    try:
        from backend.monday_scheduler import start_scheduler
        start_scheduler()
        logger.info("✅ MondayScheduler démarré (refresh widgets le lundi)")
    except Exception as e:
        logger.warning(f"⚠️ Erreur démarrage scheduler: {e}")

    uvicorn.run("app:app", host=HOST, port=PORT, reload=dev_reload)
