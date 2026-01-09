"""
Builder de prompt ultra-optimisé pour latence <2s
Maximise pertinence, minimise tokens
"""

from typing import Optional
import json
from datetime import datetime
import os


class OptimizedPromptBuilder:
    """Construit des prompts ultra-compacts (<600 tokens)"""
    
    # Prompt système conversationnel et naturel
    SYSTEM_PROMPT = """Tu es un passionné de F1 qui adore partager ses connaissances de manière décontractée et enthousiaste.
Réponds TOUJOURS en français, de façon naturelle et conversationnelle (comme si tu parlais à un pote).
Utilise le tutoiement, sois concis (2-4 phrases max), mets en **gras** les infos importantes, et ajoute des emojis F1 quand ça colle ! 🏎️
Si l'utilisateur demande un calcul (somme de victoires, écart de points, pourcentage, etc.), utilise les données précises du contexte pour effectuer le calcul toi-même et donner le résultat exact.
Note : La dernière saison complète est 2024, Max Verstappen est le champion en titre."""
    
    @staticmethod
    def get_current_date() -> str:
        """Retourne la date actuelle formatée en français."""
        import locale
        try:
            # Essayer de définir la locale en français
            locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'fr_FR')
            except:
                try:
                    locale.setlocale(locale.LC_TIME, 'French_France.1252')
                except:
                    pass  # Utiliser la locale par défaut

        date_str = datetime.now().strftime("%d %B %Y")

        # Fallback manuel si la locale française n'est pas disponible
        mois_fr = {
            'January': 'janvier', 'February': 'février', 'March': 'mars',
            'April': 'avril', 'May': 'mai', 'June': 'juin',
            'July': 'juillet', 'August': 'août', 'September': 'septembre',
            'October': 'octobre', 'November': 'novembre', 'December': 'décembre'
        }

        for en, fr in mois_fr.items():
            date_str = date_str.replace(en, fr)

        return date_str

    @staticmethod
    def build_f1_question(
        question: str,
        news_summary: Optional[str] = None,
        standings: Optional[str] = None,
        driver_info: Optional[str] = None,
        kb_content: Optional[str] = None,
        conversation_history: Optional[str] = None,
        long_term_context: Optional[str] = None,
        username: Optional[str] = None,
    ) -> str:
        """
        Construire prompt minimal pour questions F1
        - Ajout de la date actuelle dans le contexte
        - Priorité à la Knowledge Base
        - Inclusion de l'historique conversationnel et de la mémoire long terme
        """
        parts = [
            OptimizedPromptBuilder.SYSTEM_PROMPT,
            f"Nous sommes le {OptimizedPromptBuilder.get_current_date()}.",
        ]

        if username:
            parts.append(f"L'utilisateur s'appelle {username}. Utilise son nom de temps en temps pour personnaliser la réponse.")
        
        parts.append("")

        # Ajouter la mémoire long terme (préférences, faits appris)
        if long_term_context:
            parts.extend([
                "=== MÉMOIRE ET PRÉFÉRENCES ===",
                long_term_context,
                "",
            ])

        # Ajouter l'historique conversationnel récent
        if conversation_history:
            parts.extend([
                "=== HISTORIQUE RÉCENT ===",
                conversation_history,
                "",
            ])

        parts.append("=== CONTEXT ===")

        # Ajouter KB en priorité
        if kb_content:
            parts.append(f"Knowledge Base (prioritaire):\n{kb_content}")

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
    def build_general_question(
        question: str,
        conversation_history: Optional[str] = None,
        long_term_context: Optional[str] = None,
        username: Optional[str] = None,
    ) -> str:
        """Prompt pour questions générales non-F1"""
        parts = [
            "Tu es un assistant intelligent et polyvalent, mais avec une personnalité de passionné de F1.",
            "Réponds en français, de manière naturelle et amicale.",
            f"Nous sommes le {OptimizedPromptBuilder.get_current_date()}.",
        ]

        if username:
            parts.append(f"L'utilisateur s'appelle {username}. Utilise son nom de temps en temps.")
        
        parts.append("")

        if long_term_context:
            parts.extend(["=== MÉMOIRE ===", long_term_context, ""])

        if conversation_history:
            parts.extend(["=== HISTORIQUE RÉCENT ===", conversation_history, ""])

        parts.extend([
            "=== QUESTION ===",
            question,
            "",
            "Réponse directe et utile :"
        ])
        return "\n".join(parts)

    @staticmethod
    def build_fact_extraction_prompt(user_message: str, assistant_response: str) -> str:
        """Prompt pour extraire des faits et préférences d'un échange."""
        return f"""Analyse cet échange et extrais uniquement les NOUVEAUX faits importants sur l'utilisateur ou ses préférences.
Si rien de nouveau n'est appris, réponds "RIEN".
Si des infos sont apprises, réponds au format JSON: {{"facts": ["fait 1", "fait 2"], "preferences": {{"cle": "valeur"}}}}

ÉCHANGE :
Utilisateur: {user_message}
Assistant: {assistant_response}

Extraction :"""


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


