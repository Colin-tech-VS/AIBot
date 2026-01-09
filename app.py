"""
Backend FastAPI - Chatbot Ollama Local (Multiplateforme)
Reçoit les messages utilisateur, appelle Ollama (Llama 3.2 3B) et retourne les réponses.
Communication frontend ↔ backend ↔ Ollama fonctionnelle.
Compatible: Windows, macOS, Linux
"""

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Literal
import os
from pathlib import Path
import subprocess
import threading

from backend.f1_bot import answer_f1_question
from backend.knowledge_base import get_knowledge_base, reload_knowledge_base, KnowledgeDoc
from backend.optimized_prompts import ConversationMemory

# Nouveaux routers (architecture améliorée)
from app_new.routers import chat_router, session_router, prompt_router

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
        print(f"✓ Ollama: utilisant PATH variable")
        break
    elif isinstance(path, Path) and path.exists():
        OLLAMA_PATH = str(path)
        print(f"✓ Ollama trouvé : {OLLAMA_PATH}")
        break

if OLLAMA_PATH is None:
    print("⚠️  ATTENTION: Ollama.exe non trouvé aux chemins connus")
    print("   Chemins vérifiés :")
    for p in OLLAMA_PATHS[:-1]:
        print(f"   - {p}")
    print("   Veuillez ajouter le chemin correct dans OLLAMA_PATHS")
    OLLAMA_PATH = OLLAMA_PATHS[0]  # Utiliser le chemin par défaut de toute façon

# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ⚠️ URL API Ollama (Windows par défaut)
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"

# -----------------------------------------------------------------------------
# MODELS
# -----------------------------------------------------------------------------

class HistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    user_message: str
    bot_response: str
    history: List[HistoryItem]

# -----------------------------------------------------------------------------
# HISTORIQUE & MÉMOIRE CONVERSATIONNELLE
# -----------------------------------------------------------------------------

chat_history: List[HistoryItem] = []
MAX_HISTORY = 6  # 3 derniers échanges max

# Mémoire conversationnelle persistante
conversation_memory = ConversationMemory(max_history=10, memory_file="conversation_memory.json")

# -----------------------------------------------------------------------------
# ENREGISTREMENT DES NOUVEAUX ROUTERS (ARCHITECTURE AMÉLIORÉE)
# -----------------------------------------------------------------------------
# Ces routers ajoutent des fonctionnalités sans casser l'ancien système
app.include_router(chat_router.router)      # /api/chat/v2 - Chat avec sessions
app.include_router(session_router.router)   # /session/* - Gestion sessions
app.include_router(prompt_router.router)    # /prompt/* - Debug prompts

# -----------------------------------------------------------------------------
# OLLAMA API CALL
# -----------------------------------------------------------------------------

def call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False  # Streaming désactivé pour compatibilité Windows
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.Timeout:
        return "[ERREUR] Timeout Ollama"
    except Exception as e:
        return f"[ERREUR Ollama] {e}"

# -----------------------------------------------------------------------------
# ROUTES
# -----------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "title": "Chatbot Ollama Local"}
    )

@app.post("/chat", response_model=ChatResponse)
async def chat(chat_msg: ChatMessage):
    user_message = chat_msg.message.strip()
    if not user_message:
        return JSONResponse(status_code=400, content={"detail": "Message vide"})

    try:
        # Appeler le pipeline F1 (news + stats + Ollama) avec historique
        # rag_only=None : utilise la config globale RAG_ONLY; pour forcer, passer True/False
        bot_response = answer_f1_question(user_message, history=chat_history, rag_only=None)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"Erreur backend: {exc}"})

    # Historique en mémoire (session)
    chat_history.append(HistoryItem(role="user", content=user_message))
    chat_history.append(HistoryItem(role="assistant", content=bot_response))
    if len(chat_history) > MAX_HISTORY:
        chat_history[:] = chat_history[-MAX_HISTORY:]

    # Mémoire persistante (fichier JSON)
    conversation_memory.add_to_memory(user_message, bot_response)

    return ChatResponse(
        user_message=user_message,
        bot_response=bot_response,
        history=chat_history
    )

@app.get("/history")
async def get_history():
    return {"history": chat_history}

@app.post("/clear_history")
async def clear_history():
    chat_history.clear()
    conversation_memory.history.clear()
    conversation_memory.save_memory()
    return {"message": "Historique effacé (session et mémoire persistante)", "history": chat_history}

# -----------------------------------------------------------------------------
# Knowledge Base Endpoints
# -----------------------------------------------------------------------------

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

# -----------------------------------------------------------------------------
# Health check
# -----------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    try:
        # Tester Ollama via API minimal
        r = requests.post(OLLAMA_URL, json={"model": OLLAMA_MODEL, "prompt": "Ping", "stream": False}, timeout=5)
        ollama_ok = r.status_code == 200
    except Exception:
        ollama_ok = False
    kb = get_knowledge_base()
    return {
        "status": "ok",
        "backend": "FastAPI + Ollama (Windows) + Knowledge Base",
        "ollama_available": ollama_ok,
        "model": OLLAMA_MODEL,
        "knowledge_base": {"available": True, "documents_count": len(kb.docs)}
    }

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("🤖 Chatbot Ollama Local - FASTAPI (OPTIMISÉ)")
    print(f"🚀 http://localhost:8001")
    print(f"🧠 Modèle : {OLLAMA_MODEL}")
    print("=" * 60)

    # Disable automatic reload by default to avoid infinite restart loops
    # (useful when files are synced by OneDrive/Cloud and trigger reloads).
    # To enable reload during development set environment variable DEV_RELOAD=1
    dev_reload = os.environ.get("DEV_RELOAD", "0").lower() in ("1", "true", "yes")
    print(f"Reload enabled: {dev_reload}")
    uvicorn.run("app:app", host="127.0.0.1", port=8001, reload=dev_reload)

    def launch_auto_train():
        """Lancer le script auto_train.py dans un thread séparé."""
        def run_script():
            subprocess.run(["python", "backend/auto_train.py"], check=True)

        thread = threading.Thread(target=run_script, daemon=True)
        thread.start()

    # Lancer auto_train.py au démarrage du serveur
    launch_auto_train()
