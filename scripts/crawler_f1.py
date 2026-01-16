"""
Crawler F1 - Récupère et sauvegarde les données des sites F1
Exécuter 1x/jour pour alimenter la Knowledge Base
Anti-détection: délais, User-Agents rotatifs, respect robots.txt
"""

import os
import sys
import time
import random
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import re

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from bs4 import BeautifulSoup

# Configuration
CRAWLED_DIR = Path(__file__).parent.parent / "knowledge_base" / "crawled"
CRAWLED_DIR.mkdir(parents=True, exist_ok=True)

# Fichier de métadonnées pour tracker les crawls
CRAWL_META_FILE = CRAWLED_DIR / "_crawl_metadata.json"

# User-Agents rotatifs (navigateurs réels)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Sites F1 à crawler
SITES_CONFIG = {
    "standf1": {
        "base_url": "https://www.standf1.com",
        "start_urls": [
            "https://www.standf1.com/",
            "https://www.standf1.com/classement-pilotes/",
            "https://www.standf1.com/classement-constructeurs/",
            "https://www.standf1.com/calendrier/",
        ],
        "allowed_paths": ["/classement", "/calendrier", "/pilote", "/ecurie", "/circuit", "/actualite"],
        "max_pages": 50,
        "delay_range": (1.5, 3.0),  # Délai entre requêtes (secondes)
    },
    "lequipe": {
        "base_url": "https://www.lequipe.fr",
        "start_urls": [
            "https://www.lequipe.fr/Formule-1/",
            "https://www.lequipe.fr/Formule-1/f1-classement-pilotes.html",
            "https://www.lequipe.fr/Formule-1/f1-classement-constructeurs.html",
        ],
        "allowed_paths": ["/Formule-1/"],
        "max_pages": 30,
        "delay_range": (2.0, 4.0),  # L'Équipe plus strict
    },
    "fia": {
        "base_url": "https://www.fia.com",
        "start_urls": [
            "https://www.fia.com/events/fia-formula-one-world-championship/season-2025/2025-fia-formula-one-world-championship",
            "https://www.fia.com/regulation/category/110",
        ],
        "allowed_paths": ["/events/fia-formula-one", "/regulation"],
        "max_pages": 20,
        "delay_range": (2.0, 5.0),  # FIA très prudent
    },
    "toutf1": {
        "base_url": "https://www.tout-f1.com",
        "start_urls": [
            "https://www.tout-f1.com/",
            "https://www.tout-f1.com/toute-l-actu/f1",
            "https://www.tout-f1.com/toute-l-actu/essais",
            "https://www.tout-f1.com/toute-l-actu/fia",
            "https://www.tout-f1.com/les-saisons",
        ],
        "allowed_paths": ["/toute-l-actu", "/les-saisons", "/article"],
        "max_pages": 40,
        "delay_range": (2.0, 4.0),  # Délai prudent
    },
}


