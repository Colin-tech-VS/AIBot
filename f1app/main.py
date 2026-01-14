"""
Application FastAPI principale - F1 Chatbot.

Point d'entrée principal utilisant la nouvelle structure modulaire.
Usage: uvicorn app.main:app --reload --port 8001
"""

import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.logger import get_logger
from f1app.config import (
    HOST, PORT, CRAWL_INTERVAL_DAYS
)

# Alias pour la cohérence
SERVER_HOST = HOST
SERVER_PORT = PORT
APP_NAME = "F1 Chatbot"
APP_VERSION = "2.0.0"
CORS_ORIGINS = ["*"]

logger = get_logger(__name__)

# Timestamp du dernier crawl
_last_crawl: datetime = None


def auto_crawl_if_needed():
    """Lance le crawler automatiquement si plus d'une semaine."""
    global _last_crawl
    
    if _last_crawl and (datetime.now() - _last_crawl) < timedelta(days=CRAWL_INTERVAL_DAYS):
        return
    
    try:
        from scripts.crawler_f1 import main as run_crawler
        logger.info("🕷️ Lancement du crawler automatique...")
        run_crawler()
        _last_crawl = datetime.now()
        logger.info("✅ Crawler terminé")
    except ImportError:
        logger.warning("Crawler non disponible")
    except Exception as e:
        logger.error(f"Erreur crawler: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle de l'application FastAPI."""
    logger.info(f"🚀 Démarrage {APP_NAME} v{APP_VERSION}")
    
    # Initialiser les services
    try:
        from f1app.services.search import get_kb
        kb = get_kb()
        logger.info(f"📚 Knowledge Base: {kb.document_count} documents")
    except Exception as e:
        logger.warning(f"KB non chargée: {e}")
    
    # Vérifier Ollama
    try:
        from f1app.services.ollama import check_ollama_status
        status = check_ollama_status()
        if status.get("available"):
            logger.info(f"🤖 Ollama disponible: {status.get('model')}")
        else:
            logger.warning(f"⚠️ Ollama non disponible: {status.get('error')}")
    except Exception as e:
        logger.warning(f"Ollama check error: {e}")
    
    # Crawler automatique (optionnel)
    # auto_crawl_if_needed()
    
    yield
    
    logger.info("👋 Arrêt de l'application")


# Créer l'application FastAPI
app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Chatbot conversationnel sur la Formule 1 avec LLM local (Ollama)",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monter les fichiers statiques
static_path = Path(__file__).parent.parent / "frontend" / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Enregistrer les routers
from f1app.routers import get_routers
chat_router, kb_router, health_router = get_routers()
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(kb_router)


if __name__ == "__main__":
    import uvicorn
    
    # Trouver un port disponible
    port = SERVER_PORT
    for p in [SERVER_PORT, SERVER_PORT + 1, SERVER_PORT + 2]:
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((SERVER_HOST, p))
                port = p
                break
        except OSError:
            continue
    
    logger.info(f"🌐 Serveur sur http://{SERVER_HOST}:{port}")
    uvicorn.run(app, host=SERVER_HOST, port=port)
