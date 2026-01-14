"""
Service Ollama - Gestion des appels au LLM local.
Extrait de f1_bot.py pour modularité.
"""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx

from f1app.config import (
    OLLAMA_PATHS, OLLAMA_MODEL, OLLAMA_TIMEOUT, OLLAMA_URL
)
from backend.logger import get_logger

logger = get_logger(__name__)


def resolve_ollama_path() -> str:
    """Retourne un chemin valide vers ollama (multiplateforme)."""
    for p in OLLAMA_PATHS:
        if p == "ollama":
            cmd = ["which", "ollama"] if sys.platform != "win32" else ["where", "ollama"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return "ollama"
            continue
        if isinstance(p, Path) and p.exists():
            return str(p)
    return "ollama"


OLLAMA_PATH = resolve_ollama_path()


def call_ollama(prompt: str, max_tokens: int = 500) -> str:
    """Appelle Ollama avec le prompt donné et retourne la réponse.
    
    Args:
        prompt: Le prompt à envoyer au modèle
        max_tokens: Nombre maximum de tokens dans la réponse
        
    Returns:
        La réponse du modèle ou un message d'erreur
    """
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
            }
        }
        
        response = httpx.post(
            OLLAMA_URL,
            json=payload,
            timeout=OLLAMA_TIMEOUT
        )
        response.raise_for_status()
        
        data = response.json()
        return data.get("response", "").strip()
        
    except httpx.TimeoutException:
        logger.warning(f"Timeout Ollama après {OLLAMA_TIMEOUT}s")
        return "[ERREUR] Le modèle met trop de temps à répondre."
    except httpx.HTTPStatusError as e:
        logger.error(f"Erreur HTTP Ollama: {e}")
        return f"[ERREUR] Ollama non disponible: {e}"
    except Exception as e:
        logger.error(f"Erreur Ollama: {e}")
        return f"[ERREUR] Problème de communication avec Ollama: {e}"


def check_ollama_status() -> dict:
    """Vérifie si Ollama est accessible.
    
    Returns:
        Dict avec status, model, path
    """
    try:
        response = httpx.get(
            "http://127.0.0.1:11434/api/tags",
            timeout=3
        )
        if response.status_code == 200:
            data = response.json()
            models = [m.get("name") for m in data.get("models", [])]
            return {
                "status": "ok",
                "model": OLLAMA_MODEL,
                "available_models": models,
                "path": OLLAMA_PATH
            }
    except Exception as e:
        logger.warning(f"Ollama check failed: {e}")
    
    return {
        "status": "error",
        "model": OLLAMA_MODEL,
        "available_models": [],
        "path": OLLAMA_PATH
    }


def is_response_uncertain(response: str) -> bool:
    """Vérifie si la réponse LLM indique une incertitude.
    
    Args:
        response: La réponse du LLM
        
    Returns:
        True si la réponse semble incertaine
    """
    from app.config import LLM_UNCERTAIN_KEYWORDS, LLM_MIN_RESPONSE_LENGTH
    
    if not response:
        return True
    
    if len(response) < LLM_MIN_RESPONSE_LENGTH:
        return True
    
    response_lower = response.lower()
    for keyword in LLM_UNCERTAIN_KEYWORDS:
        if keyword in response_lower:
            return True
    
    return False
