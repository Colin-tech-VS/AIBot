"""
Backend FastAPI - Chatbot Ollama Local (Windows)
Optimisé avec LLaMA 3.2:3B et API HTTP Ollama
"""

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Literal
import os

from backend.f1_bot import answer_f1_question
from backend.knowledge_base import get_knowledge_base, KnowledgeDoc

# -----------------------------------------------------------------------------
# CONFIG
# -----------------------------------------------------------------------------

app = FastAPI(title="Chatbot Ollama Local - Optimisé")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")

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
        # Ici tu peux garder ton pipeline F1 si besoin
        bot_response = answer_f1_question(user_message)
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
        history=chat_history
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
    try:
        kb = get_knowledge_base()
        kb.load_from_files()
        return {"status": "success", "message": "Knowledge base rechargée", "docs_count": len(kb.docs)}
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
    print(f"🚀 http://localhost:8000")
    print(f"🧠 Modèle : {OLLAMA_MODEL}")
    print("=" * 60)

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
