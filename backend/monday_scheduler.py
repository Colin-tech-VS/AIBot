"""
Scheduler pour rafraîchir les widgets (Top 3 Drivers + Prochain GP) le lundi uniquement
Évite le crawling constant, réduit la charge serveur
"""

import threading
import time
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Instance globale du scheduler
_scheduler_instance: Optional['MondayScheduler'] = None


class MondayScheduler:
    """Scheduler pour mettre à jour le cache des widgets le lundi"""
    
    def __init__(self):
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.next_refresh: Optional[datetime] = None
        
    def start(self):
        """Démarrer le scheduler en background"""
        if self.is_running:
            return
        
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("✅ MondayScheduler démarré")
    
    def stop(self):
        """Arrêter le scheduler"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("⏹️ MondayScheduler arrêté")
    
    def _get_next_monday(self) -> datetime:
        """Calculer le prochain lundi à 00:01 UTC"""
        now = datetime.utcnow()
        
        # Lundi = 0 (en Python datetime)
        days_until_monday = (7 - now.weekday()) % 7
        
        if days_until_monday == 0:
            # C'est déjà lundi
            next_monday = now.replace(hour=0, minute=1, second=0, microsecond=0)
            if next_monday <= now:
                # Lundi prochain
                next_monday += timedelta(days=7)
        else:
            # Lundi prochain
            next_monday = (now + timedelta(days=days_until_monday)).replace(
                hour=0, minute=1, second=0, microsecond=0
            )
        
        return next_monday
    
    def _run(self):
        """Boucle du scheduler"""
        while self.is_running:
            try:
                self.next_refresh = self._get_next_monday()
                wait_seconds = (self.next_refresh - datetime.utcnow()).total_seconds()
                
                logger.info(f"⏰ Prochain refresh: {self.next_refresh.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                
                # Attendre jusqu'au lundi (avec vérification toutes les 60 sec)
                while self.is_running and wait_seconds > 0:
                    time.sleep(min(60, wait_seconds))
                    wait_seconds = (self.next_refresh - datetime.utcnow()).total_seconds()
                
                # Refresh le lundi
                if self.is_running:
                    self._refresh_widgets()
                    
            except Exception as e:
                logger.error(f"❌ Erreur scheduler: {e}")
                time.sleep(60)
    
    def _refresh_widgets(self):
        """Rafraîchir les widgets en invalidant le cache"""
        try:
            from backend.optimized_cache import get_cache
            cache = get_cache()
            
            # Invalider les clés de cache des widgets
            cache.invalidate("*widget*")
            cache.invalidate("top_drivers*")
            cache.invalidate("next_race*")
            cache.invalidate("standings:standf1*")
            cache.invalidate("standings:lequipe*")
            
            logger.info("✅ Cache widgets invalidé (lundi refresh)")
            
        except Exception as e:
            logger.error(f"❌ Erreur refresh widgets: {e}")


def get_scheduler() -> MondayScheduler:
    """Obtenir l'instance globale du scheduler"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = MondayScheduler()
    return _scheduler_instance


def start_scheduler():
    """Démarrer le scheduler global"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_scheduler():
    """Arrêter le scheduler global"""
    scheduler = get_scheduler()
    scheduler.stop()
