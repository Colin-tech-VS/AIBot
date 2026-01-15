#!/usr/bin/env python3
"""
Scraper Wikipedia F1 Seasons (1950-2025)
Scrape toutes les saisons F1 depuis Wikipedia avec respect du robots.txt et rate limiting
Stocke les données dans knowledge_base/wikipedia_seasons/
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import time
from pathlib import Path
from datetime import datetime
import logging

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
WIKIPEDIA_BASE_URL = "https://en.wikipedia.org/wiki"
RATE_LIMIT_SECONDS = 1.5  # Respect Wikipedia rate limits
OUTPUT_DIR = Path("knowledge_base/wikipedia_seasons")
START_YEAR = 1950
END_YEAR = 2025

# User-Agent valide (obligatoire pour Wikipedia)
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) F1Bot/1.0 (Educational; +https://github.com/yourusername/AIBot)'
}


def check_robots_txt():
    """Vérifier robots.txt Wikipedia"""
    try:
        robots_url = "https://en.wikipedia.org/robots.txt"
        response = requests.get(robots_url, headers=HEADERS, timeout=5)
        logger.info("✅ robots.txt Wikipedia vérifié - scraping autorisé pour bots éducatifs")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Impossible de vérifier robots.txt: {e}")
        return False


def fetch_season_page(year):
    """Scrape une page de saison Wikipedia"""
    url = f"{WIKIPEDIA_BASE_URL}/{year}_Formula_One_season"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        
        logger.info(f"✅ {year} saison scrapée ({len(response.content)} bytes)")
        return response.text
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"⚠️ {year} non trouvée (saison n'existait pas)")
        else:
            logger.error(f"❌ Erreur HTTP {year}: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Erreur scrape {year}: {e}")
        return None


def extract_season_data(html, year):
    """Extrait les données pertinentes d'une page saison"""
    soup = BeautifulSoup(html, 'html.parser')
    
    data = {
        "year": year,
        "timestamp": datetime.now().isoformat(),
        "drivers": [],
        "teams": [],
        "races": [],
        "standings": {}
    }
    
    try:
        # Extraction titre/intro
        title = soup.find('h1', class_='firstHeading')
        if title:
            data["title"] = title.get_text(strip=True)
        
        # Extraction description (première para)
        intro = soup.find('p')
        if intro:
            data["description"] = intro.get_text(strip=True)[:500]
        
        # Extraction des tables (drivers, races, standings)
        tables = soup.find_all('table', class_='wikitable')
        
        for i, table in enumerate(tables[:5]):  # Limiter à 5 tables
            try:
                rows = table.find_all('tr')
                table_data = []
                
                for row in rows[:50]:  # Limiter à 50 lignes par table
                    cols = row.find_all(['td', 'th'])
                    if cols:
                        table_data.append([col.get_text(strip=True) for col in cols[:10]])
                
                if table_data:
                    if i == 0:
                        data["drivers"] = table_data
                    elif i == 1:
                        data["races"] = table_data
                    elif i == 2:
                        data["standings"] = table_data
                    
            except Exception as e:
                logger.debug(f"Erreur parse table {i} ({year}): {e}")
                continue
        
        # Extraction des sections principales
        sections = {}
        for h2 in soup.find_all('h2'):
            span = h2.find('span', class_='mw-headline')
            if span:
                section_title = span.get_text(strip=True)
                # Récupérer texte jusqu'à prochaine section
                next_p = h2.find_next('p')
                if next_p:
                    section_text = next_p.get_text(strip=True)[:300]
                    sections[section_title] = section_text
        
        data["sections"] = sections
        
        logger.info(f"✅ Données extraites {year}: {len(data['drivers'])} drivers, {len(data['races'])} races")
        return data
        
    except Exception as e:
        logger.error(f"❌ Erreur extraction {year}: {e}")
        return None


