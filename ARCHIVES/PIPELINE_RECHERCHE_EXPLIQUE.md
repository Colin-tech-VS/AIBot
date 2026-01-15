# 🏎️ Pipeline de Recherche & Sélection d'Infos - F1 Chatbot

## Vue d'ensemble
Quand tu poses une question, le bot suit une **cascade logique** pour trouver et sélectionner la meilleure info.

```
[Question reçue]
    ↓
[Validation & Sécurité]
    ↓
[Détection du type de question]
    ↓
[Pipeline spécialisé selon le type]
    ↓
[Synthèse et réponse]
```

---

## 📋 ÉTAPE 1 : VALIDATION & CONTEXTE (0ms)

### 1.1 Historique conversationnel
```
- Formatte les 6 derniers tours de conversation
- Donne du contexte au bot pour les relances ("Plus d'infos", "Pourquoi", etc)
- Exemple: Si tu demandais sur Verstappen, le bot se souvient
```

### 1.2 Mémoire long terme
```
- Récupère les faits appris des conversations précédentes
- Stockage JSONL: all_conversations.jsonl
- Enrichit le contexte pour répondre aux questions personnalisées
```

---

## 🎯 ÉTAPE 2 : DÉTECTION DU TYPE DE QUESTION (<100ms)

Le bot analyse ta question pour savoir quelle pipeline utiliser :

### Détection via REGEX (rapide)
```
- F1 ❓ → Mots-clés comme "Verstappen", "Ferrari", "pole", "classement"
- Circuit ❓ → Mots-clés comme "circuit", "piste", "Monza", "Spa"  
- Générale ❓ → Questions sur "c'est quoi", "pourquoi", pas de F1
```

### Détection contextuelle (persistance de sujet)
```
- Si l'historique parle de F1 et tu poses une courte relance → Force F1
- Exemple: [Contexte: Verstappen] + [Question: "Et lui?"] → Reste sur F1
```

---

## 🔄 ÉTAPE 3 : PIPELINES SPÉCIALISÉS

### A. QUESTIONS SUR CIRCUITS (<100ms)
**Source prioritaire: CSV local** (traitement RAPIDE)

```
Question: "Quel circuit est le plus long?"
    ↓
[Cherche dans circuits_kb.csv]
    ↓
[Retourne directement] ✅

Exemple réponse:
"🏎️ Spa-Francorchamps (7.004 km)"
Source: [Base de données circuits CSV]
```

---

### B. QUESTIONS F1 (Le pipeline principal)

Cascade de recherche avec **PRIORITÉS claires** :

#### **PRIORITÉ #1 : Knowledge Base (2233 docs)**
```
Paramètres:
- top_k = 15  (cherche les 15 meilleurs résultats)
- min_score = 0.35  (accepte scores ≥ 35% de similarité)
- Recherche sémantique FAISS (sentence-transformers)

Sources intégrées dans KB:
  ✓ knowledge_base/*.md  (procédures, FAQs, glossaire)
  ✓ knowledge_base/f1_wiki_csv/  (1950-2024 historique)
  ✓ knowledge_base/crawled/  (223 articles news récents)

Résultat: KB_content = les 15 meilleurs chunks fusionnés (5000 chars max)
Log: "✅ KB PRIORITAIRE: 15 chunks utilisés (score ≥0.35)"
```

#### **PRIORITÉ #2 : Mémoire long terme**
```
Sources:
- learned_facts.json  (faits appris des conversations)
- user_preferences.json  (styles de réponse préférés)
- all_conversations.jsonl  (historique global)

Résultat: memory_context = contexte enrichi
Log: "✅ MEMORY: Contexte long terme récupéré"
```

#### **PRIORITÉ #3 : Standings temps réel**
```
Détecte mots-clés: "classement", "points", "leader", "top 10"

Si PILOTES → fetch StandF1 (top 10 drivers)
Si CONSTRUCTEURS → fetch StandF1 (top 10 teams)

Résultat: ergast_summary = classement actuel
Source: "StandF1.com - Classements en temps réel"
```

#### **PRIORITÉ #4 : Données historiques CSV**
```
Détecte:
- Année (1950-2026): "Qui a gagné en 1995?"
- Mots-clés: "saison", "championnat"

Cherche dans f1_wiki_csv/{1995_formula_one_season/}
Crée résumé avec:
  - Fichier source
  - Infos clés (Pilotes, Constructeurs, etc)
  - Lien Wikipedia si dispo

Résultat: season_csv_summary = résumé compact
Sources: ["Données historiques CSV", "Wikipedia F1"]
```

#### **APPEL LLM AVEC TOUTES LES INFOS**
```
prompt = OptimizedPromptBuilder.build_f1_question(
    question = ta question
    kb_content = résultats KB (priorité #1)
    long_term_context = mémoire (priorité #2)
    standings = classements (priorité #3)
    news_summary = saisons CSV (priorité #4)
    conversation_history = historique
)
```

**Le LLM (Qwen 2.5 7B) synthétise tout et choisit:**
```
"Parmi tous ces infos, laquelle est la plus pertinente?"

Critères de synthèse du LLM:
1. Véracité (trucs de la KB prioritaires)
2. Actualité (standings temps réel si pertinent)
3. Contexte (historique de conversation)
4. Cohérence avec la question
```

#### **ÉTAPE FINALE: Web Search (DERNIER RECOURS)**
```
Condition d'activation: La réponse du LLM est:
- Vide ""
- Contient "désolé", "pas d'info", "je n'ai pas"
- Moins de 30 caractères

Alors:
1. Lance recherche Wikipedia API
2. Récupère max 2 résultats
3. Reconstruit le prompt avec Wikipedia
4. Appelle Ollama une 2e fois

Source: "Recherche web (Wikipedia)"

⚠️ Web Search = FALLBACK seulement, jamais premier choix
```

