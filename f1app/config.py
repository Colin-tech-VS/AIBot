"""
Configuration centralisée pour le Chatbot F1.
Toutes les variables de configuration sont ici.
"""

import os
from pathlib import Path
from typing import List, Tuple


# === CHEMINS ===
BASE_DIR = Path(__file__).parent.parent.absolute()
FRONTEND_DIR = BASE_DIR / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates" if (FRONTEND_DIR / "templates").is_dir() else FRONTEND_DIR
STATIC_DIR = FRONTEND_DIR / "static"
KB_DIR = BASE_DIR / "knowledge_base"
LOGS_DIR = BASE_DIR / "logs"
MEMORY_DIR = BASE_DIR / "memory"


# === SERVEUR ===
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", 8001))
PORT_FALLBACK = 8002
DEV_RELOAD = os.getenv("RELOAD", "0").lower() in ("1", "true", "yes")


# === OLLAMA (LLM) ===
OLLAMA_PATHS = [
    # Windows
    Path(os.path.expanduser("~")) / "AppData" / "Local" / "Programs" / "Ollama" / "ollama.exe",
    Path("C:/Program Files/Ollama/ollama.exe"),
    # macOS
    Path("/usr/local/bin/ollama"),
    Path(os.path.expanduser("~")) / ".ollama" / "ollama",
    # Linux
    Path("/usr/bin/ollama"),
    Path("/usr/local/bin/ollama"),
    # Fallback (cherche dans PATH)
    "ollama",
]
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "15"))
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")


# === KNOWLEDGE BASE ===
KB_MIN_SCORE_F1 = float(os.getenv("KB_MIN_SCORE_F1", "0.35"))
KB_MIN_SCORE_GENERAL = float(os.getenv("KB_MIN_SCORE_GENERAL", "0.50"))
KB_TOP_K = int(os.getenv("KB_TOP_K", "10"))
KB_EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


# === CACHE TTL (secondes) ===
CACHE_TTL = {
    "ergast_standings": 600,      # 10 minutes
    "ergast_race": 600,           # 10 minutes
    "ergast_schedule": 3600,      # 1 heure
    "news_articles": 600,         # 10 minutes
    "news:summaries": 600,        # 10 minutes
    "kb_search": 300,             # 5 minutes
}


# === SCRAPING ===
SCRAPING_TIMEOUT = int(os.getenv("SCRAPING_TIMEOUT", "3"))
SCRAPING_DELAY_MIN = 1.5
SCRAPING_DELAY_MAX = 4.0
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


# === CRAWLING ===
CRAWL_INTERVAL_DAYS = int(os.getenv("CRAWL_INTERVAL_DAYS", "7"))
CRAWLED_DIR = KB_DIR / "crawled"
AUTO_CRAWL_ENABLED = os.getenv("AUTO_CRAWL", "1").lower() in ("1", "true", "yes")


# === MODES ===
RAG_ONLY = os.getenv("RAG_ONLY", "0").lower() in ("1", "true", "yes")
ENABLE_LINK_FOLLOW = True
AUTO_TRAIN_ENABLED = os.getenv("AUTO_TRAIN", "0").lower() in ("1", "true", "yes")


# === CRITÈRES INCERTITUDE LLM ===
LLM_UNCERTAIN_KEYWORDS = [
    "désolé", "pas d'info", "je n'ai pas", "incertain", 
    "pas sûr", "ne peux pas confirmer", "pas trouvé"
]
LLM_MIN_RESPONSE_LENGTH = 30


# === SOURCES F1 ===
F1_SOURCES = {
    "standf1": "https://www.standf1.com/",
    "lequipe": "https://www.lequipe.fr/Formule-1/",
    "lequipe_standings": "https://www.lequipe.fr/Formule-1/f1-classement-pilotes.html",
    "toutf1": "https://www.tout-f1.com/",
    "fia_calendar": "https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship",
    "fia_regulations": "https://www.fia.com/regulation/category/110",
}


def get_user_agent() -> str:
    """Retourne un User-Agent aléatoire."""
    import random
    return random.choice(USER_AGENTS)
