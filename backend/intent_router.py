"""
Routeur d'intention pour F1 Chatbot
Détecte les intentions et route vers les bons handlers SANS LLM
Objectif: <100ms de latence
"""

import re
from typing import Optional, Dict, Callable
from dataclasses import dataclass


@dataclass
class Intent:
    """Intention détectée avec score de confiance"""
    name: str
    handler: str
    confidence: float
    requires_llm: bool = False


class IntentRouter:
    """Routeur d'intention basé sur regex et mots-clés"""
    
    def __init__(self):
        self.patterns: Dict[str, tuple] = {
            # Format: intent_name -> (regex_pattern, requires_llm, priority)
            
            # Classements (pas besoin LLM)
            "standings_drivers": (
                r"\b(classement|champion|leader|leading|position|points|standings|drivers)\b.*\b(pilote|driver|championship)\b",
                False, 10
            ),
            "standings_teams": (
                r"\b(classement|classement constructeurs|team standings|teams|constructor)\b",
                False, 10
            ),
            
            # Prochain GP (pas besoin LLM)
            "next_race": (
                r"\b(prochain|next|suivant|upcoming)\b.*\b(grand prix|gp|race|course)\b",
                False, 9
            ),
            
            # Calendrier (pas besoin LLM)
            "calendar": (
                r"\b(calendrier|calendar|schedule|dates|races)\b",
                False, 9
            ),
            
            # Stats pilote (besoin LLM pour détails)
            "driver_stats": (
                r"\b(verstappen|hamilton|leclerc|sainz|alonso|norris|piastri|russell|perez|magnussen)\b",
                True, 8
            ),
            
            # Stats équipe (besoin LLM)
            "team_stats": (
                r"\b(red bull|mercedes|ferrari|mclaren|aston martin|alpine|haas|williams)\b",
                True, 8
            ),
            
            # Historique (pas besoin LLM si question simple)
            "history": (
                r"\b(histoire|history|historique|passé|past|anciens|legends)\b",
                True, 7
            ),
            
            # Règles (pas besoin LLM si règles simples en cache)
            "rules": (
                r"\b(règles|rules|regulations|penalty|safe|points|scoring)\b",
                False, 7
            ),
            
            # Résultats dernière course
            "last_race": (
                r"\b(dernier|last|résultat|result|podium|ganant|winner)\b.*\b(course|race|gp)\b",
                True, 8
            ),
            
            # Qui est... (Knowledge Base)
            "knowledge_base": (
                r"\b(qui|who|qu'est|what is|profil|profile|biographie|biography)\b",
                True, 6
            ),
            
            # Questions générales (LLM nécessaire)
            "general_f1": (
                r"\b(f1|formula 1|formule 1|f1|gp|grand prix)\b",
                True, 5
            ),
        }
        
        # Patterns pour questions non-F1 (recherche web)
        self.non_f1_patterns = {
            "colin": r"\b(colin|qui est colin)\b",
            "general": r".*"  # Fallback
        }
    
    def detect_intent(self, query: str) -> Intent:
        """
        Déterminer l'intention avec score de confiance
        Retour ultra-rapide grâce aux regex compilées
        """
        query_lower = query.lower()
        query_len = len(query_lower)
        
        # Scores pour chaque intention
        best_match = None
        best_score = 0
        
        for intent_name, (pattern, requires_llm, priority) in self.patterns.items():
            # Recherche regex case-insensitive
            if re.search(pattern, query_lower, re.IGNORECASE):
                # Score = priority + bonus si multiple matches
                match_count = len(re.findall(pattern, query_lower, re.IGNORECASE))
                score = priority + (match_count - 1) * 0.5
                
                if score > best_score:
                    best_score = score
                    best_match = Intent(
                        name=intent_name,
                        handler=f"handle_{intent_name}",
                        confidence=min(1.0, score / 10.0),
                        requires_llm=requires_llm
                    )
        
        # Si aucune intention F1 détectée, c'est une question générale
        if best_match is None:
            return Intent(
                name="web_search",
                handler="handle_web_search",
                confidence=0.5,
                requires_llm=False
            )
        
        return best_match
    
    def is_f1_question(self, query: str) -> bool:
        """Vérification rapide si c'est une question F1"""
        f1_keywords = [
            "f1", "formula", "formule", "gp", "grand prix",
            "verstappen", "hamilton", "leclerc", "alonso",
            "mercedes", "ferrari", "red bull", "mclaren",
            "race", "course", "driver", "pilote"
        ]
        query_lower = query.lower()
        return any(kw in query_lower for kw in f1_keywords)


# Instance globale compilée
_router_instance: Optional[IntentRouter] = None


def get_router() -> IntentRouter:
    """Obtenir l'instance du routeur"""
    global _router_instance
    if _router_instance is None:
        _router_instance = IntentRouter()
    return _router_instance
