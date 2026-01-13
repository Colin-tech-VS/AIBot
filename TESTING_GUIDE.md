# 🚀 Guide de Test des Optimisations

## Objectif
Valider que le chatbot F1 répond en **moins de 2 secondes** avec la cascade optimisée **KB → Memory → Web Search**.

---

## 🔧 Préparation

### 1. Vérifier qu'Ollama est actif
```powershell
# Démarrer Ollama en arrière-plan
ollama serve

# Dans un autre terminal, vérifier qu'il répond
ollama --version
```

### 2. Activer l'environnement virtuel
```powershell
cd C:\Users\cococ\Desktop\IA
.\.venv\Scripts\Activate.ps1
```

### 3. Lancer le serveur
```powershell
python app.py
```
Le serveur démarre sur `http://localhost:8000`

---

## ✅ Tests Manuels (via Interface Web)

### Test 1: Question Simple KB Hit (<1s attendu)
**Question**: `Qui est le champion du monde F1 2024 ?`

**Comportement attendu**:
- ✅ Réponse en **<1s**
- ✅ Cite la Knowledge Base (`📚 ...`)
- ✅ Mention de Max Verstappen
- ✅ Pas de Web Search

**Si échec**: 
- Vérifier logs → chercher `✅ KB PRIORITAIRE: X chunks`
- Si KB miss → enrichir KB avec `knowledge_base/champions_recents.md`

---

### Test 2: Question Classements (<2s attendu)
**Question**: `Donne-moi le classement pilotes actuels`

**Comportement attendu**:
- ✅ Réponse en **<2s**
- ✅ Standings StandF1 (`✅ Standings récupérés via StandF1`)
- ✅ Top 10 pilotes avec points
- ✅ Pas de Web Search

**Si échec**:
- Vérifier StandF1 accessible (logs `Fetching StandF1`)
- Si timeout → vérifier connexion internet

---

### Test 3: Question Complexe (<3s acceptable)
**Question**: `Quelle a été la stratégie de Verstappen à Monaco en 2024 ?`

**Comportement attendu**:
- ✅ Réponse en **<3s**
- ✅ Utilise KB + Memory (`✅ KB PRIORITAIRE` + `✅ MEMORY`)
- ✅ Web Search **DERNIER RECOURS** si KB insuffisant

**Si échec**:
- Temps >5s → vérifier timeout Ollama (logs `[INFO] Ollama réponse en Xs`)
- Si Web Search systématique → augmenter top_k KB à 20

---

### Test 4: Question Hors KB (Web Search)
**Question**: `Quelle est la météo prévue pour le prochain GP ?`

**Comportement attendu**:
- ✅ Web Search activé (`⚠️ LLM incertain, Web Search dernier recours`)
- ✅ Temps <5s
- ✅ Répond ou indique "je n'ai pas d'info temps réel"

---

## 🧪 Tests Automatisés

### Lancer la suite de tests
```powershell
python test_optimizations.py
```

**Tests exécutés**:
1. ✅ Chargement KB (vérification ≥10 docs)
2. ✅ Recherche KB top_k=15 (vérification retour)
3. ✅ Memory Long Terme (vérification contexte)
4. ✅ Réponse KB hit <2s
5. ✅ Réponse Standings <2s
6. ✅ Réponse Complexe <3s

**Résultat attendu**: `🎉 TOUS LES TESTS SONT RÉUSSIS!`

---

## 📊 Analyser les Logs

### Logs importants à surveiller

#### ✅ KB chargée correctement
```
✅ FAISS index validé: 2233 vecteurs, 45 documents, dim=384
```

#### ✅ KB utilisée en priorité
```
✅ KB PRIORITAIRE: 15 chunks utilisés (score ≥0.35)
```

#### ✅ Memory intégrée
```
✅ MEMORY: Contexte long terme récupéré (1234 chars)
```

#### ✅ Temps Ollama acceptable
```
[INFO] Ollama réponse en 1.23s (456 chars)
```

#### ⚠️ Web Search (rare)
```
⚠️ LLM incertain avec KB+Memory, tentative Web Search (dernier recours)...
✅ Web Search utilisé en dernier recours
```

#### ❌ Problèmes potentiels
```
❌ KB: Aucun résultat (score <0.35)  → Enrichir KB ou abaisser score
❌ Timeout Ollama                     → Vérifier daemon, réduire prompt
❌ HTTP error fetching StandF1       → Vérifier connexion internet
```

