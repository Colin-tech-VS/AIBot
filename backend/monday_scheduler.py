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
        """Calculer le prochain crawl quotidien à 06:00 UTC (2x par jour: 06:00 et 18:00)
        
        PRIORITÉ 2: Crawl QUOTIDIEN vs hebdo pour news fraîches!
        Articles jamais plus vieux que 12h (vs 7 jours avant)
        """
        now = datetime.utcnow()
        
        # Prochaine exécution à 06:00 ou 18:00 UTC (deux fois par jour)
        current_hour = now.hour
        current_minute = now.minute
        
        # Vérifier si on a passé 06:00 (matin)
        next_crawl = now.replace(hour=6, minute=0, second=0, microsecond=0)
        
        if now >= next_crawl and current_hour < 18:
            # On est entre 6h et 18h → Prochain crawl à 18h
            next_crawl = now.replace(hour=18, minute=0, second=0, microsecond=0)
        elif now >= next_crawl.replace(hour=18):
            # On est après 18h → Prochain crawl à 6h demain
            next_crawl = (now + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        
        logger.info(f"🕷️ Prochain crawl prévu: {next_crawl.strftime('%Y-%m-%d %H:%M UTC')}")
        return next_crawl
    
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
                logger.debug(f"Erreur scheduler: {e}")
                time.sleep(60)
    
    def _refresh_widgets(self):
        """Rafraîchir les widgets en invalidant le cache + relancer le crawling"""
        try:
            from backend.optimized_cache import get_cache
            cache = get_cache()
            
            logger.info("🔄 [LUNDI] Début du refresh hebdo : cache + crawling news...")
            
            # === ÉTAPE 1 : Invalider le cache des widgets ===
            cache.invalidate("*widget*")
            cache.invalidate("top_drivers*")
            cache.invalidate("next_race*")
            cache.invalidate("standings:standf1*")
            cache.invalidate("standings:lequipe*")
            logger.info("✅ Cache widgets invalidé")
            
            # === ÉTAPE 2 : Relancer le crawling des news (lundi matin) ===
            self._run_crawler()
            
        except Exception as e:
            logger.debug(f"Erreur refresh hebdo: {e}")
    
    def _run_crawler(self):
        """Exécuter les scrapers avancés pour actualiser les news"""
        try:
            from backend.scrapers.scheduler import get_scheduler
            from backend.optimized_cache import get_cache

            logger.info("🕷️  Lancement crawling hebdo via backend.scrapers Scheduler")

            # Exécuter un job de scraping complet (motorsport, autosport, ...)
            scheduler = get_scheduler()
            scheduler.scrape_job()

            # Invalider cache news pour forcer la prise en compte des nouvelles données
            cache = get_cache()
            cache.invalidate("news*")
            logger.info("✅ Cache news invalidé (nouvelles données crawlées)")

        except Exception as e:
            logger.debug(f"Erreur crawling hebdo: {e}")


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
