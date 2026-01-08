# Instructions pour agents (GitHub Copilot / IA)

## Vue d'ensemble 🚀
- Projet: **Chatbot F1** (frontend statique + backend FastAPI) qui utilise **Ollama** (LLaMA) localement pour générer réponses, enrichi par:
  - scrapers d'actualité (motorsport, autosport, actuf1, standf1)
  - API Ergast (résultats et standings)
  - une **Knowledge Base** locale (markdown / csv) avec option **ChromaDB** pour embeddings.
- Points d'entrée : `app.py` (serveur FastAPI), `backend/f1_bot.py` (pipeline / prompt / Ollama), `backend/knowledge_base.py` (KB).

## Objectif pour un agent 🧭
- Être immédiatement productif: comprendre comment générer/modifier prompts de réponses (respecter règles F1/français), comment contrôler Ollama localement, et comment enrichir ou rechercher la KB.

---

## Composants clés & responsabilités 🔧
- `app.py`
  - Serve les pages (`/`) et fournit endpoints: `/chat`, `/history`, `/clear_history`, `/kb/*`, `/health`.
  - Gère le chemin vers `ollama.exe` (Windows-first). Démarrage utile: `python app.py` (ou `uvicorn app:app --reload`).
  - **Important**: l'app suppose qu'**Ollama** est démarré (`ollama serve`) — vérifier via `ollama --version` et `/health`.

- `backend/f1_bot.py`
  - Pipeline central qui: récupère news (scraping), récupère Ergast (stats), recherche la KB, assemble un prompt (fonction `build_prompt`) puis appelle `call_ollama`.
  - Contient des **contraintes de génération** explicites (toujours FR, prioriser KB, formatage avec **gras**, citations et emojis). Voir le bloc de prompt pour règles concrètes à appliquer/maintenir.
  - Paramètres modifiables : `OLLAMA_MODEL` (ex: `llama3.2:3b`), `OLLAMA_PATHS` et `OLLAMA_TIMEOUT`.

- `backend/knowledge_base.py`
  - Gestion des docs de connaissance. Charge par défaut des docs embarquées et peut charger fichiers `.md` et `.csv` du dossier `knowledge_base/`.
  - Optionnel: si `chromadb` est installé, active recherche basée sur embeddings (persist directory: `knowledge_base/chroma`).
  - API utiles : `get_knowledge_base().search(q)` et endpoints HTTP `/kb/docs`, `/kb/search`, `/kb/add`, `/kb/reload`.

---

## Workflows et commandes pratiques ✅
- Installation : `pip install -r requirements.txt` (installer `chromadb` si embeddings requis)
- Lancement Ollama local :
  - Démarrer le daemon local: `ollama serve` (obligatoire avant usage)
  - Vérifier : `ollama --version` ou `GET /health` (retourne `ollama_available`).
- Lancer le backend :
  - `python app.py` (exécute uvicorn, `reload=True`) ou `uvicorn app:app --reload`
- Vérifier KB et endpoints :
  - Lister docs : `GET /kb/docs`
  - Recharger fichiers markdown CSV : `POST /kb/reload`
  - Ajouter doc via API : `POST /kb/add` (payload: `doc_id,title,content,category`)
- Débogage rapide : consulter logs (print/debug) ; erreurs Ollama renvoyent des chaînes commençant par `[ERREUR]` ou `❌`.

---

## Conventions projet (à respecter par un agent) ⚠️
- **Langue**: toujours **FRANÇAIS** pour les réponses utilisateur (le prompt l’exige). Si sortie en anglais, pipeline tente une traduction via _LLM_.
- **Priorité**: la **Knowledge Base** prime — si un doc répond, l’utiliser et le citer (`📚 …`).
- **Format**: réponses concises, factuelles, avec **gras** pour infos clés, emojis F1 (🏎️, 🏁, 🏆), et citations de source avec lien Markdown `[texte](url)`.
- **Ne pas inventer**: si incertain, indiquer explicitement `"Je n'ai pas confirmé"`.
- **Prompts**: modifier les règles globales en éditant `build_prompt` dans `backend/f1_bot.py` (ex: étendre contraintes, ajouter exemples).

---

## Points d'intégration externes & effets secondaires 🌐
- **Ollama** (local) : dépendance système; chemin configurable dans `OLLAMA_PATHS` (Windows). Si absent, tests/flows fallback vers KB.
- **Ergast API** : données temps réel pour résultats et standings — code contient cache TTL 5 minutes.
- **Sites d'actu**: scrapers pour `motorsport.com`, `autosport.com`, `actuf1.com`, `standf1.com` — fragile à changements structurels (tests E2E ou isolation recommandés).
- **ChromaDB** : optionnelle; installez `chromadb` pour activer embeddings. Persistence path: `knowledge_base/chroma`.

---

## Exemples concrets (où chercher/modifier) 🔎
- Pour changer le modèle Ollama : éditer `backend/f1_bot.py` → `OLLAMA_MODEL = "llama3.2:3b"`.
- Pour ajuster la règle « répondre toujours en FR » : éditer le bloc `build_prompt` (voir les instructions textuelles détaillées dans `f1_bot.py`).
- Pour ajouter une donnée persistante : créer un `.md` dans `knowledge_base/` puis `POST /kb/reload`.

---

## Tests & sécurité (observations)
- Aucune suite de tests détectée — privilégier tests manuels d'API locales (`/health`, `/chat`, `/kb/*`) et tests unitaires pour fonctions de parsing/scraping.
- Faire attention aux appels réseau (scraping, Ergast) : isoler via mocks lors de tests unitaires.

---

Si un point est incomplet ou tu veux que j'ajoute des exemples de PR (format, checklist) ou des instructions de tests automatisés, dis-le et j'itère rapidement. 🔧