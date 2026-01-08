# 🤖 Chatbot Ollama Local - Projet Complet

Chatbot Python 100% local avec **FastAPI**, **Ollama (LLaMA2)**, et frontend minimal HTML/JS.

## 📁 Structure du Projet

```
.
├── backend/
│   └── main.py              # Backend FastAPI + Ollama
├── frontend/
│   ├── templates/
│   │   └── index.html       # UI Jinja2
│   └── static/
│       ├── css/
│       │   └── style.css    # Styles modernes
│       └── js/
│           └── app.js       # Client JavaScript
├── requirements.txt         # Dépendances Python
└── README.md               # Ce fichier
```

## 🚀 Démarrage Rapide

### 1️⃣ Pré-requis

- **Python 3.8+**
- **Ollama installé** : https://ollama.ai
- Le modèle **llama2** téléchargé (première exécution télécharge ~4GB)

Vérifier Ollama :
```bash
ollama --version
```

### 2️⃣ Installation des Dépendances

```bash
pip install -r requirements.txt
```

### 3️⃣ Lancer Ollama (Terminal séparé)

```bash
ollama serve
```

Laisse ce terminal ouvert. Ollama écoute sur http://127.0.0.1:11434

### 4️⃣ Lancer le Backend FastAPI

```bash
cd backend
python main.py
```

Vous verrez :
```
============================================================
🤖 Chatbot Ollama Local - Backend FastAPI
============================================================
📁 Templates: .../frontend/templates
📁 Static: .../frontend/static
🚀 Lancement sur http://127.0.0.1:8000
⚠️  Assurez-vous qu'Ollama est lancé: ollama serve
============================================================
```

### 5️⃣ Ouvrir le Chatbot

Accédez à : **http://127.0.0.1:8000**

## 📌 Fonctionnalités

✅ **Frontend Réactif**
- Interface de chat minimaliste et moderne
- Support du dark mode automatique
- Animations fluides
- Responsive design

✅ **Backend FastAPI**
- Route `POST /chat` pour traiter les messages
- Route `GET /history` pour récupérer l'historique
- Route `POST /clear_history` pour réinitialiser
- Route `GET /health` pour vérifier l'état d'Ollama
- Historique stocké en mémoire
- Gestion des erreurs Ollama

✅ **Intégration Ollama**
- Appel subprocess vers `ollama run llama2`
- Timeout de 120s par défaut
- Détection d'erreurs (Ollama absent, timeout, etc.)

✅ **Communication Complète**
- Frontend → Backend (fetch POST)
- Backend → Ollama (subprocess)
- Ollama → Backend → Frontend (WebAPI)

## 🔧 Architecture

### Backend (FastAPI)

```python
# POST /chat
{
  "message": "Bonjour!"
}

# Réponse
{
  "user_message": "Bonjour!",
  "bot_response": "Bonjour! Comment allez-vous?",
  "history": [...]
}
```

### Frontend (HTML + Vanilla JS)

- **Fetch API** pour communiquer avec le backend
- Pas de framework JS (jQuery, React, Vue, etc.)
- Event listeners simples
- DOM manipulation natif

### Ollama (subprocess)

```python
subprocess.run(["ollama", "run", "llama2", prompt])
```

## 📝 Exemple d'Utilisation

1. Ouvrir http://127.0.0.1:8000
2. Taper : "Explique-moi ce qu'est l'IA en 3 lignes"
3. Cliquer "Envoyer" (ou Enter)
4. Attendre la réponse de LLaMA2
5. Continuer la conversation

## ⚠️ Points Importants

### Première Utilisation
- LLaMA2 sera téléchargé automatiquement (~4GB)
- La première réponse peut prendre 1-2 minutes
- Les réponses suivantes sont plus rapides

### Timeout
- Défaut : 120 secondes par message
- Éditable dans `backend/main.py` : `timeout=120`

### Port 8000
- Si occupé, modifier dans `backend/main.py` : `port=8001`

### Historique
- Stocké en mémoire (réinitialisation au restart)
- Pour persister, modifier `backend/main.py` pour utiliser une base de données

## 🛠️ Personnalisation

### Changer le Modèle
Dans `backend/main.py`, remplacer `llama2` par :
```python
# Autres modèles disponibles
# - mistral
# - neural-chat
# - starling-lm
# - etc.

subprocess.run(["ollama", "run", "mistral", prompt])
```

### Ajouter un Endpoint API
```python
@app.post("/api/custom")
async def custom_endpoint(data: SomeModel):
    # Votre logique
    return {"result": "..."}
```

### Modifier les Styles
Éditer `frontend/static/css/style.css`

### Ajouter des Commandes JS
Ajouter dans `frontend/static/js/app.js`

## 🐛 Troubleshooting

### "Ollama n'est pas installé"
```bash
# Installer Ollama
# Windows/Mac : https://ollama.ai
# Linux : curl https://ollama.ai/install.sh | sh
```

### "Ollama pas en cours d'exécution"
```bash
# Terminal séparé :
ollama serve
```

### "Port 8000 déjà utilisé"
```bash
# Lancer sur un autre port
python main.py  # Modifier port=8001 dans le code
```

### "Erreur 404 sur les fichiers statiques"
- Vérifier les chemins dans `frontend/static/`
- Vérifier que `backend/main.py` est lancé depuis le bon répertoire

## 📚 Documentation

- **FastAPI** : https://fastapi.tiangolo.com
- **Ollama** : https://ollama.ai
- **Jinja2** : https://jinja.palletsprojects.com
- **Fetch API** : https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API

## 📄 License

Libre d'utilisation - Projet éducatif

---

**Créé pour démontrer l'intégration complète : Python + FastAPI + Ollama + Frontend vanilla JS**

🚀 Bon chatting!
