#!/usr/bin/env python3
"""
Crawler F1 News - Scrape actualités F1 depuis sources externes

Sources principales:
- motorsport.com
- autosport.com  
- standf1.com
- actuf1.com

Ajoute les articles à la Knowledge Base automatiquement.
"""

import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import httpx
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
KB_DIR = BASE_DIR / "knowledge_base"
KB_NEWS_FILE = KB_DIR / "news_cache.md"
CRAWL_METADATA = KB_DIR / ".crawl_metadata.json"

# News sources avec selecteurs CSS
NEWS_SOURCES = {
    "motorsport.com": {
        "url": "https://www.motorsport.com/f1/news/latest/",
        "title_selector": "h2.ms-3.is-title-medium",
        "link_selector": "a.ms-3",
        "timeout": 15
    },
    "autosport.com": {
        "url": "https://www.autosport.com/f1/",
        "title_selector": "h2 a",
        "link_selector": "h2 a",
        "timeout": 15
    },
    "standf1.com": {
        "url": "https://www.standf1.com/",
        "title_selector": "a.card-link",
        "link_selector": "a.card-link",
        "timeout": 15
    }
}


def scrape_source(source_name: str, source_config: dict) -> list[dict]:
    """Scrape une source d'actualités F1"""
    logger.info(f"🕷️ Scraping {source_name}...")
    articles = []
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = httpx.get(
            source_config["url"],
            headers=headers,
            timeout=source_config["timeout"],
            follow_redirects=True
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Chercher les titres et liens
        titles = soup.select(source_config["title_selector"])[:5]  # Top 5 articles
        
        for title_elem in titles:
            try:
                title_text = title_elem.get_text(strip=True)
                
                # Chercher le lien (soit dans title_elem soit parent)
                link_elem = title_elem.find("a") or title_elem.parent.find("a")
                link = link_elem.get("href", "") if link_elem else ""
                
                if link and not link.startswith("http"):
                    # Reconstruire URL absolue
                    base_domain = source_config["url"].split("/")[2]
                    link = f"https://{base_domain}{link}"
                
                if title_text and link and link.startswith("http"):
                    articles.append({
                        "title": title_text[:200],
                        "link": link,
                        "source": source_name,
                        "timestamp": datetime.now().isoformat()
                    })
            except Exception as e:
                logger.debug(f"  ⚠️ Erreur parsing article: {e}")
                continue
        
        logger.info(f"  ✅ {len(articles)} articles trouvés sur {source_name}")
        return articles
        
    except httpx.TimeoutException:
        logger.warning(f"  ⏱️ Timeout {source_name}")
        return []
    except httpx.HTTPError as e:
        logger.warning(f"  ❌ Erreur réseau {source_name}: {e}")
        return []
    except Exception as e:
        logger.error(f"  ❌ Erreur scraping {source_name}: {e}")
        return []


def save_articles_to_kb(articles: list[dict]) -> None:
    """Sauvegarde les articles dans la Knowledge Base"""
    if not articles:
        logger.warning("⚠️ Aucun article à sauvegarder")
        return
    
    try:
        # Créer contenu Markdown
        content = "# F1 Actualités\n\n"
        content += f"*Mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
        
        # Grouper par source
        by_source = {}
        for article in articles:
            source = article["source"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(article)
        
        # Formatter articles
        for source, source_articles in by_source.items():
            content += f"## {source}\n\n"
            for article in source_articles:
                content += f"- **{article['title']}**\n"
                content += f"  [{article['link']}]({article['link']})\n"
                content += f"  *{article['timestamp']}*\n\n"
        
        # Écrire fichier
        KB_NEWS_FILE.write_text(content, encoding="utf-8")
        logger.info(f"✅ {len(articles)} articles sauvegardés dans {KB_NEWS_FILE.name}")
        
        # Mettre à jour metadata
        metadata = {
            "last_crawl": datetime.now().isoformat(),
            "articles_count": len(articles),
            "sources": list(by_source.keys())
        }
        CRAWL_METADATA.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde KB: {e}")
        raise


def main():
    """Crawl principal"""
    logger.info("🕷️ Aucun crawl précédent détecté, lancement du crawling...")
    
    all_articles = []
    
    # Scraper toutes les sources
    for source_name, source_config in NEWS_SOURCES.items():
        try:
            articles = scrape_source(source_name, source_config)
            all_articles.extend(articles)
        except Exception as e:
            logger.error(f"❌ Erreur source {source_name}: {e}")
            continue
    
    # Sauvegarder
    if all_articles:
        try:
            save_articles_to_kb(all_articles)
            logger.info(f"✅ Crawling terminé: {len(all_articles)} articles trouvés")
            return 0
        except Exception as e:
            logger.error(f"❌ Erreur finale: {e}")
            return 1
    else:
        logger.warning("⚠️ Aucun article trouvé")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.warning("⚠️ Crawling interrompu")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)
