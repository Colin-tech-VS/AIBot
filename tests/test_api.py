"""
Tests d'intégration API pour le chatbot F1.
"""

import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path

# Ajouter le dossier parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from f1app.main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Tests pour les endpoints de santé."""
    
    def test_health_endpoint(self):
        """Vérifie que /health répond."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "ollama" in data
        assert "kb" in data
    
    def test_root_endpoint(self):
        """Vérifie que / répond."""
        response = client.get("/")
        assert response.status_code == 200


class TestChatEndpoints:
    """Tests pour les endpoints de chat."""
    
    def test_chat_simple(self):
        """Vérifie une question simple."""
        response = client.post("/chat", json={"message": "Bonjour"})
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
    
    def test_chat_f1_question(self):
        """Vérifie une question F1."""
        response = client.post("/chat", json={
            "message": "Qui est le champion du monde 2023 ?"
        })
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert len(data["response"]) > 10
    
    def test_chat_empty_message(self):
        """Vérifie qu'un message vide est géré."""
        response = client.post("/chat", json={"message": ""})
        # Doit répondre avec une erreur ou validation
        assert response.status_code in [200, 422]
    
    def test_chat_history(self):
        """Vérifie l'historique des conversations."""
        response = client.get("/chat/history")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data


class TestKBEndpoints:
    """Tests pour les endpoints Knowledge Base."""
    
    def test_kb_docs_list(self):
        """Vérifie la liste des documents KB."""
        response = client.get("/kb/docs")
        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
    
    def test_kb_search(self):
        """Vérifie la recherche KB."""
        response = client.get("/kb/search?q=formule%201")
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data
    
    def test_kb_stats(self):
        """Vérifie les statistiques KB."""
        response = client.get("/kb/stats")
        assert response.status_code == 200
        data = response.json()
        assert "document_count" in data


class TestTopDrivers:
    """Tests pour le widget Top 5 pilotes."""
    
    def test_top_drivers(self):
        """Vérifie l'endpoint top_drivers."""
        response = client.get("/top_drivers")
        assert response.status_code == 200
        data = response.json()
        assert "drivers" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