def get_random_headers() -> Dict[str, str]:
    """Génère des headers réalistes avec User-Agent aléatoire"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }


def url_to_filename(url: str) -> str:
    """Convertit une URL en nom de fichier sécurisé"""
    # Hash court de l'URL pour unicité
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    # Extraire le path
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_") or "index"
    # Nettoyer les caractères spéciaux
    path = re.sub(r'[^\w\-]', '_', path)[:50]
    return f"{path}_{url_hash}.md"


def extract_text_content(html: str, base_url: str) -> Dict:
    """Extrait le contenu textuel principal d'une page HTML"""
    soup = BeautifulSoup(html, "html.parser")
    
    # Supprimer éléments inutiles
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside", "iframe", "form", "svg"]):
        tag.decompose()
    
    # Extraire titre
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text().strip()
    
    # Extraire H1
    h1 = ""
    h1_tag = soup.find("h1")
    if h1_tag:
        h1 = h1_tag.get_text().strip()
    
    # Chercher contenu principal
    main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|article|main", re.I))
    
    if main_content:
        paragraphs = main_content.find_all(["p", "li", "h2", "h3", "td"])
    else:
        paragraphs = soup.find_all(["p", "li", "h2", "h3"])
    
    # Extraire texte
    text_parts = []
    for p in paragraphs:
        text = p.get_text(" ", strip=True)
        if len(text) > 20:  # Ignorer les petits fragments
            text_parts.append(text)
    
    content = "\n\n".join(text_parts)
    
    # Extraire liens internes pour crawl récursif
    internal_links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full_url = urljoin(base_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc == urlparse(base_url).netloc:
            # Nettoyer l'URL (retirer fragments et params inutiles)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            internal_links.add(clean_url)
    
    return {
        "title": title,
        "h1": h1,
        "content": content,
        "links": list(internal_links),
    }


def save_as_markdown(url: str, data: Dict, site_name: str) -> Path:
    """Sauvegarde le contenu extrait en fichier Markdown"""
    site_dir = CRAWLED_DIR / site_name
    site_dir.mkdir(exist_ok=True)
    
    filename = url_to_filename(url)
    filepath = site_dir / filename
    
    # Formater en Markdown
    md_content = f"""# {data['h1'] or data['title']}

**Source**: [{url}]({url})
**Crawlé le**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

{data['content']}
"""
    
    filepath.write_text(md_content, encoding="utf-8")
    return filepath


def load_crawl_metadata() -> Dict:
    """Charge les métadonnées des crawls précédents"""
    if CRAWL_META_FILE.exists():
        try:
            return json.loads(CRAWL_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_crawl": {}, "crawled_urls": {}}


def save_crawl_metadata(metadata: Dict):
    """Sauvegarde les métadonnées de crawl"""
    CRAWL_META_FILE.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")


def should_crawl_url(url: str, config: Dict, visited: Set[str]) -> bool:
    """Vérifie si une URL doit être crawlée"""
    if url in visited:
        return False
    
    parsed = urlparse(url)
    path = parsed.path
    
    # Vérifier si le path est autorisé
    allowed = config.get("allowed_paths", [])
    if allowed:
        return any(path.startswith(allowed_path) or allowed_path in path for allowed_path in allowed)
    
    return True


def crawl_site(site_name: str, config: Dict, max_pages: Optional[int] = None) -> List[str]:
    """
    Crawle un site avec anti-détection
    
    Args:
        site_name: Nom du site (pour le dossier)
        config: Configuration du site
        max_pages: Limite de pages (override config)
    
    Returns:
        Liste des fichiers créés
    """
    print(f"\n{'='*60}")
    print(f"🕷️  Crawling {site_name.upper()}")
    print(f"{'='*60}")
    
    base_url = config["base_url"]
    start_urls = config["start_urls"]
    max_pages = max_pages or config.get("max_pages", 30)
    delay_min, delay_max = config.get("delay_range", (1.5, 3.0))
    
    # URLs à visiter (queue) et visitées
    to_visit = list(start_urls)
    visited: Set[str] = set()
    saved_files: List[str] = []
    
    # Client HTTP avec timeout
    client = httpx.Client(timeout=15.0, follow_redirects=True)
    
    try:
        page_count = 0
        
        while to_visit and page_count < max_pages:
            url = to_visit.pop(0)
            
            if url in visited:
                continue
            
            if not should_crawl_url(url, config, visited):
                continue
            
            visited.add(url)
            
            # Délai aléatoire anti-détection
            if page_count > 0:
                delay = random.uniform(delay_min, delay_max)
                print(f"   ⏳ Attente {delay:.1f}s...")
                time.sleep(delay)
            
            try:
                print(f"   📄 [{page_count+1}/{max_pages}] {url[:80]}...")
                
                # Requête avec headers aléatoires
                response = client.get(url, headers=get_random_headers())
                
                if response.status_code != 200:
                    print(f"      ⚠️ HTTP {response.status_code}")
                    continue
                
                # Extraire contenu
                data = extract_text_content(response.text, base_url)
                
                if len(data["content"]) < 100:
                    print(f"      ⚠️ Contenu trop court, ignoré")
                    continue
                
                # Sauvegarder en Markdown
                filepath = save_as_markdown(url, data, site_name)
                saved_files.append(str(filepath))
                print(f"      ✅ Sauvegardé: {filepath.name}")
                
                # Ajouter les liens internes à la queue
                for link in data["links"]:
                    if link not in visited and link not in to_visit:
                        if should_crawl_url(link, config, visited):
                            to_visit.append(link)
                
                page_count += 1
                
            except httpx.TimeoutException:
                print(f"      ⏱️ Timeout, ignoré")
            except Exception as e:
                print(f"      ❌ Erreur: {type(e).__name__}")
        
        print(f"\n   📊 Résultat: {len(saved_files)} pages sauvegardées")
        
    finally:
        client.close()
    
    return saved_files


def crawl_all_sites(sites: Optional[List[str]] = None):
    """
    Crawle tous les sites configurés (ou une sélection)
    
    Args:
        sites: Liste des sites à crawler (None = tous)
    """
    print("\n" + "="*60)
    print("🏎️  CRAWLER F1 - Début du crawling")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    metadata = load_crawl_metadata()
    all_files = []
    
    sites_to_crawl = sites or list(SITES_CONFIG.keys())
    
    for site_name in sites_to_crawl:
        if site_name not in SITES_CONFIG:
            print(f"⚠️ Site inconnu: {site_name}")
            continue
        
        config = SITES_CONFIG[site_name]
        
        try:
            files = crawl_site(site_name, config)
            all_files.extend(files)
            
            # Mettre à jour metadata
            metadata["last_crawl"][site_name] = datetime.now().isoformat()
            metadata["crawled_urls"][site_name] = len(files)
            
        except Exception as e:
            print(f"❌ Erreur crawl {site_name}: {e}")
    
    # Sauvegarder metadata
    save_crawl_metadata(metadata)
    
    print("\n" + "="*60)
    print("✅ CRAWLING TERMINÉ")
    print(f"📁 Total: {len(all_files)} fichiers créés")
    print(f"📂 Dossier: {CRAWLED_DIR}")
    print("="*60)
    
    # Conseil pour indexer
    print("\n💡 Pour indexer dans FAISS, relancez l'app ou appelez /kb/reload")
    
    return all_files


def reload_knowledge_base():
    """Recharge la Knowledge Base après crawling"""
    try:
        from backend.knowledge_base import reload_knowledge_base as kb_reload
        kb_reload()
        print("✅ Knowledge Base rechargée avec les nouveaux fichiers")
    except Exception as e:
        print(f"⚠️ Impossible de recharger la KB: {e}")
        print("   Redémarrez l'application pour prendre en compte les changements")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Crawler F1 - Récupère les données des sites F1")
    parser.add_argument("--sites", nargs="+", choices=list(SITES_CONFIG.keys()), 
                        help="Sites à crawler (défaut: tous)")
    parser.add_argument("--reload", action="store_true", 
                        help="Recharger la KB après crawling")
    
    args = parser.parse_args()
    
    # Lancer le crawl
    crawl_all_sites(args.sites)
    
    # Recharger KB si demandé
    if args.reload:
        reload_knowledge_base()
