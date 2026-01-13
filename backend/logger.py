"""
Logger centralisé pour F1 Chatbot
Configuration logging structuré avec rotation fichiers
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


# -----------------------------------
# Configuration
# -----------------------------------
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "f1_bot.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()  # DEBUG, INFO, WARNING, ERROR
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5  # Garde 5 fichiers de backup


# -----------------------------------
# Format structuré
# -----------------------------------
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# -----------------------------------
# Logger factory
# -----------------------------------
def get_logger(name: str = "f1_bot") -> logging.Logger:
    """Retourne logger configuré avec handlers console + fichier rotatif
    
    Args:
        name: Nom du logger (généralement __name__ du module)
    
    Returns:
        Logger configuré
    
    Exemple:
        from backend.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Message")
    """
    logger = logging.getLogger(name)
    
    # Éviter duplication handlers si appelé plusieurs fois
    if logger.handlers:
        return logger
    
    # Niveau global
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    
    # Formatter commun
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Handler 1: Console (stdout)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)  # Console: INFO et plus
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Handler 2: Fichier rotatif
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)  # Fichier: tout
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        # Fallback si problème création fichier
        logger.warning(f"Impossible de créer handler fichier: {e}")
    
    return logger


# -----------------------------------
# Logger par défaut (usage direct)
# -----------------------------------
logger = get_logger("f1_bot")


# -----------------------------------
# Helpers pour migration print() → logger
# -----------------------------------
def log_info(msg: str):
    """Alias pour migration rapide: log_info() au lieu de print('[INFO] ...')"""
    logger.info(msg)

def log_warning(msg: str):
    """Alias pour migration rapide"""
    logger.warning(msg)

def log_error(msg: str):
    """Alias pour migration rapide"""
    logger.error(msg)

def log_debug(msg: str):
    """Alias pour migration rapide"""
    logger.debug(msg)


if __name__ == "__main__":
    # Test logger
    test_logger = get_logger("test")
    test_logger.debug("Message DEBUG (visible en fichier)")
    test_logger.info("Message INFO")
    test_logger.warning("Message WARNING")
    test_logger.error("Message ERROR")
    
    print(f"\n✅ Logger initialisé")
    print(f"📁 Logs: {LOG_FILE}")
    print(f"📊 Niveau: {LOG_LEVEL}")
    print(f"💾 Max size: {MAX_LOG_SIZE / 1024 / 1024:.1f} MB")
    print(f"🔄 Backups: {BACKUP_COUNT}")
