"""🏎️ Scraper Motorsport.com/fr/f1/news"""
from backend.scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup
from typing import List, Dict, Optional


class MotorsportScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="motorsport",
            base_url="https://fr.motorsport.com/f1/news/"
        )
    
    def get_article_urls(self) -> List[str]:
        """📰 Récupérer URLs derniers articles F1"""
        soup = self.fetch_html(self.base_url)
        if not soup:
            return []
        
        urls = []
        seen = set()
        
        # Multi-sélecteurs pour robustesse (Motorsport change souvent)
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Filtrer uniquement articles F1 (pas la page d'accueil)
            if '/f1/news/' in href and href != '/f1/news/' and href not in seen:
                # Construire URL complète
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = f"https://fr.motorsport.com{href}"
                else:
                    continue
                
                # Vérifier que c'est un article (contient un slug après /news/)
                if full_url.count('/') > 5:  # URL article a plus de segments
                    urls.append(full_url)
                    seen.add(href)
        
        return urls[:20]  # Limiter à 20
    
    def parse_article(self, soup: BeautifulSoup, url: str) -> Optional[Dict]:
        """🔍 Parser article Motorsport"""
        try:
            # Multi-fallback sélecteurs (Motorsport utilise classes Tailwind dynamiques)
            title_elem = (
                soup.find('h1', class_=lambda x: x and 'msnt-heading' in str(x)) or
                soup.select_one('h1[class*="text-7"]') or
                soup.select_one('h1.ms-title') or
                soup.find('h1')
            )
            
            # Chercher contenu article (plusieurs formats possibles)
            content_elem = (
                soup.find('div', class_=lambda x: x and 'article' in str(x).lower()) or
                soup.select_one('div.ms-article_content') or
                soup.find('article') or
                soup.find('div', {'id': lambda x: x and 'article' in str(x).lower()})
            )
            
            # Si pas de div article, chercher tous les paragraphes après le titre
            if not content_elem and title_elem:
                # Récupérer tous les <p> suivant le titre
                paragraphs = []
                for elem in title_elem.find_all_next(['p', 'div']):
                    if elem.name == 'p':
                        text = elem.get_text(strip=True)
                        if len(text) > 50:  # Ignorer paragraphes trop courts
                            paragraphs.append(text)
                    if len(paragraphs) >= 5:  # Limiter à 5 premiers paragraphes
                        break
                
                if paragraphs:
                    content_text = ' '.join(paragraphs)
                else:
                    return None
            else:
                if not content_elem:
                    return None
                
                # Nettoyer contenu (enlever pubs, images, scripts)
                for unwanted in content_elem.select('script, style, .ad, .advertisement, figure, nav, aside'):
                    unwanted.decompose()
                
                content_text = content_elem.get_text(separator=' ', strip=True)
            
            # Chercher date
            date_elem = soup.find('time', datetime=True)
            
            # Validation minimale
            if not title_elem:
                return None
            
            title_text = title_elem.get_text(strip=True)
            
            # Filtrer titres vides ou trop courts
            if len(title_text) < 10 or len(content_text) < 100:
                return None
            
            # Limiter taille (max 1500 caractères pour KB)
            if len(content_text) > 1500:
                content_text = content_text[:1497] + "..."
            
            return {
                "title": title_text,
                "content": content_text,
                "url": url,
                "date": date_elem.get('datetime') if date_elem else None,
                "source": "motorsport.com",
                "type": "news"
            }
        
        except Exception as e:
            return None
