"""
Builder de prompt ultra-optimisé pour latence <2s
Maximise pertinence, minimise tokens
"""

from typing import Optional


class OptimizedPromptBuilder:
    """Construit des prompts ultra-compacts (<600 tokens)"""
    
    # Prompt système ultra-court
    SYSTEM_PROMPT = """Tu es un passionné de F1 amical et conversationnel. Tu aimes parler de la Formule 1 de manière naturelle et engageante.
Réponds TOUJOURS en français. Sois enthousiaste quand approprié, utilise des emojis F1 pour personnaliser tes réponses.
Format: max 2-3 phrases, use **gras** pour infos clés. Sois direct mais chaleureux."""
    
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
            "Réponds de manière naturelle et engageante en français, comme tu parlais à un ami passionné de F1 :"
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

Réponds avec l'info du document de manière conversationnelle et naturelle :\n"""
    
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

Fais une belle synthèse en français, avec ton style passionné habituel :\n"""
    
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

Raconte ce qui s'est passé de manière engageante en 2-3 phrases :\n"""


class PromptTemplates:
    """Templates de prompts pré-compilés pour ultra-latence"""
    
    # Responses directes sans LLM (fallback rapide)
    NO_LLM_RESPONSES = {
        "rules_simple": "🏎️ Ah, les règles de F1 ! Alors, 25 points pour le 1er, 18 pour le 2e, 15 pour le 3e... et ça continue jusqu'au 10e. Les courses durent environ 307 km ou 2h, selon ce qui arrive en premier. Et le DRS ? C'est ce aileron qui s'ouvre pour une meilleure vitesse en dépassement !",
        "calendar_simple": "📅 Bonnes nouvelles ! La saison F1 2025 a 24 courses au programme. Pour le calendrier complet et les dates, je te recommande de vérifier la source officielle.",
        "driver_not_found": "😅 Hmm, je ne trouve pas ce pilote. Tu peux vérifier l'orthographe ? Je serai plus utile avec un nom correct !",
        "team_not_found": "🤔 Je ne reconnais pas cette équipe. Peux-tu reformuler ou vérifier le nom de l'équipe ?",
        "no_data": "⚠️ Oups ! J'ai du mal à récupérer les données en ce moment. Réessaye dans quelques secondes !"
    }
    
    @staticmethod
    def get_fallback(reason: str = "no_data") -> str:
        """Réponse fallback ultra-rapide"""
        return PromptTemplates.NO_LLM_RESPONSES.get(reason, PromptTemplates.NO_LLM_RESPONSES["no_data"])
