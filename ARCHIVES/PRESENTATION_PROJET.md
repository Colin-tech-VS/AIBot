# 🏎️ Chatbot F1 - Guide Simple du Projet

## À quoi ça sert ? 🤔

Ce projet est un **chatbot intelligent sur la Formule 1** qui répond à tes questions sur la F1 en français. Tu peux lui demander n'importe quoi sur les pilotes, les équipes, les calendriers, les résultats, ou même des analyses sur les stratégies de course.

---

## Comment ça fonctionne ? 🎯

### 1️⃣ **Tu poses une question**
Tu écris ta question dans le chatbox du site (ex: "Qui est le champion en titre?" ou "Quand est la prochaine course?")

### 2️⃣ **Le système comprend ce que tu demandes**
Le système analyse ta question pour comprendre **ce que tu cherches vraiment** :
- Tu veux les classements des pilotes?
- Tu veux savoir quand est la prochaine course?
- Tu veux connaître les statistiques d'un pilote?

Cela se fait **super rapidement** (moins d'une seconde) sans utiliser l'IA.

### 3️⃣ **Le système cherche la réponse**
Selon ta question, le système cherche les informations de 3 façons différentes :

**A) Les données en direct** 📊
- Les classements actuels (pilotes et équipes)
- Le calendrier des courses
- Les résultats des dernières courses
- Tout ça vient directement de l'API Ergast (la base de données officielle F1)

**B) La base de connaissances locale** 📚
- Règles de F1, glossaire, historique
- Infos sur les circuits, les équipes, les pilotes
- Explications sur les stratégies de course
- Tout ça stocké localement pour répondre rapidement

**C) Les actualités récentes** 📰
- Infos fraîches des sites F1 (standf1.com, lequipe.fr, FIA)
- Les dernières nouvelles et annonces

### 4️⃣ **L'IA génère une réponse naturelle**
Si une simple recherche ne suffit pas, l'IA (Qwen 2.5 - très rapide) :
- Lit toutes les infos trouvées
- Les analyse
- Écrit une réponse en **français naturel et lisible**
- Ajoute des emojis F1 pour la fun 🏁
- Cite ses sources 📖

### 5️⃣ **Tu lis la réponse**
La réponse s'affiche instantanément (en quelques secondes), et tu peux continuer à poser d'autres questions !

---

## Les fonctionnalités principales 💡

### ✅ **Réponses rapides** ⚡
- Questions simples : réponse en moins d'1 seconde
- Questions complexes : réponse en 2-5 secondes
- Pas de temps d'attente frustrant

### ✅ **Toujours en français** 🇫🇷
- Les réponses sont **toujours en français**, c'est garanti
- Pas d'anglais, pas de mélange de langues

### ✅ **Données à jour** 🔄
- Résultats en direct depuis l'API Ergast
- Actualités mises à jour quotidiennement
- Cache intelligent pour éviter les ralentissements

### ✅ **Questions variées**
Tu peux poser :
- **Classements** : "Qui sont les top 5 pilotes?" 
- **Calendrier** : "Quand est Monaco?" 
- **Historique** : "Combien de titres a Hamilton?"
- **Tactiques** : "Pourquoi Ferrari utilise cette stratégie?"
- **Règles** : "C'est quoi le DRS?"
- **Actualités** : "Quel est la dernière news F1?"

### ✅ **Mémoire de conversation**
- Le système se souvient de ce que tu as dit
- Tu peux poser des questions de suivi sans répéter

---

## Les briques du système 🧩

```
┌─────────────────────────────────────────────────────────┐
│              TON ORDINATEUR (Frontend)                  │
│         • Site web simple avec chatbox                  │
│         • Interface propre et intuitive                 │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ↓
┌─────────────────────────────────────────────────────────┐
│         MOTEUR CENTRAL (Backend - app.py)              │
│                                                         │
│  1. ROUTEUR D'INTENTION                                 │
│     └─ Comprend ce que tu veux en 10ms                 │
│                                                         │
│  2. COLLECTEUR D'INFOS                                 │
│     ├─ Cherche les données en direct (Ergast API)      │
│     ├─ Cherche dans la base locale (FAISS)             │
│     └─ Cherche les actualités (Web scraping)           │
│                                                         │
│  3. IA (Ollama + Qwen 2.5)                             │
│     └─ Écrit une réponse naturelle en français         │
│                                                         │
│  4. CACHE INTELLIGENT                                   │
│     └─ Stocke les réponses fréquentes                  │
└──────────────────┬──────────────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
   ┌────────┐ ┌──────────┐ ┌─────────┐
   │ Ergast │ │Knowledge │ │ Actualités
   │  API   │ │  Base    │ │ & News
   │        │ │ (FAISS)  │ │
   └────────┘ └──────────┘ └─────────┘
```

