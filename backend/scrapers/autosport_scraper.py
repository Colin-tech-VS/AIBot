"""🏎️ Scraper Autosport.com/f1/news"""
from backend.scrapers.base_scraper import BaseScraper
from bs4 import BeautifulSoup
from typing import List, Dict, Optional


class AutosportScraper(BaseScraper):
    def __init__(self):
        super().__init__(
            source_name="autosport",
            base_url="https://www.autosport.com/f1/news"
        )
    
    def get_article_urls(self) -> List[str]:
        """📰 Récupérer URLs derniers articles F1"""
        soup = self.fetch_html(self.base_url)
        if not soup:
            return []
        
        urls = []
        seen = set()
        
        # Chercher tous les liens dans les éléments ms-item (détecté par le test)
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Filtrer uniquement articles F1
            if any(pattern in href.lower() for pattern in ['/f1/', '/formula-1/', '/news/']):
                # Exclure navigation/pagination
                if any(exclude in href.lower() for exclude in ['#', 'page=', 'category', 'tag', '/f1/news', '/f1$']):
                    continue
                
                # Construire URL complète
                if href.startswith('http'):
                    full_url = href
                elif href.startswith('/'):
                    full_url = f"https://www.autosport.com{href}"
                else:
                    continue
                
                # Dédupliquer
                if full_url not in seen and full_url.count('/') > 4:  # URL article valide
                    urls.append(full_url)
                    seen.add(full_url)
        
        return urls[:20]  # Limiter à 20 articles
    
    def parse_article(self, soup: BeautifulSoup, url: str) -> Optional[Dict]:
        """🔍 Parser article Autosport"""
        try:
            # Chercher titre (test a confirmé h1/h2)
            title_elem = soup.find('h1') or soup.find('h2')
            
            # Chercher date (test a confirmé balise time avec datetime)
            date_elem = soup.find('time')
            date_text = None
            if date_elem:
                date_text = date_elem.get('datetime') or date_elem.get_text(strip=True)
            
            # Chercher contenu article (plusieurs stratégies)
            content_elem = None
            for selector in ['article', 'div[class*="content"]', 'div[class*="body"]', 'main']:
                content_elem = soup.select_one(selector)
                if content_elem:
                    break
            
            # Extraire paragraphes
            content_text = ""
            if content_elem:
                # Nettoyer éléments indésirables
                for unwanted in content_elem.select('script, style, .ad, .advertisement, figure, nav, aside, .related, .share'):
                    unwanted.decompose()
                
                paragraphs = content_elem.find_all('p')
                content_paragraphs = []
                
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    # Filtrer paragraphes courts ou vides
                    if len(text) > 50:
                        content_paragraphs.append(text)
                
                content_text = '\n\n'.join(content_paragraphs)
            
            # Validation minimale
            if not title_elem:
                return None
            
            title_text = title_elem.get_text(strip=True)
            
            # Filtrer si titre trop court ou contenu insuffisant
            if len(title_text) < 10 or len(content_text) < 200:
                return None
            
            # Limiter taille (max 1500 caractères pour KB)
            if len(content_text) > 1500:
                content_text = content_text[:1497] + "..."
            
            return {
                "title": title_text,
                "content": content_text,
                "url": url,
                "date": date_text,
                "source": "autosport.com",
                "type": "news"
            }
        
        except Exception as e:
            return None
