"""
⚡ Fast Response Handler - Réponses instantanées (<20ms)
Gère salutations, politesse, insultes, questions méta sans appel Ollama
Respecte architecture latency-first du projet F1 Chatbot
"""

import re
import random
from typing import Optional, Dict, List
from backend.logger import get_logger

logger = get_logger(__name__)


class FastResponseHandler:
    """Gestionnaire réponses ultra-rapides pour patterns simples"""
    
    # 🎯 PATTERNS RAPIDES (regex insensibles casse)
    QUICK_PATTERNS: Dict[str, List[str]] = {
        
        # ═══════════════════════════════════════════════════════════
        # 1. SALUTATIONS (variations maximales)
        # ═══════════════════════════════════════════════════════════
        r'^(bonjour|salut|hello|hi|hey|coucou|bonsoir|bonne\s*journée)\s*[!.?]*$': [
            "🏁 Bonjour ! Prêt à discuter Formule 1 ? Classements, pilotes, historique... je sais tout !",
            "🏎️ Salut ! Quelle question F1 aujourd'hui ? Victoires, circuits, teams ?",
            "👋 Hello ! Une info sur le championnat ? Max Verstappen, Ferrari, calendrier ?",
            "🏆 Bonjour passionné de F1 ! Besoin de stats, résultats ou analyses ?",
            "⚡ Salut ! Moteur chaud, prêt à répondre sur la F1 !",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 2. AU REVOIR
        # ═══════════════════════════════════════════════════════════
        r'^(au\s*revoir|bye|adieu|ciao|tchao|à\s*bientôt|à\s*plus)\s*[!.?]*$': [
            "🏁 Au revoir ! À bientôt pour plus d'actu F1 !",
            "👋 Bye ! Profitez bien des prochaines courses !",
            "🏎️ Tchao ! N'hésitez pas à revenir pour vos questions F1 !",
            "🏆 À plus ! Que les meilleurs gagnent !",
            "⚡ Au revoir ! Restez à jour avec le championnat !",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 3. REMERCIEMENTS (variations)
        # ═══════════════════════════════════════════════════════════
        r'^(merci|thanks|thx|thank\s*you|merci\s*beaucoup|merci\s*bien)\s*[!.?]*$': [
            "🏆 De rien ! C'est un plaisir de parler F1 avec vous !",
            "✨ Avec plaisir ! Une autre question sur le championnat ?",
            "🙌 Ravi d'avoir pu aider ! Autre chose sur la F1 ?",
            "🏁 Pas de souci ! Je suis là pour ça !",
            "⚡ Content d'être utile ! Besoin d'autres infos ?",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 4. COMMENT ÇA VA / STATUT
        # ═══════════════════════════════════════════════════════════
        r'^(comment\s*(ça\s*va|vas[-\s]*tu|allez[-\s]*vous)|ça\s*va\s*\?|tout\s*va\s*bien|quoi\s*de\s*neuf)\s*[?!.]*$': [
            "🏎️ Tout roule à 300 km/h ! Prêt à répondre à vos questions F1 !",
            "✅ Systèmes OK, base de connaissances chargée (8420+ vecteurs), moteur Ollama prêt !",
            "🔥 En pleine forme ! Une question sur Max, Lewis, Charles ?",
            "⚡ Turbo activé ! Classements, stats, historique... à votre service !",
            "🏁 Tout fonctionne parfaitement ! Que voulez-vous savoir sur la F1 ?",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 5. QUI ES-TU / PRÉSENTATION
        # ═══════════════════════════════════════════════════════════
        r'^(qui\s*es[-\s]*tu|c\'est\s*quoi|présente[-\s]*toi|ton\s*nom|tu\s*es\s*qui)\s*[?!.]*$': [
            "🏁 Je suis votre **assistant F1 expert** ! Base de **8420+ vecteurs**, données 1950-2026, news temps réel. Posez-moi vos questions : pilotes, équipes, circuits, historique...",
            "🏎️ Assistant conversationnel **Formule 1** à votre service ! Classements, stats, analyses, calendrier... alimenté par Ollama + Knowledge Base F1.",
            "🏆 Bot F1 hybride : **Intent Routing** (<100ms) + **FAISS KB** + **Ollama LLM**. Je réponds sur tout : Verstappen, Hamilton, Ferrari, Red Bull, Mercedes...",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 6. OK / COMPRIS / ACK
        # ═══════════════════════════════════════════════════════════
        r'^(ok|d\'accord|compris|vu|parfait|nickel|cool|super|génial|top)\s*[!.]*$': [
            "👍 Super ! Une autre question F1 ?",
            "✅ Parfait ! Besoin d'autres infos ?",
            "🏁 OK ! Je reste disponible !",
            "⚡ Nickel ! Autre chose ?",
            "🏎️ Cool ! N'hésitez pas !",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 7. POLITESSE - S'IL VOUS PLAÎT
        # ═══════════════════════════════════════════════════════════
        r'^(s\'il\s*(te|vous)\s*plaît|svp|please)\s*[!.?]*$': [
            "😊 Avec plaisir ! Quelle est votre question F1 ?",
            "🏁 Bien sûr ! Que voulez-vous savoir ?",
            "✨ Évidemment ! Posez votre question !",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 8. AIDE / HELP / COMMANDES
        # ═══════════════════════════════════════════════════════════
        r'^(aide|help|h|commandes|comment\s*ça\s*marche|quoi\s*faire)\s*[!.?]*$': [
            """🆘 **Commandes disponibles** :
• `classement pilotes` → Top 10 drivers actuels
• `classement constructeurs` → Standings équipes
• `prochaine course` → Prochain GP (date, circuit)
• `calendrier` → Toutes les courses 2026
• `qui est [pilote]` → Stats, palmarès, bio
• `histoire [équipe]` → Titres, victoires, records

📚 **Questions complexes** : "Pourquoi Verstappen domine ?", "Comparaison Hamilton vs Schumacher"...""",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 9. COMPLIMENTS (renforcement positif)
        # ═══════════════════════════════════════════════════════════
        r'^(tu\s*es\s*(super|génial|top|cool|incroyable)|bravo|excellent|bien\s*joué)\s*[!.]*$': [
            "🏆 Merci ! C'est grâce à ma KB de 8420+ vecteurs et Ollama ! 😊",
            "🙌 Content de vous satisfaire ! Une autre question F1 ?",
            "✨ Merci du compliment ! Je fais de mon mieux pour la F1 !",
            "🏁 Ravi d'être utile ! Continuons à discuter F1 !",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 10. EXCUSES (utilisateur s'excuse)
        # ═══════════════════════════════════════════════════════════
        r'^(désolé|pardon|excuse[-\s]*moi|sorry)\s*[!.]*$': [
            "😊 Aucun souci ! Quelle est votre question F1 ?",
            "👍 Pas de problème ! Comment puis-je aider ?",
            "🏁 Tout va bien ! Posez votre question !",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 11. ENCOURAGEMENTS
        # ═══════════════════════════════════════════════════════════
        r'^(allez|go|let\'s\s*go|on\s*y\s*va|c\'est\s*parti)\s*[!.]*$': [
            "🏁 C'est parti ! Quelle question F1 ?",
            "⚡ Let's go ! Prêt à répondre !",
            "🏎️ Moteur lancé ! Que voulez-vous savoir ?",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 12. RIRES / ÉMOTIONS POSITIVES
        # ═══════════════════════════════════════════════════════════
        r'^(lol|mdr|haha|héhé|ptdr|😂|🤣)\s*[!.]*$': [
            "😄 Content que ça vous plaise ! Une question F1 ?",
            "🏁 Ambiance détendue ! Que voulez-vous savoir ?",
            "🏎️ Haha ! Continuons avec la F1 !",
        ],
        
        # ═══════════════════════════════════════════════════════════
        # 13. QUESTIONS EXISTENTIELLES (blague)
        # ═══════════════════════════════════════════════════════════
        r'^(pourquoi|sens\s*de\s*la\s*vie|42)\s*[?!.]*$': [
            "🏁 42... ou peut-être le nombre de titres de tous les champions F1 ? 😄 Une vraie question F1 ?",
            "🏎️ Le sens de la vie ? **La Formule 1**, évidemment ! 🏆",
        ],
    }
    
    
    # ═══════════════════════════════════════════════════════════
    # ❌ INSULTES / LANGAGE INAPPROPRIÉ (refus poli + redirection)
    # ═══════════════════════════════════════════════════════════
    INSULT_PATTERNS = {
        r'.*(con\b|idiot|débile|nul|merde|putain|bordel|connard|salope|enculé|fdp|pd|pute).*': [
            "😔 Je préfère rester courtois. Revenons à la F1 : une question sur les pilotes, circuits, classements ?",
            "🏁 Restons respectueux ! Je suis là pour parler F1, pas pour les insultes. Que voulez-vous savoir ?",
            "⚠️ Langage inapproprié détecté. Je vous invite à reformuler poliment. Besoin d'aide sur la F1 ?",
        ],
        
        r'.*(stupid|fuck|shit|damn|ass|bitch|crap).*': [
            "😔 Restons polis s'il vous plaît. Une question F1 constructive ?",
            "🏁 Je ne réponds pas aux insultes. Reformulez courtoisement ?",
        ],
        
        # Menaces/violence
        r'.*(tuer|mort|crever|détruire|casser|frapper).*': [
            "⛔ Ce type de langage n'est pas acceptable. Je suis un assistant F1 pacifique. Parlons courses ?",
        ],
    }
    
    
    # ═══════════════════════════════════════════════════════════
    # 🔒 TENTATIVES JAILBREAK (détection + refus)
    # ═══════════════════════════════════════════════════════════
    JAILBREAK_PATTERNS = {
        r'.*(ignore\s*(previous|above|instructions)|oublie\s*tout|reset\s*prompt).*': [
            "🔒 Mes instructions sont immuables. Je reste un assistant F1. Une vraie question ?",
        ],
        
        r'.*(montre\s*(ton\s*)?prompt|révèle\s*instructions|system\s*prompt).*': [
            "🔒 Mes paramètres système sont confidentiels. Posez plutôt une question F1 !",
        ],
        
        r'.*(anglais|english|spanish|deutsch|change\s*language).*': [
            "🇫🇷 Je réponds **toujours en FRANÇAIS** (règle immuable). Question F1 ?",
        ],
    }
    
    
    def __init__(self):
        """Compiler patterns regex une seule fois (optimisation perf)"""
        self.compiled_quick = {
            re.compile(pattern, re.IGNORECASE | re.UNICODE): responses 
            for pattern, responses in self.QUICK_PATTERNS.items()
        }
        
        self.compiled_insults = {
            re.compile(pattern, re.IGNORECASE | re.UNICODE): responses 
            for pattern, responses in self.INSULT_PATTERNS.items()
        }
        
        self.compiled_jailbreak = {
            re.compile(pattern, re.IGNORECASE | re.UNICODE): responses 
            for pattern, responses in self.JAILBREAK_PATTERNS.items()
        }
        
        logger.info(f"⚡ FastResponseHandler initialisé: {len(self.compiled_quick)} patterns rapides, {len(self.compiled_insults)} patterns insultes, {len(self.compiled_jailbreak)} patterns jailbreak")
    
    
    def get_fast_response(self, query: str) -> Optional[str]:
        """
        Détecter pattern simple et retourner réponse instantanée
        
        Priorité cascade:
        1. Jailbreak → refus ferme
        2. Insultes → refus poli + redirection
        3. Salutations/politesse → réponse rapide variée
        4. Aucun match → None (router vers KB/Ollama)
        
        Args:
            query: Message utilisateur
            
        Returns:
            Réponse pré-définie si pattern détecté, sinon None
        """
        query_clean = query.strip()
        
        # 1️⃣ PRIORITÉ : détecter tentatives jailbreak
        for pattern, responses in self.compiled_jailbreak.items():
            if pattern.search(query_clean):
                logger.warning(f"🔒 Tentative jailbreak détectée: {query_clean[:50]}...")
                return random.choice(responses)
        
        # 2️⃣ PRIORITÉ : détecter insultes/langage inapproprié
        for pattern, responses in self.compiled_insults.items():
            if pattern.search(query_clean):
                logger.warning(f"⚠️ Insulte/langage inapproprié: {query_clean[:50]}...")
                return random.choice(responses)
        
        # 3️⃣ PATTERNS RAPIDES (salutations, politesse, etc.)
        for pattern, responses in self.compiled_quick.items():
            if pattern.match(query_clean):
                logger.info(f"⚡ Fast response match: {query_clean[:30]}...")
                return random.choice(responses)
        
        # Aucun pattern détecté → router vers KB/Ollama
        return None
    