---

## Les données qu'on utilise 📊

### **Données en direct** (API Ergast)
- Classements actuels (pilotes et constructeurs)
- Calendrier des courses
- Résultats détaillés des courses
- Mises à jour automatiques

### **Base de connaissances locale**
- 📄 Fichiers texte (Markdown) : règles, glossaire, FAQ, procédures
- 📊 Tables (CSV) : pilotes, équipes, circuits
- 🔍 Index vectoriel (FAISS) : pour recherches sémantiques rapides
- ~5500 vecteurs pour une recherche "intelligente"

### **Actualités**
- 📰 Scraping automatique de standf1.com
- 📰 Scraping de lequipe.fr/Formule-1
- 📜 Calendrier et règlements FIA
- Cache de 24h pour ne pas surcharger les sites

---

## L'intelligence du système 🧠

### **Routage intelligent**
Le système ne balance pas tout à l'IA :
- ✅ Question simple sur les classements? → Réponse directe depuis Ergast (rapide!)
- ✅ Question sur la prochaine course? → Cherche dans le calendrier (très rapide!)
- ✅ Question complexe sur la stratégie? → L'IA lit tout et écrit une belle réponse

### **Cache pour la performance**
Plutôt que de tout recalculer :
- Les classements sont cachés 5 minutes
- Les actualités sont cachées 24h
- Les questions posées sont mémorisées
- Résultat : réponses instantanées aux questions répétées

### **Sécurité d'abord**
- L'IA ne peut pas être "hackée" pour répondre en anglais
- Chaque réponse est vérifiée pour être en français
- Pas de dérive possible de l'IA

---

## Cas d'usage pratiques 🎯

### 💬 **Question simple**
```
Toi: "Qui est le leader du championnat?"
→ Système: Détecte classements → Cherche dans Ergast → Répond en <1s
```

### 📅 **Question sur le calendrier**
```
Toi: "Quand est la prochaine course?"
→ Système: Détecte "next race" → Cherche le calendrier → Affiche date et lieu en <1s
```

### 🔍 **Question complexe**
```
Toi: "Pourquoi McLaren a-t-elle perdu contre Ferrari cette saison?"
→ Système: Cherche infos, actualités, analyses
→ L'IA lit tout et écrit une réponse complète
→ Répond en 3-5s avec explications et sources
```

### 📚 **Question sur les règles**
```
Toi: "C'est quoi le DRS?"
→ Système: Cherche dans la base de connaissances
→ Récupère l'explication du glossaire
→ Répond instantanément avec définition claire
```

---

## Avantages du projet ⭐

| Aspect | Avantage |
|--------|----------|
| **Vitesse** | Réponses en <1s pour questions simples, 2-5s pour complexes |
| **Langue** | Français garanti, pas d'anglais imposé |
| **Fraîcheur** | Données actualisées (Ergast) + news du jour |
| **Fiabilité** | Citations des sources, pas d'inventions |
| **Fluidité** | L'IA écrit naturellement, pas de listes sèches |
| **Local** | Fonctionne sans dépendre d'APIs externes complexes |
| **Intelligent** | Comprend l'intention, pas juste les mots-clés |

---

## Comment ça s'exécute? 🚀

### **Au lancement**
1. Tu lances le serveur → les données se chargent en cache
2. La base de connaissances se prépare (index FAISS)
3. Ollama démarre en arrière-plan (IA locale)
4. Le frontend se connecte au backend

### **Pendant que tu utilises**
1. Chaque question est traitée en cascade
2. Les réponses sont mises en cache
3. L'IA ne s'active que si besoin
4. Tout fonctionne offline (pas dépendant d'internet constant)

---

## Résumé en une phrase 🎯

**C'est un assistant F1 ultra-rapide qui comprend ce que tu demandes, cherche les bonnes infos (en direct ou dans sa base), et te répond en français naturel en 1 à 5 secondes.**

---

*Créé pour les fans de F1 qui veulent des réponses rapides, fiables et en français ! 🏁*
