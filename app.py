"""
Backend FastAPI - Chatbot Ollama Local (Windows)
Reçoit les messages utilisateur, appelle Ollama (LLaMA2) et retourne les réponses.
Communication frontend ↔ backend ↔ Ollama fonctionnelle.
Optimisé pour Windows avec chemin complet à ollama.exe
"""

import subprocess
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List
import os
import sys
from pathlib import Path

# Configuration
app = FastAPI(title="Chatbot Ollama Local (Windows)")

# Déterminer les chemins relatifs au répertoire du projet
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "static")

# ⚠️ CONFIGURATION OLLAMA WINDOWS
# Ajouter ici le chemin complet vers ollama.exe sur votre machine
OLLAMA_PATHS = [
    r"C:\Users\cococ\AppData\Local\Programs\Ollama\ollama.exe",  # Chemin par défaut Windows
    r"C:\Program Files\Ollama\ollama.exe",  # Alternative
    "ollama",  # Fallback : cherche dans le PATH
]

# Déterminer le chemin valide vers ollama.exe
OLLAMA_PATH = None
for path in OLLAMA_PATHS:
    if path == "ollama":
        # On essaiera le PATH lors de l'exécution
        OLLAMA_PATH = "ollama"
        break
    elif Path(path).exists():
        OLLAMA_PATH = path
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

# Configuration Jinja2
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Historique des messages en mémoire
chat_history: List[dict] = []

# Modèles Pydantic
class ChatMessage(BaseModel):
    """Modèle pour un message utilisateur"""
    message: str


class ChatResponse(BaseModel):
    """Modèle pour la réponse du backend"""
    user_message: str
    bot_response: str
    history: List[dict]


def call_ollama(prompt: str) -> str:
    """
    Appelle Ollama localement avec le modèle llama2.
    Optimisé pour Windows avec chemin complet.
    
    Args:
        prompt: Le message utilisateur à traiter
        
    Returns:
        La réponse générée par Ollama
    """
    try:
        # Construire la commande avec le chemin complet (Windows)
        command = [OLLAMA_PATH, "run", "llama2", prompt]
        
        print(f"DEBUG: Exécution → {' '.join(command)}")
        
        # Appel subprocess à Ollama avec gestion Windows
        # IMPORTANT: encoding='utf-8' pour éviter les erreurs UnicodeDecodeError
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding='utf-8',  # ✅ Forcer UTF-8 (Windows par défaut utilise cp1252)
            errors='replace',  # ✅ Remplacer les caractères non décodables
            timeout=120,  # Timeout de 2 minutes
            shell=False,  # Ne pas utiliser shell sur Windows
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0  # Pas de fenêtre console
        )
        
        if process.returncode == 0:
            # Retourner la sortie standard (réponse du modèle)
            response = process.stdout.strip()
            return response if response else "⚠️ Ollama a retourné une réponse vide"
        else:
            # En cas d'erreur, retourner le message d'erreur
            error_msg = process.stderr.strip() or "Erreur Ollama inconnue"
            print(f"ERROR: {error_msg}")
            return f"[ERREUR Ollama] {error_msg}"
            
    except FileNotFoundError as e:
        return (
            f"[ERREUR] Ollama introuvable à : {OLLAMA_PATH}\n"
            f"Solutions :\n"
            f"1. Vérifier que Ollama est installé sur Windows\n"
            f"2. Mettre à jour OLLAMA_PATH dans app.py\n"
            f"3. S'assurer qu'Ollama.exe est en cours d'exécution (ollama serve)\n"
            f"Erreur technique: {str(e)}"
        )
    except subprocess.TimeoutExpired:
        return "[ERREUR] Ollama a pris trop longtemps (timeout 120s). Le modèle LLaMA2 génère une réponse complexe."
    except Exception as e:
        print(f"ERROR Exception: {str(e)}")
        return f"[ERREUR] {type(e).__name__}: {str(e)}"


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve la page d'accueil avec le chatbot"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Chatbot Ollama Local",
        },
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(chat_msg: ChatMessage) -> ChatResponse:
    """
    Endpoint POST /chat
    Reçoit un message utilisateur, appelle Ollama, stocke l'historique.
    
    Payload attendu:
    {
        "message": "Bonjour, comment ça va?"
    }
    
    Réponse:
    {
        "user_message": "...",
        "bot_response": "...",
        "history": [...]
    }
    """
    user_message = chat_msg.message.strip()
    
    if not user_message:
        return JSONResponse(
            status_code=400,
            content={"detail": "Le message ne peut pas être vide"}
        )
    
    # Appeler Ollama
    bot_response = call_ollama(user_message)
    
    # Ajouter à l'historique
    chat_history.append({
        "role": "user",
        "content": user_message
    })
    chat_history.append({
        "role": "assistant",
        "content": bot_response
    })
    
    # Retourner la réponse
    return ChatResponse(
        user_message=user_message,
        bot_response=bot_response,
        history=chat_history
    )


@app.get("/history")
async def get_history() -> dict:
    """Retourne l'historique complet des messages"""
    return {"history": chat_history}


@app.post("/clear_history")
async def clear_history() -> dict:
    """Efface l'historique en mémoire"""
    global chat_history
    chat_history = []
    return {"message": "Historique effacé", "history": chat_history}


@app.get("/health")
async def health_check() -> dict:
    """Vérifie la santé du backend et teste Ollama"""
    try:
        # Test rapide : vérifier si ollama répond
        result = subprocess.run(
            [OLLAMA_PATH, "--version"],
            capture_output=True,
            text=True,
            encoding='utf-8',  # ✅ UTF-8 encoding
            errors='replace',
            timeout=5,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        ollama_ok = result.returncode == 0
        ollama_version = result.stdout.strip() if ollama_ok else "Non disponible"
    except Exception as e:
        ollama_ok = False
        ollama_version = str(e)
    
    return {
        "status": "ok",
        "backend": "FastAPI + Ollama (Windows)",
        "ollama_path": OLLAMA_PATH,
        "ollama_available": ollama_ok,
        "ollama_info": ollama_version
    }


if __name__ == "__main__":
    import uvicorn
    
    print("=" * 70)
    print("🤖 Chatbot Ollama Local - Backend FastAPI (WINDOWS)")
    print("=" * 70)
    print(f"📁 Templates: {TEMPLATES_DIR}")
    print(f"📁 Static: {STATIC_DIR}")
    print(f"🔧 Ollama Path: {OLLAMA_PATH}")
    print(f"🚀 Lancement sur http://127.0.0.1:8000")
    print(f"✅ À partir d'ici: http://localhost:8000")
    print("=" * 70)
    print("\n⚠️  PRÉALABLE: Ollama doit être en cours d'exécution")
    print("   Ouvrez un terminal et lancez: ollama serve")
    print("=" * 70 + "\n")
    
    # Lancer le serveur avec reload activé
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
