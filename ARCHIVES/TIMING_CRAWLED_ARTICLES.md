# ⏰ Timeline: Quand les articles crawlés sont pris en compte

## Vue globale du timing

```
LUNDI 00:01 UTC        STARTUP APP         À CHAQUE QUESTION         SUNDAY 23:59 UTC
    ↓                       ↓                       ↓                        ↓
[Crawler]  →  [223 articles]  →  [KB reload]  →  [Utilisés en recherche]  →  [Cycle répète lundi]
   (weekly)      (saved JSON)     (FAISS index)      (si question F1)
```

---

## 📅 ÉTAPE 1: CRAWLING (Lundi 00:01 UTC)

### Quand ça se déclenche?

```python
# app.py - Démarrage du serveur
start_scheduler()  # Lance le scheduler Monday
    ↓
MondayScheduler check:
    "Est-ce lundi (jour 0) ET 00:01 UTC?"
    ↓
    OUI → Exécute: crawler_f1_weekly.py
    NON → Attend jusqu'à lundi
```

### Que fait le crawler?

```
crawler_f1_weekly.py lance:

  1. Motorsport.com (page 1)
     └─ ~62 articles crawlés
     └─ Sauvé: knowledge_base/crawled/news_motorsport.json

  2. Autosport.com (page 1)
     └─ ~59 articles crawlés
     └─ Sauvé: knowledge_base/crawled/news_autosport.json

  3. ActuF1.com (page 1)
     └─ ~102 articles crawlés
     └─ Sauvé: knowledge_base/crawled/news_actuf1.json

Total: 223 articles par semaine
```

### Résultat du crawl

```
knowledge_base/crawled/
├── news_motorsport.json  (62 articles)
├── news_autosport.json   (59 articles)
└── news_actuf1.json      (102 articles)

Chaque fichier contient:
{
  "site": "motorsport.com",
  "crawled_at": "2026-01-14T00:01:00Z",
  "items": [
    {
      "title": "Titre de l'article",
      "url": "https://...",
      ...
    }
  ]
}
```

---

## 🔄 ÉTAPE 2: INTÉGRATION À LA KB (Quand?)

### OPTION A: Au démarrage du serveur

```python
# app.py - Démarrage
if AUTO_CRAWL_ENABLED:
    auto_crawl_if_needed()
    # Check: dernière exécution crawl < 24h?
    #   OUI → Lance crawler_f1_weekly.py MAINTENANT
    #   NON → Skip
    ↓
get_knowledge_base()  # Initialise la KB
    ↓
KnowledgeBase.load_from_files():
    1. Charge knowledge_base/*.md
    2. Charge knowledge_base/f1_wiki_csv/**/*.csv
    3. Charge knowledge_base/crawled/news_*.json  ← ICI!
       └─ load_crawled_articles(kb_dir)
       └─ Crée KnowledgeDoc pour chaque article
       └─ Ajoute à index FAISS
    ↓
✅ 2233 documents indexés (2010 + 223)
   7983 chunks total
```

**Timing réel :**
- Serveur démarre → Charge KB → Intègre crawled articles
- **Immédiat au démarrage !**

### OPTION B: Refresh à la demande

```python
# API Endpoint
POST /kb/reload

→ reload_knowledge_base()
  └─ Relit tous les fichiers .md/.csv/crawled/*.json
  └─ Réindexe FAISS
  └─ Logs: "✅ {total_articles} articles crawlés indexés"
```

**Timing réel :**
- Si tu appelles manuellement `/kb/reload`
- **Instant (~3-5 secondes)**

---

## 🎯 ÉTAPE 3: UTILISATION DANS LES QUESTIONS (À chaque requête)

### Quand les crawled articles sont cherchés?

```
User: "Qui a marqué ce week-end?"
    ↓
[Détection type: F1?] → OUI
    ↓
[Pipeline F1]
    ↓
[PRIORITÉ #1: Knowledge Base Search]
    
    kb.search(query, top_k=15, min_score=0.35)
    
    Ce search cherche PARTOUT:
    ├─ knowledge_base/*.md (FAQ, glossaire)
    ├─ knowledge_base/f1_wiki_csv/*.csv (historique)
    └─ knowledge_base/crawled/*.json ← ICI! (news récentes)
    
    FAISS trouve les 15 meilleurs chunks
    (peu importe la source, c'est du vecteur!)
    ↓
Résultat: ~5-10 chunks trouvés parmi les 223 articles
    ↓
Les articles crawlés sont UTILISÉS dans le prompt!
```

**Log exemple :**
```
✅ KB PRIORITAIRE: 15 chunks utilisés (score ≥0.35)
   - 3 chunks de FAQ
   - 2 chunks de CSV 2025
   - 10 chunks de news crawlées (motorsport, actuf1) ← LES NÔTRES!
```

---

## ⚡ Timing complet en détail

### Dimanche 23:59 UTC
```
Aucun article crawlé n'est pris
Les 2010 documents de base sont utilisés uniquement
```

### Lundi 00:01 UTC (Scheduler)
```
[Crawling commence]
  └─ Motorsport.com page 1 (~2sec)
  └─ Autosport.com page 1 (~2sec)
  └─ ActuF1.com page 1 (~2sec)
  └─ Sauvé dans /crawled/*.json
  
[Résultat: 223 articles nouveaux]
```

### Lundi 00:06 UTC
```
[Serveur pas redémarré]
→ KB utilise toujours les ANCIENS articles
→ Les 223 nouveaux ne sont PAS encore intégrés
→ Faut redémarrer le serveur OU appeler /kb/reload
```