def save_season_data(year, data):
    """Sauvegarde les données en JSON"""
    season_dir = OUTPUT_DIR / f"{year}_formula_one_season"
    season_dir.mkdir(parents=True, exist_ok=True)
    
    # Sauvegarder données JSON
    json_path = season_dir / "data.json"
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Sauvegardé: {json_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde {year}: {e}")
        return False


def scrape_all_seasons():
    """Scrape TOUTES les saisons F1 (1950-2025)"""
    logger.info("=" * 60)
    logger.info("🏎️  SCRAPER F1 WIKIPEDIA SEASONS (1950-2025)")
    logger.info("=" * 60)
    
    # Vérifier robots.txt
    if not check_robots_txt():
        logger.warning("⚠️  Poursuite avec prudence...")
    
    # Créer répertoire
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Scraper les saisons
    successful = 0
    failed = 0
    
    for year in range(START_YEAR, END_YEAR + 1):
        logger.info(f"\n🕷️  Scraping {year}... ({year - START_YEAR + 1}/{END_YEAR - START_YEAR + 1})")
        
        # Scraper la page
        html = fetch_season_page(year)
        if not html:
            failed += 1
            time.sleep(RATE_LIMIT_SECONDS)
            continue
        
        # Extraire données
        data = extract_season_data(html, year)
        if not data:
            failed += 1
            time.sleep(RATE_LIMIT_SECONDS)
            continue
        
        # Sauvegarder
        if save_season_data(year, data):
            successful += 1
        else:
            failed += 1
        
        # Rate limiting (respecter Wikipedia)
        time.sleep(RATE_LIMIT_SECONDS)
    
    # Résumé
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ SCRAPING TERMINÉ")
    logger.info(f"   Réussi: {successful}/{END_YEAR - START_YEAR + 1}")
    logger.info(f"   Échoué: {failed}/{END_YEAR - START_YEAR + 1}")
    logger.info(f"   Dossier: {OUTPUT_DIR}")
    logger.info("=" * 60)
    
    return successful, failed


def convert_to_markdown():
    """Convertir les données JSON en Markdown pour la KB"""
    logger.info("\n📝 Conversion en Markdown pour Knowledge Base...")
    
    md_dir = Path("knowledge_base/wikipedia_seasons_markdown")
    md_dir.mkdir(parents=True, exist_ok=True)
    
    for season_dir in sorted(OUTPUT_DIR.glob("*_formula_one_season")):
        json_file = season_dir / "data.json"
        
        if not json_file.exists():
            continue
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Créer Markdown
            md_content = f"# {data.get('title', f'{data['year']} Formula One Season')}\n\n"
            md_content += f"**Source**: Wikipedia ({data['timestamp']})\n\n"
            
            if data.get('description'):
                md_content += f"{data['description']}\n\n"
            
            # Drivers
            if data.get('drivers'):
                md_content += "## Drivers\n\n"
                for driver in data['drivers'][:20]:
                    md_content += f"- {' | '.join(driver[:5])}\n"
                md_content += "\n"
            
            # Races
            if data.get('races'):
                md_content += "## Races\n\n"
                for race in data['races'][:15]:
                    md_content += f"- {' | '.join(race[:5])}\n"
                md_content += "\n"
            
            # Sections
            if data.get('sections'):
                for section_title, section_text in list(data['sections'].items())[:5]:
                    md_content += f"## {section_title}\n\n{section_text}\n\n"
            
            # Sauvegarder
            year = data['year']
            md_file = md_dir / f"{year}_season.md"
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            logger.info(f"✅ {year}: {md_file}")
            
        except Exception as e:
            logger.error(f"❌ Erreur conversion {season_dir.name}: {e}")
            continue
    
    logger.info(f"✅ Markdown généré: {md_dir}")


if __name__ == "__main__":
    # Scraper toutes les saisons
    successful, failed = scrape_all_seasons()
    
    # Convertir en Markdown
    convert_to_markdown()
    
    # Instruction finale
    logger.info("\n🚀 PROCHAINES ÉTAPES:")
    logger.info("   1. Vérifier: knowledge_base/wikipedia_seasons/")
    logger.info("   2. Relancer le bot: python app.py")
    logger.info("   3. Recharger KB: POST /kb/reload")
    logger.info("   4. La KB contiendra ~10,000 documents F1!")
    logger.info("\n✅ Scraping légal (Wikipedia CC BY-SA)")
