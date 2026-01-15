# 🔍 La CASCADE: Où exactement les articles crawlés sont utilisés?

## Le moment clé : `kb.search()` dans ÉTAPE 1

```
PIPELINE F1 COMMENCE
    ↓
[ÉTAPE 1: Knowledge Base - PRIORITAIRE]
    ↓
kb = get_knowledge_base()  ← Charge KB (2233 docs incluant les crawled)
    ↓
kb_results = kb.search(user_question, top_k=15, min_score=0.35)
                                    ↑                    ↑
                        Cherche les 15 meilleurs   Score minimum
                        dans TOUS les 2233 docs   (crawled inclus!)
    ↓
┌─────────────────────────────────────────────────────────┐
│ C'EST ICI QUE LES ARTICLES CRAWLÉS SONT UTILISÉS!       │
│                                                         │
│ FAISS cherche dans:                                     │
│ ├─ 2010 documents de base (FAQ, glossaire, wiki CSV)   │
│ └─ 223 articles crawlés (motorsport, autosport, actuf1)│
│                                                         │
│ Les 15 meilleurs chunks (peu importe la source!)       │
│ sont retournés et fusionnés                            │
└─────────────────────────────────────────────────────────┘
    ↓
if kb_results:
    kb_content = "\n\n".join(kb_results)[:5000]
                           ↑
            Fusionne TOUS les chunks trouvés
            (FAQ + wiki CSV + ARTICLES CRAWLÉS)
    ↓
sources.append("Knowledge Base F1 (base de connaissances locale)")
               ↑
        Source citée (ne différencie pas l'origine)
```

---

## 🎯 Cas concret: Question sur actualités récentes

### Scénario
**Question:** "Qui a remporté le dernier Grand Prix?"
**Date:** Mardi 14 janvier 2026 (juste après le crawl du lundi)

### Déroulement complet

```
[1] User pose: "Qui a remporté le dernier Grand Prix?"
    ↓

[2] Détection type: F1? OUI ✓
    ↓

[3] ÉTAPE 1: Knowledge Base Search
    
    kb.search("Qui a remporté le dernier Grand Prix?", top_k=15, min_score=0.35)
    
    FAISS traite CHAQUE vecteur:
    
    Chunk #1 (FAQ - Score 0.28) → REJETÉ (< 0.35)
    Chunk #2 (CSV 2025 standings - Score 0.41) → ✓ ACCEPTÉ
    Chunk #3 (CSV 1990 - Score 0.12) → REJETÉ
    Chunk #4 (crawled_actuf1_15 - "GP dimanche") → ✓ SCORE 0.68 ACCEPTÉ
    Chunk #5 (crawled_motorsport_8 - "Résultats") → ✓ SCORE 0.64 ACCEPTÉ
    Chunk #6 (crawled_actuf1_42 - "Classement") → ✓ SCORE 0.59 ACCEPTÉ
    Chunk #7 (glossaire - Score 0.19) → REJETÉ
    Chunk #8 (CSV 2025 calendar - Score 0.38) → ✓ ACCEPTÉ
    Chunk #9 (crawled_motorsport_12 - "Victoire") → ✓ SCORE 0.61 ACCEPTÉ
    Chunk #10 (FAQ - Score 0.31) → REJETÉ
    ...
    Chunk #N (crawled_actuf1_99 - "Podium") → ✓ SCORE 0.55 ACCEPTÉ
    
    Trier par score décroissant, garder TOP 15:
    
    🥇 crawled_actuf1_15 (0.68) ← ARTICLE CRAWLÉ #1
    🥈 crawled_motorsport_8 (0.64) ← ARTICLE CRAWLÉ #2
    🥉 crawled_motorsport_12 (0.61) ← ARTICLE CRAWLÉ #3
    4️⃣ crawled_actuf1_42 (0.59) ← ARTICLE CRAWLÉ #4
    5️⃣ crawled_actuf1_99 (0.55) ← ARTICLE CRAWLÉ #5
    6️⃣ CSV 2025 calendar (0.38)
    7️⃣ CSV 2025 standings (0.41)
    ... (+ 8 autres)
    
    ✅ Résultat: 15 chunks, dont 5 articles crawlés!
    ↓

[4] Fusionne les résultats

    kb_content = """
    [Article crawlé 1] ActuF1: Verstappen remporte le GP...
    
    [Article crawlé 2] Motorsport: Verstappen gagne...
    
    [Article crawlé 3] Motorsport: Résultats complets...
    
    [Article crawlé 4] ActuF1: Classement final...
    
    [Article crawlé 5] ActuF1: Podium du jour...
    
    [Données CSV] 2025 Calendar: ...
    
    [Données CSV] Standings: ...
    
    ... (+ 7 autres chunks)
    """
    
    Total: 5000 caractères max
    ↓

[5] Ajoute source

    sources.append("Knowledge Base F1 (base de connaissances locale)")
    
    Note: Ne différencie pas FAQ, CSV, ou articles crawlés
    (Tous dans la même KB!)
    ↓

[6] Construit le PROMPT

    prompt = OptimizedPromptBuilder.build_f1_question(
        question="Qui a remporté le dernier Grand Prix?",
        kb_content=kb_content,  ← CONTIENT 5 ARTICLES CRAWLÉS!
        standings=None,
        conversation_history="",
        long_term_context=None
    )
    
    Le prompt envoyé à Ollama:
    """
    [SYSTEM PROMPT 5 RÈGLES IMMUABLES]
    
    CONTEXTE CONVERSATION:
    (aucun)
    
    SOURCES:
    [Article crawlé 1] ActuF1: Verstappen remporte le GP...
    [Article crawlé 2] Motorsport: Verstappen gagne...
    [Article crawlé 3] Motorsport: Résultats complets...
    [Article crawlé 4] ActuF1: Classement final...
    [Article crawlé 5] ActuF1: Podium du jour...
    [Données CSV] 2025 Calendar: ...
    [Données CSV] Standings: ...
    
    QUESTION: Qui a remporté le dernier Grand Prix?
    
    Réponds maintenant (direct et concis):
    """
    ↓

[7] Ollama génère réponse

    Qwen 2.5 7B lit le prompt et voit:
    - 5 articles crawlés mentionnant "Verstappen" et "GP"
    - Données CSV confirmant la date
    
    Génère:
    "🏎️ Max Verstappen a remporté le dernier Grand Prix dimanche
     avec une victoire stratégique. Il domine désormais le classement..."
    ↓

[8] Retour utilisateur

    Response: "🏎️ Max Verstappen a remporté..."
    Sources: ["Knowledge Base F1 (base de connaissances locale)"]
    
    ✅ L'utilisateur a reçu l'info depuis les articles crawlés!
       (Sans le savoir - c'est transparent)
```

