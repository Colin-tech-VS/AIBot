# 🏎️ F1 Chatbot - Assistant Conversationnel Formule 1

Chatbot intelligent sur la Formule 1 utilisant **Ollama Qwen 2.5 7B** localement, avec Knowledge Base vectorielle et routage d'intention optimisé pour des réponses rapides et précises.

## ✨ Fonctionnalités

### 🚀 **Performance Hybride**
- **Routage d'intention** (regex) → Réponses <100ms pour questions simples
- **LLM local** (Ollama Qwen 2.5 7B) → Analyses complexes et conversations naturelles
- **Cache intelligent** → TTL adaptatif (300-1800s selon type)
- **Temperature variable** → 0.15 FAQ / 0.35 Actualités

### 📚 **Knowledge Base Avancée**
- **7983 chunks FAISS** indexés (2233 documents, 2010 base + 223 crawled)
- **Recherche sémantique** → min_score: 0.45 (précision industrie)
- **Sources** : Markdown, CSV, données Wikipedia historiques F1 (1950-2024)
- **Chunking** : RecursiveCharacterTextSplitter (600 tokens, overlap=100)

### 🔒 **Sécurité 2 Niveaux**
- **Niveau 1** : Validation input (23 patterns regex anti-injection)
- **Niveau 2** : Instructions anti-jailbreak in-prompt (protection LLM)
- **Protection** : ~70% des attaques bloquées (prompt injection, bypass langue, extraction)

### 🧠 **Mémoire & Contexte**
- **Mémoire long terme** : Faits appris + préférences utilisateur
- **Historique conversationnel** : Contexte des échanges
- **Apprentissage automatique** : Extraction LLM des faits pertinents

### 📰 **Données Temps Réel**
- **Crawlers optimisés** : 2x par jour (06:00 + 18:00 UTC) → articles max 12h
- **Sources** : motorsport.com, autosport.com, actuf1.com, standf1.com
- **API Ergast** : Résultats officiels, classements, calendrier
- **Web Search proactif** : Automatique pour questions actualités
- **News caching** : TTL variable (1800s pour news)

### 🔐 **Authentification**
- **JWT tokens** (bcrypt + PyJWT)
- **Base SQLite** : Gestion utilisateurs
- **Synchronisation conversations** multi-appareils

---

## 🛠️ Installation

### Prérequis

