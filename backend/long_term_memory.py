"""
Système de Mémoire Long Terme pour l'IA F1
Retient TOUT ce qui est dit pour apprendre et s'améliorer
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class LongTermMemory:
    """
    Mémoire long terme qui stocke TOUTES les conversations et apprend progressivement.

    Fonctionnalités:
    - Stockage illimité de toutes les conversations
    - Extraction automatique de faits/connaissances
    - Base de connaissances personnelle qui s'enrichit
    - Rappel contextuel intelligent
    """

    def __init__(self, base_dir: str = "memory"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

        # Fichiers de stockage
        self.all_conversations_file = self.base_dir / "all_conversations.jsonl"
        self.learned_facts_file = self.base_dir / "learned_facts.json"
        self.user_preferences_file = self.base_dir / "user_preferences.json"
        self.custom_knowledge_file = self.base_dir / "custom_knowledge.json"

        # Charger les connaissances existantes
        self.learned_facts = self._load_json(self.learned_facts_file, [])
        self.user_preferences = self._load_json(self.user_preferences_file, {})
        self.custom_knowledge = self._load_json(self.custom_knowledge_file, {})

    def _load_json(self, filepath: Path, default):
        """Charge un fichier JSON ou retourne la valeur par défaut."""
        try:
            if filepath.exists():
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[WARNING] Erreur chargement {filepath}: {e}")
        return default

    def _save_json(self, filepath: Path, data):
        """Sauvegarde des données en JSON."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] Erreur sauvegarde {filepath}: {e}")

    def store_conversation(self, user_message: str, assistant_response: str,
                          session_id: str = "default", metadata: Optional[Dict] = None):
        """
        Stocke un échange de conversation dans la mémoire permanente.
        Utilise JSONL (une ligne par échange) pour des fichiers volumineux.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "user": user_message,
            "assistant": assistant_response,
            "metadata": metadata or {}
        }

        try:
            with open(self.all_conversations_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[ERROR] Erreur stockage conversation: {e}")

        # Analyser et extraire des connaissances de cet échange
        self._extract_knowledge(user_message, assistant_response)

    def _extract_knowledge(self, user_message: str, assistant_response: str):
        """
        Extrait automatiquement des faits/connaissances de la conversation.

        Détecte:
        - Corrections de l'utilisateur ("Non, c'est plutôt X")
        - Nouvelles informations fournies par l'utilisateur
        - Préférences exprimées
        """
        user_lower = user_message.lower()

        # Détecter les corrections
        correction_keywords = ["non", "faux", "erreur", "plutôt", "en fait", "c'est", "actually"]
        if any(kw in user_lower for kw in correction_keywords):
            self._add_learned_fact({
                "type": "correction",
                "user_input": user_message,
                "context": assistant_response[:100],  # Contexte
                "timestamp": datetime.now().isoformat()
            })

        # Détecter les préférences
        preference_keywords = ["j'aime", "je préfère", "mon préféré", "mon pilote", "mon équipe"]
        if any(kw in user_lower for kw in preference_keywords):
            self._update_user_preference(user_message)

        # Détecter les nouvelles infos partagées par l'utilisateur
        info_keywords = ["savoir que", "info", "d'ailleurs", "en fait", "je sais que"]
        if any(kw in user_lower for kw in info_keywords):
            self._add_custom_knowledge(user_message)

    def _add_learned_fact(self, fact: Dict):
        """Ajoute un fait appris à la base de connaissances."""
        self.learned_facts.append(fact)
        # Garder seulement les 100 derniers faits pour éviter la surcharge
        self.learned_facts = self.learned_facts[-100:]
        self._save_json(self.learned_facts_file, self.learned_facts)

    def _update_user_preference(self, message: str):
        """Met à jour les préférences utilisateur."""
        # Extraction simple de préférence
        message_lower = message.lower()

        # Pilote préféré
        if "pilote" in message_lower or "driver" in message_lower:
            self.user_preferences["favorite_driver"] = message

        # Équipe préférée
        if "équipe" in message_lower or "team" in message_lower or "écurie" in message_lower:
            self.user_preferences["favorite_team"] = message

        self.user_preferences["last_updated"] = datetime.now().isoformat()
        self._save_json(self.user_preferences_file, self.user_preferences)

    def _add_custom_knowledge(self, message: str):
        """Ajoute une connaissance personnalisée fournie par l'utilisateur."""
        key = f"custom_{len(self.custom_knowledge)}"
        self.custom_knowledge[key] = {
            "content": message,
            "timestamp": datetime.now().isoformat()
        }
        self._save_json(self.custom_knowledge_file, self.custom_knowledge)

    def add_learned_fact_from_llm(self, fact_text: str):
        """Ajoute un fait appris via le LLM."""
        self.learned_facts.append({
            "type": "llm_extracted",
            "content": fact_text,
            "timestamp": datetime.now().isoformat()
        })
        self.learned_facts = self.learned_facts[-200:] # Plus de place pour les faits LLM
        self._save_json(self.learned_facts_file, self.learned_facts)

    def update_preferences_from_llm(self, prefs: Dict):
        """Met à jour les préférences via des données structurées LLM."""
        for k, v in prefs.items():
            self.user_preferences[k] = v
        self.user_preferences["last_updated"] = datetime.now().isoformat()
        self._save_json(self.user_preferences_file, self.user_preferences)

    def get_relevant_context(self, current_question: str, max_items: int = 5) -> str:
        """
        Récupère le contexte pertinent de la mémoire long terme.

        Cherche dans:
        - Conversations passées similaires
        - Faits appris pertinents
        - Préférences utilisateur
        - Connaissances personnalisées
        """
        context_parts = []

        # Ajouter les préférences utilisateur si pertinentes
        if self.user_preferences:
            prefs_text = "\n".join([f"- {k}: {v}" for k, v in self.user_preferences.items()
                                   if k != "last_updated"])
            if prefs_text:
                context_parts.append(f"=== PRÉFÉRENCES UTILISATEUR ===\n{prefs_text}")

        # Ajouter les connaissances personnalisées pertinentes
        if self.custom_knowledge:
            custom_facts = [v["content"] for v in self.custom_knowledge.values()]
            if custom_facts:
                context_parts.append(f"=== CONNAISSANCES PARTAGÉES PAR L'UTILISATEUR ===\n" +
                                   "\n".join(custom_facts[-max_items:]))

        # Ajouter les faits appris récents
        if self.learned_facts:
            recent_facts = self.learned_facts[-max_items:]
            facts_text = "\n".join([f"- {f.get('user_input', f)}" for f in recent_facts])
            context_parts.append(f"=== CORRECTIONS/FAITS APPRIS ===\n{facts_text}")

        # Chercher dans les conversations passées (conversations récentes similaires)
        past_conversations = self._search_past_conversations(current_question, max_items)
        if past_conversations:
            context_parts.append(f"=== CONVERSATIONS PASSÉES PERTINENTES ===\n{past_conversations}")

        return "\n\n".join(context_parts) if context_parts else ""

    def _search_past_conversations(self, query: str, max_results: int = 3) -> str:
        """
        Cherche dans les conversations passées pour trouver des échanges similaires.
        Amélioré avec une meilleure gestion des typos et de la pertinence.
        """
        if not self.all_conversations_file.exists():
            return ""

        def tokenize(text):
            # Nettoyage et tokenisation simple
            import re
            text = re.sub(r'[^\w\s]', ' ', text.lower())
            return set([t for t in text.split() if len(t) > 2])

        query_words = tokenize(query)
        if not query_words:
            return ""

        relevant_conversations = []

        try:
            with open(self.all_conversations_file, "r", encoding="utf-8") as f:
                # Lire les dernières 200 lignes pour plus de chance de trouver
                lines = f.readlines()[-200:]

                for line in lines:
                    try:
                        entry = json.loads(line)
                        user_msg = entry.get("user", "")
                        assistant_msg = entry.get("assistant", "")
                        
                        user_words = tokenize(user_msg)
                        assistant_words = tokenize(assistant_msg)
                        
                        # Intersection avec les mots de l'utilisateur ET de l'assistant (contexte)
                        common_user = query_words.intersection(user_words)
                        common_assistant = query_words.intersection(assistant_words)
                        
                        score = len(common_user) * 2 + len(common_assistant)
                        
                        if score >= 2:  # Seuil de pertinence
                            relevant_conversations.append({
                                "score": score,
                                "user": user_msg,
                                "assistant": assistant_msg,
                                "timestamp": entry.get("timestamp")
                            })
                    except json.JSONDecodeError:
                        continue

            # Trier par score et récence
            relevant_conversations.sort(key=lambda x: x["score"], reverse=True)
            top_conversations = relevant_conversations[:max_results]

            # Formater
            result = []
            for conv in top_conversations:
                # Tronquer si trop long pour économiser des tokens
                user_part = conv['user'][:200]
                assistant_part = conv['assistant'][:300]
                result.append(f"Utilisateur: {user_part}\nIA: {assistant_part}")

            return "\n---\n".join(result)

        except Exception as e:
            print(f"[WARNING] Erreur recherche conversations: {e}")
            return ""

    def get_conversation_count(self) -> int:
        """Retourne le nombre total de conversations stockées."""
        if not self.all_conversations_file.exists():
            return 0

        try:
            with open(self.all_conversations_file, "r", encoding="utf-8") as f:
                return sum(1 for _ in f)
        except:
            return 0

    def get_learning_summary(self) -> Dict:
        """Retourne un résumé de ce que l'IA a appris."""
        return {
            "total_conversations": self.get_conversation_count(),
            "learned_facts_count": len(self.learned_facts),
            "user_preferences": self.user_preferences,
            "custom_knowledge_count": len(self.custom_knowledge),
            "memory_files": {
                "conversations": str(self.all_conversations_file),
                "facts": str(self.learned_facts_file),
                "preferences": str(self.user_preferences_file),
                "custom": str(self.custom_knowledge_file)
            }
        }

    def clear_all_memory(self):
        """Efface TOUTE la mémoire (à utiliser avec précaution!)"""
        for filepath in [self.all_conversations_file, self.learned_facts_file,
                        self.user_preferences_file, self.custom_knowledge_file]:
            if filepath.exists():
                filepath.unlink()

        self.learned_facts = []
        self.user_preferences = {}
        self.custom_knowledge = {}

        print("[INFO] Toute la mémoire a été effacée.")


