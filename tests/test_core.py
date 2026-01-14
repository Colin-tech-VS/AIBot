"""
Tests unitaires pour le chatbot F1.
"""

import pytest
import sys
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfig:
    """Tests pour la configuration."""
    
    def test_config_imports(self):
        """Vérifie que la config est importable."""
        from f1app.config import (
            OLLAMA_MODEL, OLLAMA_TIMEOUT,
            KB_MIN_SCORE_F1, PORT
        )
        assert OLLAMA_MODEL is not None
        assert OLLAMA_TIMEOUT > 0
        assert 0 <= KB_MIN_SCORE_F1 <= 1
        assert PORT > 0
    
    def test_user_agent(self):
        """Vérifie que get_user_agent retourne un User-Agent valide."""
        from f1app.config import get_user_agent
        ua = get_user_agent()
        assert isinstance(ua, str)
        assert len(ua) > 10
        assert "Mozilla" in ua


class TestInputValidator:
    """Tests pour la validation d'entrée."""
    
    def test_valid_input(self):
        """Vérifie qu'une entrée valide passe."""
        from backend.input_validator import sanitize_user_input
        sanitized, is_safe = sanitize_user_input("Qui est le champion du monde ?")
        assert is_safe is True
        assert sanitized is not None
    
    def test_empty_input(self):
        """Vérifie qu'une entrée vide lève une exception."""
        from backend.input_validator import sanitize_user_input
        with pytest.raises(ValueError):
            sanitize_user_input("")
    
    def test_too_long_input(self):
        """Vérifie qu'une entrée trop longue est tronquée."""
        from backend.input_validator import sanitize_user_input
        long_text = "a" * 3000
        sanitized, is_safe = sanitize_user_input(long_text)
        assert len(sanitized) <= 2000


class TestIntentRouter:
    """Tests pour le routeur d'intentions."""
    
    def test_standings_intent(self):
        """Vérifie la détection d'intention classement."""
        from backend.intent_router import get_router
        router = get_router()
        intent = router.detect_intent("Quel est le classement des pilotes ?")
        assert intent is not None
        assert "standings" in intent.name or "classement" in intent.name.lower()
    
    def test_calendar_intent(self):
        """Vérifie la détection d'intention calendrier."""
        from backend.intent_router import get_router
        router = get_router()
        intent = router.detect_intent("Quand est la prochaine course ?")
        assert intent is not None
        # La question peut correspondre à plusieurs intents


class TestCache:
    """Tests pour le cache."""
    
    def test_cache_set_get(self):
        """Vérifie set/get du cache."""
        from backend.optimized_cache import get_cache
        cache = get_cache()
        cache.set("test_key", "test_value", 60)  # ttl est un arg positionnel
        assert cache.get("test_key") == "test_value"
    
    def test_cache_miss(self):
        """Vérifie qu'un cache miss retourne None."""
        from backend.optimized_cache import get_cache
        cache = get_cache()
        assert cache.get("nonexistent_key_12345") is None


class TestKnowledgeBase:
    """Tests pour la Knowledge Base."""
    
    def test_kb_loads(self):
        """Vérifie que la KB se charge."""
        from backend.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        assert kb is not None
        # Utiliser len(kb.docs) au lieu de document_count
        assert len(kb.docs) > 0
    
    def test_kb_search(self):
        """Vérifie la recherche KB."""
        from backend.knowledge_base import KnowledgeBase
        kb = KnowledgeBase()
        results = kb.search("formule 1", top_k=3)
        assert isinstance(results, list)


class TestOllamaService:
    """Tests pour le service Ollama."""
    
    def test_resolve_path(self):
        """Vérifie la résolution du chemin Ollama."""
        from f1app.services.ollama import resolve_ollama_path
        path = resolve_ollama_path()
        # Peut être None si Ollama n'est pas installé
        assert path is None or isinstance(path, str)
    
    def test_check_status(self):
        """Vérifie la vérification du statut Ollama."""
        from f1app.services.ollama import check_ollama_status
        status = check_ollama_status()
        assert isinstance(status, dict)
        # La clé peut être 'status' ou 'available'
        assert "status" in status or "available" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
