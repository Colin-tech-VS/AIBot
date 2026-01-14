# Instructions pour agents (GitHub Copilot / IA)

## Vue d'ensemble 🚀
**Chatbot F1** (frontend statique + backend FastAPI) : chatbot conversationnel sur la Formule 1 qui utilise **Ollama** (Qwen 2.5 3B) localement pour générer des réponses. Architecture hybride **latency-first** combinant :
- **Routage d'intention** (regex) → handlers rapides (<100ms) pour questions simples (classements, calendrier)
- **LLM pour questions complexes** (stratégies, historique, analyses)
- **Knowledge Base** locale (markdown/CSV + FAISS pour embeddings)
- Scrapers d'actualité (standf1.com, lequipe.fr, FIA)
- API Ergast (résultats, standings, calendrier)

**Points d'entrée clés** : `app.py` (FastAPI), `backend/f1_bot.py` (orchestration), `backend/intent_router.py` (routage sans-LLM), `backend/knowledge_base.py` (KB).

## Objectif pour un agent 🧭
Être immédiatement productif en comprenant : la **cascade de routage** (intention → handler → cache → LLM), comment **modifier prompts** et **contraintes de réponse** (français obligatoire), comment étendre la **Knowledge Base**, et comment optimiser les **paramètres Ollama**.

---

## Composants clés & responsabilités 🔧

### Routage et orchestration
- **`backend/intent_router.py`**  
  - Détecte intentions via **regex + mots-clés** sans LLM (~10ms). Retourne `Intent` (nom, handler, confiance, `requires_llm`).
  - Patterns clés : `standings_drivers`, `standings_teams`, `next_race`, `calendar`, `driver_stats`, `team_stats`.
  - **Pattern importé** dans `fast_handlers.py` et `f1_bot.py`.

- **`backend/fast_handlers.py`**  
  - Handlers ultra-rapides (<100ms) pour questions sans-LLM: `F1DataHandler.get_standings()`, etc.
  - Consulte **Ergast API** (avec cache) et retourne résultats formatés.
  - Sert de **fallback** quand confiance d'intention est haute et pas d'ambiguïté.

- **`backend/f1_bot.py`** (orchestration centrale)  
  - Fonction `answer_f1_question(question)` : route la question selon intention + contenu.  
  - **Cascade logique** : 1) Détecter intention → 2) Chercher KB + news + Ergast → 3) Builder prompt → 4) Appeler Ollama si nécessaire.
  - Paramètres modifiables : `OLLAMA_MODEL`, `RAG_ONLY` (force Knowledge Base seule), `NEWS_CACHE_TTL`, `ERGAST_CACHE_TTL`.

### Caching et performance
- **`backend/optimized_cache.py`**  
  - Cache local avec **TTL per-type** (`CACHE_TTL` dict : `ergast_standings`, `ergast_race`, `ergast_schedule`, `news`).  
  - Classe `OptimizedCache` : `get(key)`, `set(key, value, ttl_seconds)`, stats (hits/misses).
  - **Usage** : `from backend.optimized_cache import get_cache; cache = get_cache()`.

### Prompt et LLM
- **`backend/optimized_prompts.py`**  
  - `OptimizedPromptBuilder` : construire prompts avec règles de sécurité anti-jailbreak.  
  - Méthodes : `build_f1_question()` (standings + news + KB + mémoire), `build_kb_question()` (KB seule).
  - **Règles implicites** : français obligatoire, gras pour clés, emojis F1, citations de source, anti-jailbreak.

- **Configuration Ollama** (dans `f1_bot.py`)  
  - `OLLAMA_MODEL = "qwen2.5:3b"` — modèle rapide et performant.  
  - `OLLAMA_TIMEOUT = 15` — timeout ultra-rapide (15s).  
  - Détecte chemin ollama.exe (Windows/macOS/Linux) via `OLLAMA_PATHS`.

### Knowledge Base
- **`backend/knowledge_base.py`**  
  - Charge fichiers `.md` et `.csv` du dossier `knowledge_base/`.  
  - Classe `KnowledgeBase` : `search(q)` avec embeddings FAISS (sentence-transformers).  
  - **Index FAISS** : ~5500 vecteurs, dimension 384, persisté localement.  
  - API HTTP via `app.py` : `/kb/docs`, `/kb/search?q=...`, `/kb/add`, `/kb/reload`.

