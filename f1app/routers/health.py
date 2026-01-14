"""
Router Health - Endpoints de santé et monitoring.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from backend.logger import get_logger
from f1app.services.ollama import check_ollama_status
from f1app.services.search import get_kb_stats

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Réponse de santé."""
    status: str
    ollama: dict
    kb: dict
    version: str = "2.0.0"


class OllamaStatus(BaseModel):
    """Statut Ollama."""
    available: bool
    model: Optional[str] = None
    error: Optional[str] = None


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Vérifie la santé du système.
    
    Vérifie:
    - Ollama disponible et modèle chargé
    - Knowledge Base chargée
    
    Returns:
        Statut de santé détaillé
    """
    try:
        # Vérifier Ollama
        ollama_status = check_ollama_status()
        
        # Vérifier KB
        try:
            kb_stats = get_kb_stats()
            kb_ok = kb_stats.get("document_count", 0) > 0
        except Exception as e:
            kb_stats = {"error": str(e)}
            kb_ok = False
        
        # Statut global
        all_ok = ollama_status.get("available", False) and kb_ok
        
        return HealthResponse(
            status="healthy" if all_ok else "degraded",
            ollama=ollama_status,
            kb=kb_stats
        )
        
    except Exception as e:
        logger.error(f"Erreur health check: {e}")
        return HealthResponse(
            status="unhealthy",
            ollama={"available": False, "error": str(e)},
            kb={"error": str(e)}
        )


@router.get("/")
async def root():
    """Page d'accueil - redirige vers le frontend.
    
    Returns:
        Page HTML du chatbot
    """
    from fastapi.responses import FileResponse
    import os
    
    frontend_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "frontend", "index.html"
    )
    
    if os.path.exists(frontend_path):
        return FileResponse(frontend_path)
    
    return {"message": "F1 Chatbot API", "docs": "/docs"}


@router.get("/top_drivers")
async def get_top_drivers():
    """Retourne le Top 5 des pilotes F1.
    
    Utilise les standings en cache ou les récupère
    depuis les sources web (StandF1, L'Équipe).
    
    Returns:
        Liste des 5 premiers pilotes avec points
    """
    try:
        from backend.standings_utils import get_driver_standings
        
        standings = get_driver_standings()
        
        if not standings:
            return {"drivers": [], "error": "Standings indisponibles"}
        
        # Formater le top 5
        top5 = []
        for driver in standings[:5]:
            top5.append({
                "position": driver.get("position", "?"),
                "name": driver.get("name", driver.get("driver", "?")),
                "team": driver.get("team", "?"),
                "points": driver.get("points", 0)
            })
        
        return {"drivers": top5}
        
    except Exception as e:
        logger.error(f"Erreur top drivers: {e}")
        return {"drivers": [], "error": str(e)}
