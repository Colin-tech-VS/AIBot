from pathlib import Path
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


def main() -> Path:
    out_dir = Path("docs")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "Guide_Projet_F1_Chatbot.docx"

    sections = [
        ("Guide du Projet Chatbot F1", [
            "Vue d'ensemble: Frontend statique + backend FastAPI, LLM local via Ollama (LLaMA 3.2 3B).",
            "Architecture latency-first: routage d'intention rapide (regex), handlers FastAPI, LLM pour questions complexes, Knowledge Base locale (Markdown/CSV + FAISS), scrapers d'actualité (StandF1.com).",
        ]),
        ("Composants Clés", [
            "backend/intent_router.py: Détection d'intentions (regex/mots-clés).",
            "backend/fast_handlers.py: Handlers rapides (standings/calendrier) via scrapers avec cache.",
            "backend/f1_bot.py: Orchestration: intention → KB/news/standings → prompt → Ollama. Paramètres: OLLAMA_MODEL, RAG_ONLY, NEWS_CACHE_TTL.",
            "backend/knowledge_base.py: Chargement/recherche .md/.csv; endpoints KB (docs, search, add, reload).",
            "backend/optimized_cache.py: Cache TTL par type (news_articles, web_search, kb_search, standings).",
            "backend/optimized_prompts.py: Prompts compacts (<400 tokens), FR obligatoire, format concis avec sources.",
            "backend/optimized_ollama.py: Wrapper Ollama (température 0.2, num_predict 256, timeout 30s, streaming).",
            "app.py: FastAPI + Jinja2; endpoints /, /chat, /history, /kb/*, /health; config HOST/PORT; garde AUTO_TRAIN optionnel.",
            "frontend/: HTML/CSS/JS de la chatbox; historique et validation JSON.",
        ]),
        ("Endpoints & Flux", [
            "Endpoints: /chat (POST), /history, /clear_history, /kb/docs, /kb/search?q=..., /kb/add, /kb/reload, /health.",
            "Santé: /health vérifie Ollama et KB (ollama serve attendu sur http://127.0.0.1:11434).",
        ]),
        ("Installation & Lancement", [
            "Installer deps: pip install -r requirements.txt (chromadb optionnel).",
            "Démarrer Ollama: 'ollama serve' (daemon).",
            "Lancer backend: python app.py (ou uvicorn app:app --reload). Accès: http://localhost:8000 (ou PORT configuré).",
            "Variables: HOST, PORT, DEV_RELOAD, AUTO_TRAIN, OLLAMA_URL; fallback si port occupé.",
        ]),
        ("Knowledge Base (KB)", [
            "knowledge_base/: .md/.csv + urls.txt; sous-dossiers f1_wiki_csv par saison.",
            "Chargement récursif; recherche simple (embeddings via ChromaDB si installé, persistance dans knowledge_base/chroma/).",
            "Priorité: utiliser KB si pertinente et citer la source (📚 …).",
        ]),
        ("Routage & Intents", [
            "Cascade: 1) intention, 2) KB+news+standings, 3) prompt, 4) LLM si nécessaire.",
            "Intents: standings_drivers, standings_teams, next_race, calendar, driver_stats, team_stats.",
        ]),
        ("News & Sources", [
            "Scrapers: motorsport.com, autosport.com, actuf1.com, standf1.com, L'Équipe (Formule 1).",
            "Cache news via optimized_cache; liens explicites; attention aux changements HTML des sites.",
        ]),
        ("Prompts & LLM", [
            "Règles: FR obligatoire, concis, factuel, infos clés en gras, emojis F1 (🏎️, 🏁, 🏆), sources en Markdown.",
            "Modifier build_prompt dans f1_bot.py; ajuster paramètres dans optimized_ollama.py.",
        ]),
        ("CI & Docker", [
            "CI: .github/workflows/ci.yml (ruff, black) + requirements-dev.txt.",
            "Docker: Dockerfile (python:3.12-slim); Ollama attendu sur l'hôte (host.docker.internal:11434).",
        ]),
        ("Stabilisation & Conseils", [
            "AUTO_TRAIN: désactivé par défaut; exécuter auto_train.py seulement si présent et activé.",
            "Port fallback: si 8001 occupé, choisir un port libre.",
            "Tests conseillés: /health, /kb/reload, /kb/docs; unitaires pour parse/scrape; mocks pour appels réseau.",
        ]),
    ]

    doc = Document()
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    title_par = doc.add_paragraph()
    run = title_par.add_run("Guide du Projet Chatbot F1")
    run.bold = True
    run.font.size = Pt(20)
    title_par.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for heading, items in sections:
        doc.add_heading(heading, level=2)
        for it in items:
            p = doc.add_paragraph(it)
            p.style = doc.styles['Normal']

    doc.add_page_break()
    doc.add_paragraph("Contact & Maintenance: voir .github/copilot-instructions.md pour règles et bonnes pratiques.")

    doc.save(str(out_path))
    return out_path


if __name__ == "__main__":
    path = main()
    print(f"Fichier généré: {path}")
