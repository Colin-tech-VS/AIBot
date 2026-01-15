# 📅 Scheduler Automatique de Crawling (Lundi)

## 🎯 Objectif
Actualiser **automatiquement** les données crawlées (news F1) **tous les lundis à 00:01 UTC** pour éviter une surcharge serveur et garder les données fraîches.

---

## 🔧 Architecture

### 1. **Scheduler Principal** : `backend/monday_scheduler.py`

**Classe `MondayScheduler`** :
- Lance un **thread daemon** au démarrage de l'app
- Calcule le **prochain lundi** automatiquement
- Attend jusqu'à **00:01 UTC** le lundi (avec vérification toutes les 60s)
- Exécute deux actions :
  1. **Invalide le cache** des widgets (standings, top drivers, etc.)
  2. **Lance le crawler** pour actualiser les news

**Code de lancement** :
```python
from backend.monday_scheduler import start_scheduler
start_scheduler()  # Appelé au démarrage de app.py
```

### 2. **Script Crawler** : `scripts/crawler_f1.py`

Sites crawlés chaque lundi :
- 🏎️ **motorsport.com** - News F1 internationales
- 🏎️ **autosport.com** - News et analyses
- 🏎️ **actuf1.com** - Actualités F1 francophones
- 📊 **standf1.com** - Classements et stats
- 📅 **fia.com** - Calendrier officiel

**Résultat** : Fichiers JSON sauvegardés dans `knowledge_base/crawled/`

### 3. **Intégration dans le Bot** : `backend/f1_bot.py`

La fonction `get_news_summaries()` récupère et enrichit les données crawlées pour les réponses du chatbot.

---

## 📋 Flux d'Exécution (Lundi)

```
📅 LUNDI 00:01 UTC
│
├─ MondayScheduler déclenche _refresh_widgets()
│
├─ 🔄 ÉTAPE 1: Invalider cache widgets
│  ├─ Cache des standings
│  ├─ Cache des top drivers
│  └─ Cache des prochain GP
│
├─ 🕷️  ÉTAPE 2: Lancer crawling (subprocess)
│  ├─ Exécute scripts/crawler_f1.py
│  ├─ Timeout: 120 secondes max
│  └─ Crawle 5 sites en parallèle
│
├─ 📝 Sauve données dans knowledge_base/crawled/
│
└─ ✅ Invalide cache news pour rechargement frais
```

---

## 🎮 Contrôle Manuel

### A. Force un Crawling **IMMÉDIATEMENT**

```bash
# Terminal 1 : Lance l'app
python app.py

# Terminal 2 : Force crawling
curl -X POST http://localhost:8000/crawler/run
```

**Réponse** :
```json
{
  "status": "success",
  "message": "Crawling exécuté avec succès",
  "output": "..."
}
```

### B. Relancer le Crawler en Script Autonome

```bash
python scripts/crawler_f1.py
```

**Output** :
```
🕷️  Crawling motorsport.com...
✅ motorsport: 12 articles
🕷️  Crawling autosport.com...
✅ autosport: 8 articles
...
📝 Métadonnées sauvegardées
```

---

## 📊 Configuration

### Modifier le jour/heure de refresh

**Fichier** : `backend/monday_scheduler.py` ligne 49-64

Actuellement : **Lundi à 00:01 UTC**

Pour changer en **Mercredi à 14h** :
```python
def _get_next_monday(self) -> datetime:
    now = datetime.utcnow()
    
    # Mercredi = 2 (au lieu de 0 pour lundi)
    days_until_target = (2 - now.weekday()) % 7
    
    # Heure: 14h (au lieu de 00:01)
    next_target = (now + timedelta(days=days_until_target)).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    ...
```

### Augmenter le timeout du crawler

**Fichier** : `backend/monday_scheduler.py` ligne 128

```python
timeout=120  # Secondes (augmenter si sites lents)
```

---

## 🐛 Dépannage

### Le scheduler ne lance pas ?

```bash
# Vérifier les logs
python app.py 2>&1 | grep -i "scheduler\|crawl"

# Résultat attendu:
# ✅ MondayScheduler démarré (refresh widgets le lundi)
```

### Le crawling timeout ?

Sites peuvent être lents. Augmenter timeout :
```python
timeout=300  # 5 minutes au lieu de 2
```

### Les données ne se mettent pas à jour ?

Vérifier métadonnées de crawl :
```bash
cat knowledge_base/crawled/_crawl_metadata.json
```

Doit montrer un timestamp récent du lundi.

### Forcer une mise à jour immédiate

```bash
# Via API
curl -X POST http://localhost:8000/crawler/run

# Via script
python scripts/crawler_f1.py

# Via cache invalidation
curl -X POST http://localhost:8000/kb/reload
```

---

## 📈 Monitoring

### Vérifier le statut du scheduler

Les logs montrent :
```
⏰ Prochain refresh: 2026-01-20 00:01:00 UTC
✅ Cache widgets invalidé (lundi refresh)
🕷️  Lancement crawling...
✅ Cache news invalidé (nouvelles données crawlées)
```

### États possibles

| État | Meaning |
|------|---------|
| `⏰ Prochain refresh` | Scheduler en attente jusqu'au lundi |
| `🕷️  Lancement crawling` | Crawling en cours |
| `✅ Cache invalidé` | Nouvelle data prête |
| `⚠️  Crawling partiellement échoué` | Certains sites inaccessibles (fallback OK) |
| `❌ Erreur crawling` | Erreur critique |

---

## 🚀 Prochaines Améliorations

- [ ] Notifier l'utilisateur quand crawling terminé
- [ ] Dashboard pour voir l'âge des données (last_crawl)
- [ ] Ajouter un **retry** si crawling échoue
- [ ] Ajouter des logs **Slack/Discord** pour monitoring en prod
- [ ] Implémenter **cache multi-niveaux** (in-memory + disk)

---

## 📝 Résumé

✅ **Scheduler automatique les lundis** → actualise news sans effort  
✅ **Endpoint manuel** (`/crawler/run`) pour forcer mise à jour  
✅ **Timeout intelligent** (120s) pour éviter blocages  
✅ **Cache invalidation** pour frais données servies  
✅ **Logs détaillés** pour monitoring  