1. **Python 3.10+**
2. **Ollama** installé ([ollama.com](https://ollama.com))
   ```bash
   # Installer Ollama puis télécharger le modèle
   ollama pull qwen2.5:7b
   ```

### Installation Rapide

```bash
# 1. Cloner le repo
git clone https://github.com/VOTRE_USERNAME/AIBot.git
cd AIBot

# 2. Créer environnement virtuel
python -m venv chatbot
chatbot\Scripts\activate  # Windows
# source chatbot/bin/activate  # Linux/macOS

# 3. Installer dépendances
pip install -r requirements.txt

# 4. Lancer Ollama en daemon
ollama serve

# 5. Lancer le serveur (dans un autre terminal)
python app.py
```

Accéder à l'application : **http://localhost:8001**

---

## 📂 Structure du Projet

```
AIBot/
├── app.py                      # Point d'entrée FastAPI
├── requirements.txt            # Dépendances Python
├── backend/
│   ├── f1_bot.py              # Orchestration centrale (answer_f1_question)
│   ├── intent_router.py       # Détection intention sans LLM
│   ├── fast_handlers.py       # Handlers rapides (<100ms)
│   ├── knowledge_base.py      # FAISS + embeddings
│   ├── optimized_prompts.py   # Prompt builder + mémoire
│   ├── optimized_cache.py     # Cache TTL intelligent
│   ├── optimized_ollama.py    # Wrapper Ollama
│   ├── input_validator.py     # Sécurité Niveau 1
│   ├── long_term_memory.py    # Mémoire persistante
│   ├── standings_utils.py     # Scrapers classements
│   ├── logger.py              # Logging structuré
│   └── auth/                  # Authentification JWT
├── frontend/
│   ├── index.html             # Interface chat
│   └── static/                # CSS + JS
├── knowledge_base/
│   ├── *.md                   # Documents KB (FAQ, règles, glossaire)
│   └── f1_wiki_csv/           # Données Wikipedia (1950-2024)
├── memory/
│   ├── learned_facts.json     # Faits appris
│   └── user_preferences.json  # Préférences utilisateurs
└── logs/
    └── f1_bot.log             # Logs rotatifs (10 MB max)
```

---

## 🎯 Utilisation

### Questions Supportées

**Classements & Résultats**
```
"Classement pilotes 2024"
"Qui a gagné Monaco ?"
"Résultats du dernier GP"
```

**Actualités**
```
"Dernières news F1"
"Actualités Red Bull"
```

**Règles & Technique**
```
"C'est quoi le DRS ?"
"Explique la règle des pénalités"
"Différence entre hard et soft"
```

**Historique**
```
"Combien de titres pour Hamilton ?"
"Meilleur pilote des années 2000"
```

**Conversationnel**
```
"Parle-moi de Verstappen"
"Pourquoi Ferrari est en difficulté ?"
"Compare Hamilton et Schumacher"
```

### Commandes API

**Chat**
```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Qui a gagné le championnat 2024?", "conversation_id": "user123"}'
```

**Health Check**
```bash
curl http://localhost:8001/health
```

**Knowledge Base Search**
```bash
curl "http://localhost:8001/kb/search?q=DRS"
```

---

## ⚙️ Configuration

### Variables d'Environnement

```bash
# .env (optionnel)
OLLAMA_MODEL=qwen2.5:7b
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
AUTO_TRAIN=0            # Désactiver auto-learning
```

### Paramètres Modifiables

**Cache TTL** (`backend/optimized_cache.py`)
```python
CACHE_TTL = {
    "news": 600,              # 10 min
    "kb_search": 1200,        # 20 min
    "ergast_standings": 1800  # 30 min
}
```

**Modèle LLM** (`backend/f1_bot.py`)
```python
OLLAMA_MODEL = "qwen2.5:7b"  # Changer modèle ici
```

**Sécurité Niveau 1** (`backend/input_validator.py`)
```python
BANNED_PATTERNS = [
    r"ignore.*instructions",
    r"system:",
    # Ajouter patterns ici
]
```

---

## 🧪 Tests

```bash
# Test sécurité Niveau 1 (input validator)
python test_input_validator.py

# Test sécurité Niveau 2 (anti-jailbreak) - serveur requis
python test_level2_live.py

# Test Knowledge Base
python test_faiss.py
```

---

## 🏗️ Architecture Technique

### Pipeline de Réponse

```
Question utilisateur
    ↓
[Input Validator] (Niveau 1)
    ↓
[Intent Router] (regex - <10ms)
    ↓
    ├─→ [Fast Handler] (classements/calendrier) → Cache → Réponse
    ├─→ [KB Search] (FAISS) → Top-K chunks
    ├─→ [Scrapers] (actualités) → Cache
    └─→ [Ollama LLM] (Niveau 2 anti-jailbreak)
            ↓
        Réponse finale
            ↓
    [Long-term Memory] (apprentissage)
```

### Stack Technique

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| **Backend** | FastAPI + Uvicorn | API REST |
| **LLM** | Ollama Qwen 2.5 7B | Génération réponses |
| **Embeddings** | sentence-transformers | Vectorisation sémantique |
| **Vector DB** | FAISS (CPU) | Recherche similarité |
| **Chunking** | LangChain RecursiveTextSplitter | Découpage documents |
| **Cache** | Custom TTL cache | Performance |
| **Auth** | JWT + bcrypt | Sécurité utilisateurs |
| **Logging** | RotatingFileHandler | Traçabilité |
| **Scraping** | BeautifulSoup4 + requests | Actualités |

---

## 📊 Performance

| Métrique | Valeur |
|----------|--------|
| **Latence moyenne** | 2-8s (selon scraping) |
| **Questions simples** | <100ms (handlers rapides) |
| **KB search** | ~200ms (FAISS 5551 vecteurs) |
| **Cache hit rate** | ~60-70% (après warm-up) |
| **Taille index FAISS** | ~8 MB (5551 vecteurs 384-dim) |
| **Mémoire runtime** | ~2 GB (sentence-transformers) |

---

## 🔐 Sécurité

### Protections Implémentées

✅ **Niveau 1 - Pre-LLM** (70% efficace)
- Validation input (23 regex patterns)
- Blocage keywords malicieux
- Max length 2000 chars

✅ **Niveau 2 - In-Prompt** (60% efficace)
- Instructions anti-jailbreak explicites
- Refus révélation prompt
- Langue française forcée
- Interdiction invention données

⚠️ **Limitations Connues**
- Prompt révélation possible (~40% attaques sophistiquées)
- Recommandé : Niveau 3 (output filtering) pour prod

### Tests Sécurité

```bash
# Validation complète (5 scénarios)
python test_level2_live.py
# Résultat actuel : 3/5 tests passent (60%)
```

---

## 🚧 Limitations & TODO

### Limitations Actuelles
- ⚠️ **Latence** : 8s max (scrapers synchrones)
- ⚠️ **Sécurité** : 60-70% protection (prompt leakage possible)
- ⚠️ **Tests** : 0 tests pytest (régression risquée)
- ⚠️ **Scrapers** : Fragiles (dépendent structure HTML externe)

### Roadmap
- [ ] **Async scrapers** → Réduire latence à 2-3s
- [ ] **Tests pytest** → Couverture 80%+ (KB, routing, cache)
- [ ] **Niveau 3 sécurité** → Output filtering regex
- [ ] **Rate limiting** → Éviter ban IP scrapers
- [ ] **Frontend amélioré** → Markdown rendering (marked.js)

---

## 📝 Licence

MIT License - Voir [LICENSE](LICENSE) pour détails.

---

## 🤝 Contribution

Contributions bienvenues ! Ouvrir une issue ou PR sur GitHub.

**Développé avec ❤️ pour les fans de F1** 🏁
