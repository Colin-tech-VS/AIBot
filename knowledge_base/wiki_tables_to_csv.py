# wiki_tables_to_csv.py
# Usage: python wiki_tables_to_csv.py
# Exporte toutes les tables HTML des URLs listées dans urls.txt (1 URL par ligne)

from __future__ import annotations
import re
import time
from pathlib import Path

import httpx
import pandas as pd


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,fr-FR;q=0.8,fr;q=0.7",
}


def safe_name(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower()
    return s[:140] if s else "page"


def fetch_html(url: str, timeout: int = 30) -> str:
    r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    status = r.status_code

    # Erreurs typiques quand Wikipedia rate-limit
    if status in (429, 503):
        raise RuntimeError(
            f"Rate-limited / temporaire ({status}) sur {url}\n"
            f"➡️ Augmente la pause (SLEEP_SECONDS) et relance."
        )

    r.raise_for_status()
    html = r.text

    # Debug rapide
    table_count = html.lower().count("<table")
    if table_count == 0:
        raise ValueError(
            f"Aucune balise <table> détectée sur {url} (status {status}). "
            f"Possible page erreur/redirect/anti-bot."
        )

    return html


def export_tables_from_url(url: str, outdir: Path, export_wikitable_only: bool = True) -> None:
    page_slug = safe_name(url.split("/wiki/")[-1] if "/wiki/" in url else url)
    page_dir = outdir / page_slug
    page_dir.mkdir(parents=True, exist_ok=True)

    try:
        html = fetch_html(url)
    except Exception as e:
        # Sauvegarde une page debug pour inspection
        debug_file = page_dir / "debug_no_table_or_error.html"
        try:
            # Si on a quand même une réponse partielle, on la dump
            if isinstance(e, ValueError) or isinstance(e, RuntimeError):
                # on n'a pas forcément html ici
                pass
        except Exception:
            pass
        raise

    # Sauvegarde HTML (utile si besoin de comprendre)
    (page_dir / "source.html").write_text(html, encoding="utf-8")

    # 1) Toutes les tables
    try:
        tables_all = pd.read_html(html)
    except Exception as e:
        raise RuntimeError(f"pd.read_html a échoué sur {url} : {e}")

    for i, df in enumerate(tables_all, start=1):
        df.to_csv(page_dir / f"table_all_{i:02d}.csv", index=False, encoding="utf-8")

    # 2) Bonus: seulement les wikitable (souvent ce que tu veux sur Wikipedia)
    if export_wikitable_only:
        try:
            tables_wiki = pd.read_html(html, attrs={"class": "wikitable"})
            for i, df in enumerate(tables_wiki, start=1):
                df.to_csv(page_dir / f"table_wikitable_{i:02d}.csv", index=False, encoding="utf-8")
        except ValueError:
            # aucune table wikitable, pas grave
            pass


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    urls_file = base_dir / "urls.txt"
    outdir = base_dir / "f1_wiki_csv"
    outdir.mkdir(exist_ok=True)

    if not urls_file.exists():
        raise FileNotFoundError(f"urls.txt introuvable ici: {urls_file}")

    urls = []
    for line in urls_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)

    if not urls:
        raise SystemExit("urls.txt est vide. Mets 1 URL par ligne.")

    print(f"📄 {len(urls)} URL(s) trouvée(s) dans {urls_file}")
    print(f"📁 Export CSV vers: {outdir}\n")

    for idx, url in enumerate(urls, start=1):
        print(f"[{idx}/{len(urls)}] {url}")
        try:
            export_tables_from_url(url, outdir, export_wikitable_only=True)
            print("  ✅ OK\n")
        except Exception as e:
            # On continue sur les autres URLs au lieu de tout stopper
            print(f"  ❌ ERREUR: {e}\n")

        time.sleep(SLEEP_SECONDS)

    print("Terminé ✅")


# Mets 3 à 8 secondes si tu as des 429/503
SLEEP_SECONDS = 4


if __name__ == "__main__":
    main()
