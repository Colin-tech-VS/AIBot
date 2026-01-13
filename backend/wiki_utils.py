from typing import Optional
import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

WIKI_API_BASE = "https://en.wikipedia.org/w/api.php"


def normalize_wiki_title_from_dir(dir_name: str) -> str:
    """Convertit un nom de dossier type '2004_formula_one_season' en '2004_Formula_One_season'."""
    if not dir_name:
        return ""
    parts = dir_name.split("_")
    normalized = []
    for p in parts:
        if p.lower() == "formula":
            normalized.append("Formula")
        elif p.lower() == "one":
            normalized.append("One")
        elif p.lower() == "season":
            normalized.append("season")
        else:
            # Capitaliser l'année reste telle quelle; mots: capitalisation titre
            normalized.append(p.capitalize() if not p.isdigit() else p)
    return "_".join(normalized)


def build_wiki_url_from_title(title: str, language: str = "en") -> str:
    if not title:
        return ""
    return f"https://{language}.wikipedia.org/wiki/{title}"


def fetch_wiki_extract_by_title(title: str, sentences: int = 4) -> Optional[str]:
    """Récupère un extrait plaintext court pour une page donnée."""
    if not title:
        return None
    try:
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": 1,
            "exsentences": sentences,
            "exlimit": 1,
            "titles": title,
        }
        resp = httpx.get(WIKI_API_BASE, params=params, headers=HEADERS, timeout=5, follow_redirects=True)  # Timeout réduit 8s→5s
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for _, page in pages.items():
            extract = page.get("extract")
            if extract:
                return extract.strip()
        return None
    except Exception:
        return None
