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
import sys
from pathlib import Path

from backend.f1_bot import answer_f1_question
from backend.knowledge_base import get_knowledge_base, reload_knowledge_base, KnowledgeDoc

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
        print(f"[OK] Ollama: utilisant PATH variable")
        break
    elif isinstance(path, Path) and path.exists():
        OLLAMA_PATH = str(path)
        print(f"[OK] Ollama trouve : {OLLAMA_PATH}")
        break

if OLLAMA_PATH is None:
    print("[WARN] Ollama.exe non trouve aux chemins connus")
    print("   Chemins verifies :")
    for p in OLLAMA_PATHS[:-1]:
        print(f"   - {p}")
    print("   Veuillez ajouter le chemin correct dans OLLAMA_PATHS")
    OLLAMA_PATH = OLLAMA_PATHS[0]  # Utiliser le chemin par defaut de toute facon

# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/image", StaticFiles(directory=IMAGE_DIR), name="image")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# URL API Ollama (Windows par defaut)
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
    sources: List[str] = []

# -----------------------------------------------------------------------------
# HISTORIQUE
# -----------------------------------------------------------------------------

chat_history: List[HistoryItem] = []
MAX_HISTORY = 6  # 3 derniers échanges max

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
        bot_response, sources = answer_f1_question(user_message, history=chat_history, rag_only=None)
    except Exception as exc:
        return JSONResponse(status_code=500, content={"detail": f"Erreur backend: {exc}"})

    # Historique
    chat_history.append(HistoryItem(role="user", content=user_message))
    chat_history.append(HistoryItem(role="assistant", content=bot_response))
    if len(chat_history) > MAX_HISTORY:
        chat_history[:] = chat_history[-MAX_HISTORY:]

    return ChatResponse(
        user_message=user_message,
        bot_response=bot_response,
        history=chat_history,
        sources=sources
    )

@app.get("/history")
async def get_history():
    return {"history": chat_history}

@app.post("/clear_history")
async def clear_history():
    chat_history.clear()
    return {"message": "Historique effacé", "history": chat_history}

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
# Knowledge Base Management
# -----------------------------------------------------------------------------

@app.post("/api/kb/add-folder")
async def add_folder_to_kb(request: Request):
    """Ajouter un dossier a la Knowledge Base avec conversion automatique vers ChromaDB"""
    try:
        data = await request.json()
        folder_path = data.get("folder_path", "")

        if not folder_path:
            return JSONResponse({"success": False, "error": "Aucun chemin de dossier fourni"}, status_code=400)

        folder = Path(folder_path)
        if not folder.exists():
            return JSONResponse({"success": False, "error": "Le dossier n'existe pas"}, status_code=400)

        if not folder.is_dir():
            return JSONResponse({"success": False, "error": "Le chemin doit etre un dossier"}, status_code=400)

        # Importer le processeur
        sys.path.insert(0, str(BASE_DIR / "scripts"))
        from import_folder_to_kb import process_folder_to_kb

        result = process_folder_to_kb(str(folder))

        if result["status"] == "success":
            return JSONResponse({
                "success": True,
                "message": f"{result['count']} documents ajoutes avec succes",
                "count": result["count"],
                "total_in_db": result.get("total_in_db", 0)
            })
        else:
            return JSONResponse({
                "success": False,
                "error": result.get("message", "Erreur inconnue")
            }, status_code=500)

    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/api/kb/stats")
async def get_kb_stats():
    """Obtenir les statistiques de la Knowledge Base"""
    try:
        kb = get_knowledge_base()

        # Statistiques par categorie
        categories = {}
        for doc in kb.docs.values():
            categories[doc.category] = categories.get(doc.category, 0) + 1

        return JSONResponse({
            "success": True,
            "total_documents": len(kb.docs),
            "chromadb_active": kb.use_chromadb,
            "chromadb_count": kb.collection.count() if kb.collection else 0,
            "categories": categories
        })
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("Chatbot Ollama Local - FASTAPI (OPTIMISE)")
    print(f"URL: http://localhost:8000")
    print(f"Modele : {OLLAMA_MODEL}")
    print("=" * 60)

    # Disable automatic reload by default to avoid infinite restart loops
    # (useful when files are synced by OneDrive/Cloud and trigger reloads).
    # To enable reload during development set environment variable DEV_RELOAD=1
    dev_reload = os.environ.get("DEV_RELOAD", "0").lower() in ("1", "true", "yes")
    print(f"Reload enabled: {dev_reload}")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=dev_reload)