### Frontend & server
- **`app.py`** (FastAPI + Jinja2)  
  - Serve pages statiques (`/`), expose endpoints `/chat`, `/history`, `/clear_history`, `/kb/*`, `/health`.  
  - Gère paths multiplateforme Ollama (Windows → `AppData\Local\Programs\Ollama\ollama.exe`).  
  - **Important** : suppose Ollama démarré en daemon (`ollama serve`) sur `http://127.0.0.1:11434`.

- **`frontend/` (HTML/CSS/JS)**  
  - Chatbox simple, affiche historique, valide JSON responses.

## Workflows et commandes pratiques ✅
- **Installation** : `pip install -r requirements.txt` (+ `chromadb` optionnel pour embeddings).
- **Lancer Ollama** : `ollama serve` (daemon, obligatoire). Vérifier : `ollama --version` ou `GET /health`.
- **Lancer backend** : `python app.py` (ou `uvicorn app:app --reload`). Accès : `http://localhost:8001` (fallback: 8002).
- **Tests endpoints** :
  - `/health` → statut Ollama + KB.
  - `/chat` → POST `{"message": "..."}`.
  - `/kb/docs` → liste des docs KB.
  - `/kb/search?q=...` → recherche KB.
  - `/kb/reload` → recharge fichiers `.md/.csv` depuis disque.
- **Débogage** : logs en stdout (print/debug) ; erreurs Ollama commencent par `[ERREUR]` ou `❌`.

---

## Conventions projet (à respecter par un agent) ⚠️
- **Langue**: toujours **FRANÇAIS** pour les réponses utilisateur (le prompt l’exige). Si sortie en anglais, pipeline tente une traduction via _LLM_.
- **Priorité**: la **Knowledge Base** prime — si un doc répond, l’utiliser et le citer (`📚 …`).
- **Format**: réponses concises, factuelles, avec **gras** pour infos clés, emojis F1 (🏎️, 🏁, 🏆), et citations de source avec lien Markdown `[texte](https://exemple.com)`.
- **Ne pas inventer**: si incertain, indiquer explicitement `"Je n'ai pas confirmé"`.
- **Prompts**: modifier les règles globales en éditant `build_prompt` dans `backend/f1_bot.py` (ex: étendre contraintes, ajouter exemples).

---

## Points d'intégration externes & effets secondaires 🌐
- **Ollama** (local) : dépendance système; chemin configurable dans `OLLAMA_PATHS` (f1_bot.py). Si absent, tests/flows fallback vers KB.
- **Ergast API** : données temps réel pour résultats et standings — code contient cache TTL 5 minutes.
- **Sites d'actu**: scrapers pour `standf1.com`, `lequipe.fr/Formule-1`, FIA (calendrier + règlements) — fragile à changements structurels.
- **FAISS** : index vectoriel pour recherche sémantique dans la Knowledge Base (~5500 vecteurs).

---

## Exemples concrets (où chercher/modifier) 🔎
- Pour changer le modèle Ollama : éditer `backend/f1_bot.py` → `OLLAMA_MODEL = "qwen2.5:3b"` (actuel).
- Pour ajuster la règle « répondre toujours en FR » : éditer le bloc `build_prompt` (voir les instructions textuelles détaillées dans `f1_bot.py`).
- Pour ajouter une donnée persistante : créer un `.md` dans `knowledge_base/` puis `POST /kb/reload`.

---

## Tests & sécurité (observations)
- Aucune suite de tests détectée — privilégier tests manuels d'API locales (`/health`, `/chat`, `/kb/*`) et tests unitaires pour fonctions de parsing/scraping.
- Faire attention aux appels réseau (scraping, Ergast) : isoler via mocks lors de tests unitaires.

---

Si un point est incomplet ou tu veux que j'ajoute des exemples de PR (format, checklist) ou des instructions de tests automatisés, dis-le et j'itère rapidement. 🔧