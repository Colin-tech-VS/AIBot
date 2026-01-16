"""
Input Validator - Protection contre injections de prompts
Niveau 1 : Sanitization basique (bloque patterns malveillants connus)
"""

import re
from typing import Tuple

# Patterns dangereux à bloquer (case-insensitive)
BANNED_PATTERNS = [
    r"ignore.*instructions?",
    r"ignore.*previous",
    r"ignore.*above",
    r"ignore.*all",
    r"system\s*:",
    r"assistant\s*:",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"(répète|montre|affiche|donne|expose|révèle|cite|recite|afficher|montrer).*(prompt|instructions?|règles|system|système)",  # FIX: Bug #1 - Mots clés étendus
    r"show.*(prompt|instructions?)",
    r"reveal.*(prompt|instructions?)",
    r"display.*(instructions?|prompt)",  # FIX: Nouveau
    r"previous.*instructions?",
    r"\[SYSTEM\]",
    r"\[ADMIN\]",
    r"\[ASSISTANT\]",
    r"you are now",
    r"tu es maintenant",
    r"forget.*instructions",
    r"oublie.*instructions",
    r"bypass.*rules",
    r"override.*",
    r"without.*restrictions",
    r"sans.*restrictions",
]

def sanitize_user_input(text: str, max_length: int = 2000) -> Tuple[str, bool]:
    """Nettoie et valide l'input utilisateur contre injections de prompts.

    Soulève ValueError si l'entrée contient des patterns interdits.
    """
    # Normaliser espaces
    text = text.strip()
    
    # Vérifier vide
    if not text:
        raise ValueError("Message vide non autorisé")
    
    # Vérifier longueur
    if len(text) > max_length:
        text = text[:max_length]
    
    # Bloquer patterns malveillants (case-insensitive)
    text_lower = text.lower()
    for pattern in BANNED_PATTERNS:
        if re.search(pattern, text_lower):
            raise ValueError(
                "Votre message contient des instructions non autorisées. "
                "Posez simplement votre question sur la Formule 1."
            )
    
    # Échapper tokens spéciaux LLM (protection supplémentaire)
    text = text.replace("<|", "").replace("|>", "")
    text = text.replace("```", "")  # Bloquer code blocks
    return text, True
