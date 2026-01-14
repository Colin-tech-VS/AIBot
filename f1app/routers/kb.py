"""
Router KB - Endpoints pour la Knowledge Base.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.logger import get_logger
from f1app.services.search import (
    get_kb, reload_kb, search_kb, list_kb_docs, 
    add_kb_doc, get_kb_stats, SearchResult
)

logger = get_logger(__name__)

router = APIRouter(prefix="/kb", tags=["Knowledge Base"])


class SearchResponse(BaseModel):
    """Réponse de recherche KB."""
    results: List[dict]
    count: int


class AddDocRequest(BaseModel):
    """Requête d'ajout de document."""
    content: str = Field(..., min_length=10, max_length=50000)
    source: str = Field(default="custom", max_length=200)


class DocInfo(BaseModel):
    """Info sur un document."""
    source: str
    type: str
    chars: int


@router.get("/docs")
async def list_documents(limit: int = Query(100, ge=1, le=1000)):
    """Liste les documents de la Knowledge Base.
    
    Args:
        limit: Nombre max de documents à retourner
        
    Returns:
        Liste des documents avec métadonnées
    """
    try:
        docs = list_kb_docs()[:limit]
        return {
            "documents": docs,
            "total": len(list_kb_docs()),
            "showing": len(docs)
        }
    except Exception as e:
        logger.error(f"Erreur list docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search", response_model=SearchResponse)
async def search_documents(
    q: str = Query(..., min_length=2, max_length=500),
    top_k: int = Query(5, ge=1, le=20),
    min_score: float = Query(0.3, ge=0.0, le=1.0)
):
    """Recherche dans la Knowledge Base.
    
    Args:
        q: La requête de recherche
        top_k: Nombre max de résultats
        min_score: Score minimum (0-1)
        
    Returns:
        Résultats de recherche avec scores
    """
    try:
        results = search_kb(q, top_k=top_k, min_score=min_score)
        
        return SearchResponse(
            results=[
                {
                    "content": r.content[:500],
                    "source": r.source,
                    "score": round(r.score, 3)
                }
                for r in results
            ],
            count=len(results)
        )
    except Exception as e:
        logger.error(f"Erreur search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_document(request: AddDocRequest):
    """Ajoute un document à la Knowledge Base.
    
    Args:
        request: Contenu et source du document
        
    Returns:
        Message de confirmation
    """
    try:
        success = add_kb_doc(request.content, request.source)
        if success:
            return {"message": f"Document '{request.source}' ajouté", "success": True}
        else:
            raise HTTPException(status_code=500, detail="Erreur ajout document")
    except Exception as e:
        logger.error(f"Erreur add doc: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reload")
async def reload_knowledge_base():
    """Recharge la Knowledge Base depuis le disque.
    
    Utile après avoir ajouté des fichiers .md ou .csv
    dans le dossier knowledge_base/.
    
    Returns:
        Nombre de documents chargés
    """
    try:
        count = reload_kb()
        return {
            "message": f"Knowledge Base rechargée: {count} documents",
            "document_count": count
        }
    except Exception as e:
        logger.error(f"Erreur reload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Retourne les statistiques de la Knowledge Base.
    
    Returns:
        Statistiques (nombre de docs, taille index, etc.)
    """
    try:
        stats = get_kb_stats()
        return stats
    except Exception as e:
        logger.error(f"Erreur stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