---

## 🔍 Débogage

### Problème: Réponses trop lentes (>3s)

**Diagnostics**:
1. Vérifier logs Ollama → temps de génération
   ```
   [INFO] Ollama réponse en X.XXs
   ```
   - Si >3s → Ollama surchargé, redémarrer daemon
   - Si >5s → Prompt trop long, vérifier `estimate_tokens()`

2. Vérifier KB hits
   ```
   ✅ KB PRIORITAIRE: X chunks
   ```
   - Si 0 chunks → Augmenter top_k à 20 ou abaisser score à 0.3
   - Si <5 chunks → Enrichir KB avec plus de docs

3. Vérifier Web Search usage
   ```
   ⚠️ LLM incertain, Web Search dernier recours
   ```
   - Si >20% des requêtes → KB insuffisante, enrichir contenu

**Solutions**:
- Augmenter `num_predict` de 150 → 200 (si réponses trop courtes)
- Abaisser `min_score` de 0.35 → 0.3 (si KB miss fréquents)
- Augmenter `top_k` de 15 → 20 (pour plus de contexte)
- Redémarrer Ollama (`ollama serve`)

---

### Problème: KB ne retourne aucun résultat

**Diagnostics**:
```powershell
# Vérifier index FAISS
ls knowledge_base/faiss_index.bin
ls knowledge_base/faiss_metadata.pkl

# Recharger KB manuellement
curl http://localhost:8000/kb/reload
```

**Solutions**:
1. Supprimer index corrompu et recharger
   ```powershell
   rm knowledge_base/faiss_index.bin
   rm knowledge_base/faiss_metadata.pkl
   # Redémarrer app.py
   ```

2. Enrichir KB avec plus de docs
   ```powershell
   # Ajouter fichiers .md dans knowledge_base/
   # Recharger
   curl http://localhost:8000/kb/reload
   ```

---

### Problème: Ollama timeout fréquent

**Diagnostics**:
```powershell
# Vérifier daemon Ollama
ollama list
ollama ps
```

**Solutions**:
1. Redémarrer daemon
   ```powershell
   # Tuer processus
   taskkill /F /IM ollama.exe
   # Relancer
   ollama serve
   ```

2. Vérifier modèle
   ```powershell
   ollama pull qwen2.5:3b
   ```

3. Augmenter timeout dans `f1_bot.py`
   ```python
   OLLAMA_TIMEOUT = 20  # Au lieu de 15
   ```

---

## 📈 Métriques de Succès

### Objectifs Atteints ✅
- [x] KB chargée avec ≥2000 chunks
- [x] KB utilisée en priorité (>90% requêtes)
- [x] Memory intégrée (>80% requêtes)
- [x] Web Search <10% requêtes
- [x] Temps réponse <2s (questions simples)
- [x] Temps réponse <3s (questions complexes)

### Métriques à Surveiller
- **KB Hit Rate**: >90% attendu
- **Memory Usage**: >80% attendu
- **Web Search Rate**: <10% attendu
- **Latence moyenne**: <2s attendu
- **Latence P95**: <3s attendu

---

## 🎯 Ajustements Post-Tests

### Si taux Web Search >20%
```python
# Dans f1_bot.py
kb_results = kb.search(user_question, top_k=20, min_score=0.3)  # Au lieu de 15/0.35
```

### Si réponses trop courtes
```python
# Dans optimized_ollama.py
num_predict: int = 200  # Au lieu de 150
```

### Si timeout Ollama fréquent
```python
# Dans f1_bot.py
OLLAMA_TIMEOUT = 20  # Au lieu de 15
```

### Si KB miss fréquent
1. Enrichir `knowledge_base/` avec plus de fichiers .md
2. Recharger: `curl http://localhost:8000/kb/reload`

---

## 📞 Aide

**Voir les logs détaillés**:
```powershell
# Dans terminal app.py, augmenter verbosité
set KB_LOG_VERBOSE=1
python app.py
```

**Tester endpoint santé**:
```powershell
curl http://localhost:8000/health
```

**Vérifier KB**:
```powershell
curl http://localhost:8000/kb/docs
```

---

**Dernière mise à jour**: 13 janvier 2026
