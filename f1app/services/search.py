"""
Service Search - Recherche Knowledge Base et RAG.
Extrait de f1_bot.py pour modularité.
"""

import os
from typing import List, Tuple, Optional
from dataclasses import dataclass

from backend.logger import get_logger
from backend.knowledge_base import KnowledgeBase
from backend.optimized_cache import get_cache
from f1app.config import (
    KB_MIN_SCORE_F1, KB_MIN_SCORE_GENERAL, KB_TOP_K
)

# Alias pour la cohérence interne
KB_MIN_SCORE_CONTEXT = KB_MIN_SCORE_F1
KB_MIN_SCORE_REPONSE = KB_MIN_SCORE_GENERAL
KB_MAX_DOCS_CONTEXT = KB_TOP_K
KB_MAX_DOCS_REPONSE = 5

logger = get_logger(__name__)
_cache = get_cache()
_kb: Optional[KnowledgeBase] = None


@dataclass
class SearchResult:
    """Résultat de recherche KB."""
    content: str
    source: str
    score: float


def get_kb() -> KnowledgeBase:
    """Récupère ou initialise la Knowledge Base (singleton)."""
    global _kb
    if _kb is None:
        from backend.knowledge_base import KnowledgeBase
        _kb = KnowledgeBase()
        logger.info(f"Knowledge Base chargée: {_kb.document_count} documents")
    return _kb


def reload_kb() -> int:
    """Recharge la Knowledge Base depuis le disque.
    
    Returns:
        Le nombre de documents chargés
    """
    global _kb
    _kb = None
    kb = get_kb()
    return len(kb.docs)


def search_kb(query: str, top_k: int = 5, min_score: float = None) -> List[SearchResult]:
    """Recherche dans la Knowledge Base.
    
    Args:
        query: La requête de recherche
        top_k: Nombre max de résultats
        min_score: Score minimum (0-1)
        
    Returns:
        Liste de SearchResult triés par score décroissant
    """
    if min_score is None:
        min_score = KB_MIN_SCORE_CONTEXT
    
    # Cache key
    cache_key = f"kb:search:{hash(query)}:{top_k}:{min_score}"
    cached = _cache.get(cache_key)
    if cached:
        return cached
    
    kb = get_kb()
    
    try:
        results = kb.search(query, top_k=top_k)
        
        search_results = []
        for doc, score in results:
            if score >= min_score:
                search_results.append(SearchResult(
                    content=doc.get("content", doc.get("text", str(doc)))[:1000],
                    source=doc.get("source", "kb"),
                    score=score
                ))
        
        # Trier par score
        search_results.sort(key=lambda x: x.score, reverse=True)
        
        # Mettre en cache
        _cache.set(cache_key, search_results, 300)
        
        return search_results
    except Exception as e:
        logger.error(f"Erreur recherche KB: {e}")
        return []


def get_kb_context(query: str) -> str:
    """Récupère le contexte KB pour une question.
    
    Utilise un score minimum plus bas pour le contexte (0.35)
    car on veut plus de documents potentiellement pertinents.
    
    Args:
        query: La question de l'utilisateur
        
    Returns:
        Le contexte formaté ou chaîne vide
    """
    results = search_kb(query, top_k=KB_MAX_DOCS_CONTEXT, min_score=KB_MIN_SCORE_CONTEXT)
    
    if not results:
        return ""
    
    context_parts = []
    for r in results:
        context_parts.append(f"📚 [{r.source}] (score: {r.score:.2f}): {r.content}")
    
    return "\n\n".join(context_parts)


def get_kb_answer(query: str) -> Optional[str]:
    """Tente d'obtenir une réponse directe de la KB.
    
    Utilise un score minimum élevé (0.55) car on ne veut
    répondre directement que si on est très confiant.
    
    Args:
        query: La question de l'utilisateur
        
    Returns:
        La réponse formatée ou None si pas assez confiant
    """
    results = search_kb(query, top_k=KB_MAX_DOCS_REPONSE, min_score=KB_MIN_SCORE_REPONSE)
    
    if not results:
        return None
    
    # Si score très élevé, répondre directement
    top = results[0]
    if top.score >= 0.7:
        return f"📚 D'après la Knowledge Base ({top.source}):\n\n{top.content}"
    
    return None


def list_kb_docs() -> List[dict]:
    """Liste tous les documents de la KB.
    
    Returns:
        Liste de dicts avec source, type, chars
    """
    kb = get_kb()
    docs_list = []
    
    for doc_id, doc in kb.docs.items():
        # doc est un KnowledgeDoc
        docs_list.append({
            "source": getattr(doc, 'title', doc_id) or doc_id,
            "type": getattr(doc, 'category', 'general'),
            "chars": len(getattr(doc, 'content', '') or '')
        })
    
    return docs_list


def add_kb_doc(content: str, source: str = "custom") -> bool:
    """Ajoute un document à la KB.
    
    Args:
        content: Le contenu du document
        source: La source/nom du document
        
    Returns:
        True si ajouté avec succès
    """
    kb = get_kb()
    
    try:
        kb.add_document({
            "content": content,
            "source": source,
            "type": "custom"
        })
        logger.info(f"Document ajouté à la KB: {source}")
        return True
    except Exception as e:
        logger.error(f"Erreur ajout KB: {e}")
        return False


def get_kb_stats() -> dict:
    """Retourne les statistiques de la KB.
    
    Returns:
        Dict avec document_count, index_size, etc.
    """
    kb = get_kb()
    
    return {
        "document_count": len(kb.docs),
        "index_size": getattr(kb, "index", None).ntotal if hasattr(kb, "index") and kb.index else None,
        "embedding_model": getattr(kb, "model_name", "sentence-transformers"),
    }