---

## 📊 VISUALISATION: Où se trouvent les crawled articles dans la CASCADE

```
┌─────────────────────────────────────────────────────────────────┐
│                    PIPELINE F1 COMPLET                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ÉTAPE 1: Knowledge Base Search [ICI!!!]                       │
│  ├─ FAISS search (top_k=15, min_score=0.35)                   │
│  │  ├─ 2010 docs de base (FAQ, wiki CSV)                      │
│  │  └─ 223 articles crawlés ← CHERCHÉS ICI!                   │
│  │      ├─ news_motorsport.json                              │
│  │      ├─ news_autosport.json                               │
│  │      └─ news_actuf1.json                                  │
│  │                                                            │
│  │  Résultat: top 15 chunks (mélange de sources)            │
│  │                                                            │
│  ├─ kb_content = fusion des 15 chunks                         │
│  └─ sources.append("Knowledge Base F1")                       │
│                                                                 │
│  ÉTAPE 1.5: CSV Saisons (si année détectée)                  │
│  ├─ Cherche dans f1_wiki_csv/ (historique)                   │
│  └─ NOT les articles crawlés (historique ancien)             │
│                                                                 │
│  ÉTAPE 2: Memory Long Terme                                    │
│  └─ Faits appris (pas les articles crawlés)                  │
│                                                                 │
│  ÉTAPE 3: Standings (si classement détecté)                   │
│  └─ StandF1 temps réel (pas articles crawlés)                │
│                                                                 │
│  ÉTAPE 4: LLM SYNTHÈSE                                         │
│  ├─ Reçoit kb_content (INCLUANT articles crawlés)            │
│  ├─ Génère réponse basée sur les sources                     │
│  └─ Sources citées: "Knowledge Base F1"                       │
│                                                                 │
│  ÉTAPE 5: Web Search (SI ÉCHEC)                               │
│  └─ Wikipedia search (pas articles crawlés)                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎯 Résumé: Le moment exact

| Question | Moment dans la cascade | Articles crawlés utilisés? |
|----------|----------------------|--------------------------|
| **"Qui a gagné dimanche?"** | ÉTAPE 1: KB Search | ✅ OUI (si similarité > 0.35) |
| **"Qui était champion en 1995?"** | ÉTAPE 1.5: CSV Saisons | ❌ NON (historique ancien) |
| **"Quel est le classement?"** | ÉTAPE 3: Standings | ❌ NON (pas dans standings) |
| **"Explique pourquoi Verstappen a perdu"** | ÉTAPE 1: KB Search | ✅ OUI (si articles parlent de la perte) |
| **"Donne-moi les news du week-end"** | ÉTAPE 1: KB Search | ✅ OUI (articles crawlés = news!) |

---

## 🔎 Comment vérifier si un article crawlé a été utilisé?

### Dans les logs

```
✅ KB PRIORITAIRE: 15 chunks utilisés (score ≥0.35)
```

Cette ligne signifie:
- 15 chunks trouvés
- Certains peuvent être des articles crawlés
- Pas de distinction dans les logs

### Pour voir lesquels exactement

Ajouter ce code en debug:

```python
# Dans backend/f1_bot.py - ÉTAPE 1