### Lundi 00:07 UTC (Après redémarrage)
```
[Serveur démarre]
  ↓
[get_knowledge_base() initialise]
  ↓
[load_crawled_articles() charge /crawled/*.json]
  ↓
✅ 2233 documents indexés (2010 + 223)
  ↓
À partir d'ICI, les questions utilisent les 223 nouveaux articles!
```

### Lundi 00:08 UTC onwards
```
User pose une question F1
  ↓
KB search cherche dans les 2233 docs (inclus les 223 nouveaux)
  ↓
Si la réponse est dans un article crawlé → Utilisé!
  ↓
✅ "Source: Knowledge Base F1 (base de connaissances locale)"
```

### Mardi - Dimanche
```
KB continue avec les 223 articles crawlés lundi
Pas de nouveau crawl
Articles restent "frais" (~7 jours)
```

### Prochain lundi 00:01 UTC
```
[Crawl #2 déclenchée]
  └─ 223 NOUVEAUX articles crawlés
  └─ Remplacent les anciens /crawled/*.json
  
Après redémarrage:
  └─ KB indexe les 223 NOUVEAUX
  └─ Les anciens (lundi précédent) sont supprimés
  └─ 2233 docs = 2010 base + 223 nouveaux
```

---

## 🔐 Mécanisme détaillé: Comment FAISS sait chercher les crawled articles?

### Indexing (une seule fois)

```python
# backend/knowledge_base.py - load_from_files()

for json_file in crawled_dir.glob("news_*.json"):
    for item in items:
        # Créer document
        doc = KnowledgeDoc(
            doc_id="crawled_motorsport_42",
            title="Verstappen wins Monaco GP",
            content="Source: MOTORSPORT.COM\nTitle: ...",
            source_type="news"  ← Type: news
        )
        
        # Ajouter à l'index
        self.add_document(doc)
        
        # self.add_document() fait:
        # 1. Génère embedding (all-MiniLM-L6-v2)
        # 2. Ajoute à index FAISS
        # 3. Stocke metadata (title, source_type, etc)
```

### Search (à chaque question)

```python
# backend/knowledge_base.py - search()

kb_results = kb.search("Qui a gagné Monaco?", top_k=15, min_score=0.35)

Process:
1. Génère embedding de la question
2. Cherche les 15 vecteurs les plus proches dans FAISS
   
   FAISS check TOUS les 2233 documents:
   ├─ FAQ embedding vs question embedding → score 0.42 ✗
   ├─ CSV 2024 Verstappen → score 0.38 ✓
   ├─ CSV 2025 Monaco results → score 0.51 ✓
   ├─ crawled_motorsport_15 (Monaco article) → score 0.67 ✓✓✓
   ├─ crawled_actuf1_8 (Monaco news) → score 0.59 ✓✓
   └─ ... 11 autres résultats
   
3. Retourne top 15 (peu importe la source!)
```

**Point clé:** FAISS ne sait pas d'où vient le vecteur - il cherche juste les plus proches! 🎯

---

## 🐛 Debug: Vérifier si les crawled articles sont indexés

### Commande pour vérifier

```python
from backend.knowledge_base import get_knowledge_base

kb = get_knowledge_base()

# Vérifier total docs
print(f"Documents totaux: {len(kb.docs)}")
# Expected: 2233 (si crawled articles chargés)
# Expected: 2010 (si crawled articles NOT chargés)

# Chercher spécifiquement un article crawlé
results = kb.search("Motorsport Grand Prix", top_k=5, min_score=0.35)
for r in results:
    if "motorsport" in r.lower() or "crawled" in r.lower():
        print(f"✅ Crawled article trouvé: {r[:100]}...")
```

### Logs à vérifier

```
# Startup logs (app.py)
✅ KB chargée: 2233 documents  ← Bon signe!
✅ {223} articles crawlés indexés dans FAISS  ← Parfait!

# Search logs (f1_bot.py)
✅ KB PRIORITAIRE: 15 chunks utilisés (score ≥0.35)  ← Cherche dans tous
```

---

## 📊 Timeline visuelle complète

```
LUNDI                           SAMEDI                       DIMANCHE
00:01     06:00     12:00       18:00      00:01           18:00      23:59
  │         │          │         │          │               │           │
  ├─[CRAWL]─┤          │         │          │               │           │
  │         └─[Save]───┤         │          │               │           │
  │                    └─[Restart server]   │               │           │
  │                         └─[FAISS INDEX] │               │           │
  │                              └─[READY]──├─[QUESTIONS]───┤           │
  │                                         │ (using 223)    │           │
  │                                         └────────────────┤           │
  │                                                          └─[Wait]────┤
  │                                                                      │
  └──────────── LUNDI PROCHAIN 00:01 ─────────────────────────────────┘
                   [CRAWL #2]
```

---

## ✅ Résumé: 3 phases

| Phase | Quand | Quoi | Où |
|-------|-------|------|-----|
| **CRAWL** | Lundi 00:01 UTC | 223 articles téléchargés | `/crawled/*.json` |
| **INDEXING** | Redémarrage serveur | Articles ajoutés à FAISS | En mémoire (index vectoriel) |
| **USAGE** | À chaque question F1 | Cherchés via similarité | Dans `kb.search()` |

**État final :** Les 223 articles crawlés sont **complètement invisibles** à l'utilisateur mais **très utiles** pour les recherches ! 🎯