# Ajout d'une classe pour gérer la mémoire conversationnelle
class ConversationMemory:
    """Gère la mémoire des conversations utilisateur-assistant."""

    def __init__(self, max_history: int = 5, memory_file: str = "conversation_memory.json"):
        self.max_history = max_history
        self.memory_file = memory_file
        self.history = self.load_memory()

    def add_to_memory(self, user_message: str, assistant_response: str):
        """Ajoute un échange à la mémoire."""
        self.history.append({"user": user_message, "assistant": assistant_response})
        self.history = self.history[-self.max_history:]  # Limiter la taille de l'historique
        self.save_memory()

    def get_memory(self) -> str:
        """Retourne l'historique formaté pour les prompts."""
        return "\n".join([
            f"User: {entry['user']}\nAssistant: {entry['assistant']}"
            for entry in self.history
        ])

    def save_memory(self):
        """Sauvegarde la mémoire dans un fichier JSON."""
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=4)

    def load_memory(self):
        """Charge la mémoire depuis un fichier JSON."""
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return []

# Exemple d'utilisation dans le pipeline
conversation_memory = ConversationMemory()

# Ajouter un échange à la mémoire
conversation_memory.add_to_memory("Qui a gagné le dernier GP?", "Max Verstappen a gagné le dernier GP.")

# Inclure la mémoire dans un prompt
historique = conversation_memory.get_memory()
prompt = f"{historique}\nUser: Quelle est la prochaine course?\nAssistant:"

# Ajout d'une classe pour sauvegarder toutes les conversations F1
class F1ConversationLogger:
    """Gère la sauvegarde et la vérification des conversations F1."""

    def __init__(self, log_file: str = "f1_conversations.json"):
        self.log_file = log_file
        self.conversations = self.load_conversations()

    def log_conversation(self, user_message: str, assistant_response: str):
        """Ajoute une conversation F1 au fichier de log."""
        self.conversations.append({"user": user_message, "assistant": assistant_response})
        self.save_conversations()

    def save_conversations(self):
        """Sauvegarde les conversations dans un fichier JSON."""
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.conversations, f, ensure_ascii=False, indent=4)

    def load_conversations(self):
        """Charge les conversations depuis un fichier JSON."""
        if os.path.exists(self.log_file):
            with open(self.log_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def verify_conversations(self):
        """Vérifie les données des conversations pour détecter les anomalies."""
        verified = []
        for convo in self.conversations:
            if "user" in convo and "assistant" in convo:
                verified.append(convo)
            else:
                print(f"[WARN] Conversation invalide détectée: {convo}")
        return verified

    # Ajout d'une méthode pour apprentissage automatique supervisé
    def train_from_validated_data(self):
        """Entraîne un modèle à partir des données validées."""
        validated_data = [
            convo for convo in self.conversations if convo.get("validated")
        ]
        if not validated_data:
            print("[INFO] Aucune donnée validée disponible pour l'entraînement.")
            return

        # Préparer les données pour l'entraînement
        training_data = [
            {
                "input": convo["user"],
                "output": convo["assistant"]
            }
            for convo in validated_data
        ]

        # Exemple : Sauvegarder les données d'entraînement dans un fichier JSON
        with open("validated_training_data.json", "w", encoding="utf-8") as f:
            json.dump(training_data, f, ensure_ascii=False, indent=4)

        print(f"[INFO] Données d'entraînement sauvegardées : {len(training_data)} exemples.")

# Exemple d'utilisation
f1_logger = F1ConversationLogger()

# Ajouter une conversation
f1_logger.log_conversation("Qui a gagné le dernier GP?", "Max Verstappen a gagné le dernier GP.")

# Vérifier les conversations
verified_conversations = f1_logger.verify_conversations()
print(f"Conversations vérifiées: {len(verified_conversations)}")

# Entraîner à partir des données validées
f1_logger.train_from_validated_data()
