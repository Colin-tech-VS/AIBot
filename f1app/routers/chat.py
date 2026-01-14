"""
Router Chat - Endpoints pour le chatbot F1.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from backend.logger import get_logger
from backend.f1_bot import answer_f1_question
from backend.long_term_memory import LongTermMemory

logger = get_logger(__name__)
memory = LongTermMemory()

router = APIRouter(prefix="/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    """Requête de chat."""
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Réponse de chat."""
    response: str
    sources: list = []
    cached: bool = False


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Endpoint principal de chat avec le bot F1.
    
    Args:
        request: La requête contenant le message utilisateur
        
    Returns:
        La réponse du bot avec sources optionnelles
    """
    try:
        logger.info(f"Chat request: {request.message[:50]}...")
        
        # Valider l'entrée
        from backend.input_validator import sanitize_user_input
        try:
            sanitized, is_safe = sanitize_user_input(request.message)
            if not is_safe:
                return ChatResponse(
                    response="Message non autorisé.",
                    sources=[],
                    cached=False
                )
        except ValueError as e:
            return ChatResponse(
                response=str(e),
                sources=[],
                cached=False
            )
        
        # Obtenir la réponse
        result = answer_f1_question(sanitized)
        
        # answer_f1_question peut retourner (str, list) ou juste str
        if isinstance(result, tuple):
            response_text, sources = result
        else:
            response_text = result
            sources = []
        
        # Sauvegarder dans la mémoire
        try:
            memory.store_conversation(
                user_message=request.message,
                assistant_response=response_text
            )
        except Exception as mem_error:
            logger.warning(f"Erreur sauvegarde mémoire: {mem_error}")
        
        return ChatResponse(
            response=response_text,
            sources=sources if sources else [],
            cached=False
        )
        
    except Exception as e:
        logger.error(f"Erreur chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_history(limit: int = 10):
    """Récupère l'historique des conversations.
    
    Args:
        limit: Nombre max de conversations à retourner
        
    Returns:
        Liste des dernières conversations
    """
    try:
        history = memory.get_recent_conversations(limit=limit)
        return {"history": history}
    except Exception as e:
        logger.error(f"Erreur history: {e}")
        return {"history": []}


@router.post("/clear")
async def clear_history():
    """Efface l'historique des conversations.
    
    Returns:
        Message de confirmation
    """
    try:
        memory.clear_conversations()
        return {"message": "Historique effacé"}
    except Exception as e:
        logger.error(f"Erreur clear: {e}")
        raise HTTPException(status_code=500, detail=str(e))
