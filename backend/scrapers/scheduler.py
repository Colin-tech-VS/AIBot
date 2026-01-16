"""⏰ Scheduler pour scraping automatique hebdomadaire"""
import schedule
import time
import threading
from backend.logger import get_logger

logger = get_logger(__name__)


class ScraperScheduler:
    def __init__(self):
        self.scrapers = []  # Sera rempli lors du start()
        self.running = False
        self.thread = None
    
    def scrape_job(self):
        """🕷️ Tâche de scraping périodique"""
        logger.info("🕷️ === Scraping planifié démarré ===")
        total_articles = 0
        
        # Import dynamique pour éviter circular import
        from backend.scrapers.motorsport_scraper import MotorsportScraper
        from backend.scrapers.autosport_scraper import AutosportScraper
        
        # Ajouter autres scrapers ici quand créés
        self.scrapers = [
            MotorsportScraper(),
            AutosportScraper(),  # ✅ Activé (test 100% réussi)
            # StandF1Scraper(),    # À décommenter après création
        ]
        
        for scraper in self.scrapers:
            try:
                articles = scraper.scrape_all(max_articles=15)
                total_articles += len(articles)
            except Exception as e:
                logger.error(f"❌ Scraper {scraper.source_name} failed: {e}")
        
        # Recharger la KB après scraping (utilise reload_knowledge_base global)
        try:
            from backend.knowledge_base import reload_knowledge_base
            reload_knowledge_base()
            logger.info(f"✅ KB rechargée ({total_articles} nouveaux articles)")
        except Exception as e:
            logger.error(f"❌ KB reload failed: {e}")
        
        logger.info("🕷️ === Scraping terminé ===")
    
    def start(self, interval_minutes: int = 10080, run_immediately: bool = True):
        """⏰ Démarrer scheduler (défaut: 10080 min = 7 jours)"""
        if self.running:
            logger.warning("⚠️ Scheduler déjà actif")
            return
        
        self.running = True
        
        # Scraping initial
        if run_immediately:
            try:
                self.scrape_job()
            except Exception as e:
                logger.error(f"❌ Scraping initial failed: {e}")
        
        # Scheduler périodique
        schedule.every(interval_minutes).minutes.do(self.scrape_job)
        
        # Thread dédié
        def run_scheduler():
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check toutes les 60s
        
        self.thread = threading.Thread(target=run_scheduler, daemon=True, name="ScraperScheduler")
        self.thread.start()
        logger.info(f"✅ Scheduler démarré (refresh: {interval_minutes} min)")
    
    def stop(self):
        """🛑 Arrêter scheduler"""
        self.running = False
        schedule.clear()
        logger.info("🛑 Scheduler arrêté")


# Instance globale
_scheduler = None

def get_scheduler() -> ScraperScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = ScraperScheduler()
    return _scheduler
