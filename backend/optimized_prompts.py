"""
Builder de prompt ultra-optimisé pour latence <2s
Maximise pertinence, minimise tokens
"""

from typing import Optional


class OptimizedPromptBuilder:
    """Construit des prompts ultra-compacts (<600 tokens)"""
    
    # Prompt système ultra-court
    SYSTEM_PROMPT = """Tu es un expert F1 concis et factuel. Réponds TOUJOURS en français.
Format: max 2-3 phrases, use **gras** pour infos clés, emojis F1 si pertinent."""
    
    @staticmethod
    def build_f1_question(
        question: str,
        news_summary: Optional[str] = None,
        standings: Optional[str] = None,
        driver_info: Optional[str] = None,
    ) -> str:
        """
        Construire prompt minimal pour questions F1
        - Système: ~30 tokens
        - Context: 100-200 tokens
        - Question: 50 tokens
        Total: <400 tokens
        """
        parts = [
            OptimizedPromptBuilder.SYSTEM_PROMPT,
            "",
            "=== CONTEXT ===",
        ]
        
        # Ajouter seulement les données pertinentes
        if standings:
            parts.append(f"Classement actuel:\n{standings}")
        
        if news_summary:
            parts.append(f"Actualités:\n{news_summary}")
        
        if driver_info:
            parts.append(f"Info pilote:\n{driver_info}")
        
        parts.extend([
            "",
            "=== QUESTION ===",
            question,
            "",
            "Réponse brève et factuelle en français :"
        ])
        
        return "\n".join(parts)
    
    @staticmethod
    def build_kb_question(
        question: str,
        kb_content: str,
    ) -> str:
        """
        Prompt pour recherche Knowledge Base
        Extrait info pertinente d'un document
        """
        return f"""{OptimizedPromptBuilder.SYSTEM_PROMPT}

=== DOCUMENT ===
{kb_content}

=== QUESTION ===
{question}

Réponds directement avec l'info du document, sans explications inutiles :\n"""
    
    @staticmethod
    def build_web_search_question(
        question: str,
        search_results: str,
    ) -> str:
        """
        Prompt pour recherche web
        Synthétise les résultats
        """
        return f"""{OptimizedPromptBuilder.SYSTEM_PROMPT}

=== RÉSULTATS WEB ===
{search_results}

=== QUESTION ===
{question}

Synthétise une réponse brève en français :\n"""
    
    @staticmethod
    def build_last_race_question(
        question: str,
        race_results: str,
    ) -> str:
        """Prompt pour résultats dernière course"""
        return f"""{OptimizedPromptBuilder.SYSTEM_PROMPT}

=== RÉSULTATS COURSE ===
{race_results}

=== QUESTION ===
{question}

Résume en 2-3 phrases en français :\n"""


class PromptTemplates:
    """Templates de prompts pré-compilés pour ultra-latence"""
    
    # Responses directes sans LLM (fallback rapide)
    NO_LLM_RESPONSES = {
        "rules_simple": "📋 F1 c'est 25pts pour 1er, 18 pour 2e, 15 pour 3e... Distance ~307km en 2h. DRS et KERS en F1 moderne.",
        "calendar_simple": "📅 F1 2025 a 24 courses. Le calendrier complet est sur Ergast.",
        "driver_not_found": "❓ Je n'ai pas d'info sur ce pilote. Vérifiez l'orthographe.",
        "team_not_found": "❓ Je n'ai pas d'info sur cette équipe.",
        "no_data": "⚠️ Je n'ai pas pu récupérer les données. Réessayez."
    }
    
    @staticmethod
    def get_fallback(reason: str = "no_data") -> str:
        """Réponse fallback ultra-rapide"""
        return PromptTemplates.NO_LLM_RESPONSES.get(reason, PromptTemplates.NO_LLM_RESPONSES["no_data"])