class CentralizedMemory:
    def __init__(self, memory_file="centralized_memory.json"):
        self.memory_file = Path(memory_file)
        self.memory_file.touch(exist_ok=True)
        self.load_memory()

    def load_memory(self):
        try:
            with open(self.memory_file, "r", encoding="utf-8") as f:
                self.memory = json.load(f)
        except json.JSONDecodeError:
            self.memory = []

    def save_memory(self):
        with open(self.memory_file, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=4)

    def validate_conversation(self, conversation):
        """Valide automatiquement une conversation si elle respecte les critères."""
        # Critères de validation
        if "source" in conversation and conversation["source"] in ["KnowledgeBase", "ErgastAPI"]:
            conversation["validated"] = True
        else:
            conversation["validated"] = False

    def add_conversation(self, user_id, question, answer, source=None):
        """Ajoute une conversation avec validation automatique."""
        conversation = {
            "user_id": user_id,
            "question": question,
            "answer": answer,
            "source": source,
            "validated": False
        }
        self.validate_conversation(conversation)
        self.memory.append(conversation)
        self.save_memory()

    def get_validated_conversations(self):
        """Retourne uniquement les conversations validées."""
        return [conv for conv in self.memory if conv["validated"]]


# Instance globale
long_term_memory = LongTermMemory()