kb = get_knowledge_base()
kb_results = kb.search(user_question, top_k=15, min_score=0.35)

# DEBUG: Afficher les sources
for i, chunk in enumerate(kb_results):
    if "crawled" in chunk.lower() or "motorsport" in chunk.lower():
        print(f"🔍 Chunk #{i+1}: ARTICLE CRAWLÉ DÉTECTÉ")
        print(f"   Extrait: {chunk[:100]}...")
    elif "2025" in chunk or "standings" in chunk.lower():
        print(f"📊 Chunk #{i+1}: DONNÉES CSV/STANDINGS")
    else:
        print(f"📝 Chunk #{i+1}: FAQ/GLOSSAIRE")
```

---

## ⚡ Points clés

```
✅ Les articles crawlés sont cherchés dans ÉTAPE 1
  └─ kb.search() regarde TOUS les 2233 docs
  └─ FAISS les teste comme les autres vecteurs

✅ Si la similarité > 0.35 → UTILISÉS dans le prompt
  └─ Contribuent à la réponse Ollama

✅ JAMAIS de fallback sur articles crawlés
  └─ Ils sont juste intégrés à la KB
  └─ Traités comme n'importe quel chunk

✅ Mélange transparent
  └─ FAQ + CSV 1950-2024 + Articles crawlés
  └─ Tout fusionné dans kb_content
  └─ Ollama ne sait pas la différence

⚠️ Web Search NE récupère PAS les articles crawlés
  └─ Web Search = Wikipedia API seulement
  └─ Fallback de dernier recours
  └─ Articles crawlés sont dans KB (pas web)
```

---

## 📈 Exemple: Comment un article crawlé "gagne" contre d'autres sources

**Question:** "Qui a remporté le Grand Prix de Monza?"
**Contexte:** Article crawlé lundi parle de Monza, FAQ aussi

```
FAISS compare les similarités:

FAQ (générique "Monza est un circuit"):
  └─ Embedding FAQ → Question "Monza" → Score 0.32 ❌ REJETÉ

CSV historique (Monza 1950-2024):
  └─ Embedding CSV Monza → Question → Score 0.39 ✓ ACCEPTÉ (#7 rank)

Article crawlé (Motorsport: "Verstappen wins Monza 2025"):
  └─ Embedding crawled → Question → Score 0.72 ✓✓ ACCEPTÉ (#1 rank!)
  
  Pourquoi plus haut?
  - Mots clés exacts: "Verstappen", "win", "Monza", "2025"
  - Contexte récent (crawlé dimanche)
  - Exact match pour la question actuelle
```

**Résultat:** L'article crawlé arrive #1, donc utilisé en priorité! 🥇

---

## 🔐 Sécurité & Vérité

```
Scénario: Article crawlé contient info fausse
  └─ "Verstappen a gagné Monza" (faux!)

Contrôles:
  1. KB indexe juste le vecteur (pas validation du texte)
  2. LLM voit le texte faux dans le prompt
  3. LLM peut:
     ✓ Reconnaître l'erreur (s'il a d'autres infos)
     ✗ Répéter l'erreur (si c'est la seule source)
  
Solution: KB est aussi bonne que les sources crawlées!
  └─ Les scrapers doivent être fiables
  └─ Monitoring des articles est important
```