---

### C. QUESTIONS GÉNÉRALES (Non-F1)

```
Question: "C'est quoi Python?"
    ↓
[Cherche KB avec score ≥0.5 (plus strict)]
    ↓
SI résultat pertinent:
    → Utilise prompt F1 avec KB
SINON:
    → Utilise prompt général (sans contexte F1)
    ↓
[Appelle Ollama]
```

---

## 📊 COMMENT LE BOT CHOISIT QUELLE INFO DONNER

### Règles de sélection (ordre d'importance)

```
1️⃣ KNOWLEDGE BASE (si score ≥0.35)
   └─ Priorité maximale
   └─ Source fiable (FAQ, documents)
   └─ Articles crawlés (news récentes)

2️⃣ MÉMOIRE LONG TERME
   └─ Si KB insuffisant
   └─ Complète avec contexte perso

3️⃣ STANDINGS TEMPS RÉEL
   └─ Pour questions classements
   └─ Données Ergast actualisées

4️⃣ DONNÉES HISTORIQUES
   └─ Pour questions "en 1995", "cette saison"
   └─ CSV structurées 1950-2024

5️⃣ LLM SYNTHÈSE
   └─ Combine les sources #1-4
   └─ Répond de manière cohérente

6️⃣ WEB SEARCH (si échec total)
   └─ Dernier recours
   └─ Wikipedia API
```

### Exemple concret

**Question:** "Qui a gagné le classement en 1995?"

```
ÉTAPE 1: Validation
  └─ Année détectée: 1995
  └─ Type: Question F1 historique

ÉTAPE 2: Pipeline F1
  ├─ KB Search → cherche "1995" dans 2233 docs
  │   └─ Résultat: 5-10 chunks trouvés (score 0.45+)
  │   └─ Contenu: Infos sur la saison 1995
  │
  ├─ Memory → cherche contexte long terme
  │   └─ Résultat: vide (première fois)
  │
  ├─ Standings → mots-clés absents
  │   └─ Résultat: ignoré
  │
  └─ CSV Saisons → année 1995 exacte
      └─ Résultat: f1_wiki_csv/1995_formula_one_season/
      └─ Contenu: Drivers, races, résultats

ÉTAPE 3: Appel LLM
  prompt = KB(5-10 chunks) + CSV(résumé 1995) + Historique
  
  LLM synthétise:
  "En 1995, le champion a été [nom], avec [points] points"
  
  LLM cite automatiquement:
  - Si data KB → "selon nos docus"
  - Si data CSV → "d'après les archives 1995"

ÉTAPE 4: Réponse
  ✅ "Benetton a remporté le championnat 1995 avec [pilote]..."
  Sources: ["Knowledge Base F1", "Données historiques CSV"]
```

---

## ⚡ Optimisations implémentées

### Cache multi-étages
```
- Cache KB: réutilise résultats FAISS
- Cache Memory: récupère faits appris
- Cache Standings: rafraîchi toutes les 10 min
- Cache News: articles crawlés rechargés le lundi
```

### Détection d'incertitude
```
Si le LLM répond vaguement:
  → Fallback Web Search activé
  → Enrichit avec Wikipedia
  → Relance LLM avec nouvelles infos
```

### Persistance de sujet
```
Historique: [Verstappen] [Crash Silverstone] [Red Bull]
Question: "Pourquoi?"

Bot détecte:
  → Contexte F1 récent
  → Question courte avec pronom
  → Force classification F1
  → Utilise pipeline F1 même si ambigu
```

---

## 🎓 Résumé: L'IA décide via PRIORITÉS

```
┌─────────────────────────────────────────┐
│  Tu poses une question                  │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Type de question?                      │
│  ├─ Circuit?    → CSV rapide ✅         │
│  ├─ F1?         → Pipeline complet      │
│  └─ Générale?   → Mode libre            │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Cherche info par PRIORITÉ:             │
│  1️⃣ KB (2233 docs) top_k=15            │
│  2️⃣ Memory (faits appris)              │
│  3️⃣ Standings (temps réel)             │
│  4️⃣ CSV Historique (1950-2024)        │
│  5️⃣ LLM Synthèse (combine 1-4)         │
│  6️⃣ Web Search (dernier recours)       │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  Ollama génère réponse cohérente        │
│  + liste des sources utilisées          │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  ✅ Réponse livrée                      │
│  Stockée dans mémoire long terme        │
└─────────────────────────────────────────┘
```

---

## 📝 Logs à regarder pour debug

Quand tu vérifies `logs/f1_bot.log`, tu verras:

```
✅ KB PRIORITAIRE: 15 chunks utilisés (score ≥0.35)
    → KB a trouvé suffisamment d'infos

✅ MEMORY: Contexte long terme récupéré
    → Faits appris utilisés

✅ Standings récupérés via StandF1
    → Classements temps réel activés

Saisons CSV: 12 entrées (résumé 8)
    → Données historiques intégrées

⚠️ LLM incertain avec KB+Memory, tentative Web Search
    → LLM a dû fallback sur Wikipedia

✅ Web Search utilisé en dernier recours
    → Wikipedia a sauvé la situation
```

---

## 🔐 Sécurité & Vérité

Le bot **ne fabrique JAMAIS** d'info :

```
Scénario: Question sur un sujet absent
  ├─ KB ne trouve rien (score <0.35)
  ├─ Memory vide
  ├─ CSV absent
  ├─ LLM hésite
  └─ Web Search échoue

Résultat: Message honnête
  "Désolé, j'ai cherché dans ma base et sur le web
   mais je n'ai pas trouvé de détails précis sur ça..."
```

Jamais d'hallucination ou de faux infos ! 🚫
