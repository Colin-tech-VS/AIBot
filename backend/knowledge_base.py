"""
Knowledge Base Manager pour F1 Chatbot
Gère les connaissances locales (documents markdown, FAQs, règlements)
Supporte recherche simple et Chromadb (optionnel pour embeddings)
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional
import os
import csv

# Essayer importer chromadb, sinon utiliser recherche simple
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("[INFO] ChromaDB non disponible. Utilisant recherche simple.")


# -----------------------------------
# Chemin Knowledge Base
# -----------------------------------
KB_DIR = Path(__file__).parent.parent / "knowledge_base"
KB_DIR.mkdir(exist_ok=True)


# -----------------------------------
# Modèles
# -----------------------------------
class KnowledgeDoc(dict):
    """Document de connaissances"""
    def __init__(self, doc_id: str, title: str, content: str, category: str = "general"):
        super().__init__()
        self.doc_id = doc_id
        self.title = title
        self.content = content
        self.category = category  # f1-rules, teams, drivers, history, etc.


# -----------------------------------
# Knowledge Base (Simple + ChromaDB optionnel)
# -----------------------------------
class KnowledgeBase:
    def __init__(self, use_chromadb: bool = True):
        self.use_chromadb = use_chromadb and CHROMADB_AVAILABLE
        self.docs: Dict[str, KnowledgeDoc] = {}
        self.client = None
        self.collection = None
        
        if self.use_chromadb:
            self._init_chromadb()
        
        self._load_default_knowledge()
    
    def _init_chromadb(self):
        """Initialize ChromaDB for embeddings"""
        try:
            settings = Settings(
                chroma_db_impl="duckdb",
                persist_directory=str(KB_DIR / "chroma"),
                anonymized_telemetry=False,
            )
            self.client = chromadb.Client(settings)
            self.collection = self.client.get_or_create_collection(
                name="f1_knowledge",
                metadata={"hnsw:space": "cosine"}
            )
            print("[INFO] ChromaDB initialized for knowledge base")
        except Exception as e:
            print(f"[WARN] ChromaDB init failed: {e}. Using simple search.")
            self.use_chromadb = False
    
    def _load_default_knowledge(self):
        """Charger les connaissances par défaut F1"""
        default_docs = [
            KnowledgeDoc(
                "f1_rules_basic",
                "Règles de base F1",
                """
                **F1 Règles de base 2025** :
                - **Distance de la course** : 307 km (approximativement 2 heures)
                - **Points au podium** : 1er=25pts, 2e=18pts, 3e=15pts, 4e=12pts, 5e=10pts, 6e=8pts, 7e=6pts, 8e=4pts, 9e=2pts, 10e=1pt
                - **Point du meilleur tour** : 1 point (si dans les 10 premiers)
                - **Drapeau rouge** : Course arrêtée si danger immédiat
                - **ERS (Energy Recovery System)** : Récupération d'énergie contrôlée
                - **Sécurité** : Halo obligatoire, KERS, systèmes de protection
                """,
                "f1-rules"
            ),
            KnowledgeDoc(
                "f1_history",
                "Histoire de la F1",
                """
                **Histoire de la Formule 1** :
                - **Fondation** : 1950, premier championnat officiel
                - **Évolutions majeures** :
                  - 1960s : Monocoques introduites (lotus)
                  - 1970s : Aérodynamique révolutionnaire
                  - 1980s : Turbo era
                  - 1990s : Williams dominance, V10 engines
                  - 2000s : Ferrari dominance (Schumacher)
                  - 2010s : Mercedes dominance (Hamilton)
                  - 2020s : Red Bull, Verstappen era
                - **Pilotes légendaires** : Senna, Prost, Schumacher, Hamilton, Verstappen
                """,
                "history"
            ),
            KnowledgeDoc(
                "current_teams_2025",
                "Équipes F1 2025",
                """
                **Équipes de F1 2025** :
                1. **Red Bull Racing** - Max Verstappen, Sergio Pérez
                2. **Mercedes** - Lewis Hamilton, George Russell
                3. **Ferrari** - Charles Leclerc, Carlos Sainz
                4. **McLaren** - Lando Norris, Oscar Piastri
                5. **Aston Martin** - Fernando Alonso, Lance Stroll
                6. **Alpine** - Pierre Gasly, Esteban Ocon
                7. **Haas F1** - Kevin Magnussen, Nico Hülkenberg
                8. **Racing Bulls** - Yuki Tsunoda, Liam Lawson
                9. **Williams** - Alexander Albon, Carlos Sainz Jr.
                10. **Kick Sauber** - Zhou Guanyu, Valtteri Bottas
                """,
                "teams"
            ),
            KnowledgeDoc(
                "driver_facts",
                "Faits Pilotes F1",
                """
                **Faits clés pilotes actuels** :
                - **Max Verstappen** : Recordman de victoires (99+), 3x champion F1
                - **Lewis Hamilton** : 7x champion F1, recordman historique (bientôt chez Ferrari)
                - **Charles Leclerc** : Jeune talent Ferrari, approx 5 victoires
                - **George Russell** : Mercedes, talent émergent, 1 victoire
                - **Fernando Alonso** : Vétéran, 2x champion, toujours compétitif
                """,
                "drivers"
            ),
            KnowledgeDoc(
                "faq_f1",
                "FAQ F1",
                """
                **Questions fréquentes F1** :
                
                Q: Combien de races par saison ?
                R: Approx 24 races (calendrier 2025)
                
                Q: Quelle est la plus longue piste F1 ?
                R: Le circuit de Monza (5.793 km) ou Spa (7.004 km)
                
                Q: Qui est le plus jeune champions F1 ?
                R: Max Verstappen (18 ans à sa première victoire), Sebastian Vettel (23 ans champion)
                
                Q: Combien de temps dure une course ?
                R: Environ 2 heures (distance : 307 km)
                """,
                "faq"
            ),
        ]
        
        for doc in default_docs:
            self.add_document(doc)
    
    def add_document(self, doc: KnowledgeDoc):
        """Ajouter un document à la knowledge base"""
        self.docs[doc.doc_id] = doc
        
        if self.use_chromadb and self.collection:
            try:
                self.collection.add(
                    ids=[doc.doc_id],
                    documents=[doc.content],
                    metadatas=[{"title": doc.title, "category": doc.category}]
                )
                print(f"[INFO] Document ajouté à ChromaDB: {doc.title}")
            except Exception as e:
                print(f"[WARN] ChromaDB add failed: {e}")
    
    def search(self, query: str, top_k: int = 3) -> List[str]:
        """Rechercher des documents pertinents"""
        if self.use_chromadb and self.collection:
            try:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k
                )
                if results and results["documents"]:
                    return results["documents"][0]
            except Exception as e:
                print(f"[WARN] ChromaDB search failed: {e}")
        
        # Fallback : recherche simple (keyword matching)
        return self._simple_search(query, top_k)
    
    def _simple_search(self, query: str, top_k: int = 3) -> List[str]:
        """Recherche simple par mots-clés - améliorée pour chercher en profondeur"""
        query_lower = query.lower()
        query_words = query_lower.split()
        scores = []
        
        for doc_id, doc in self.docs.items():
            # Combiner titre + contenu pour la recherche
            full_text = (doc.title + " " + doc.content).lower()
            
            # Score 1: Nombre exact de mots trovés (exact match)
            exact_score = sum(1 for word in query_words if word in full_text)
            
            # Score 2: Correspondance partielle (si "yves" dans le doc, matchera "yves d'epitech")
            partial_score = 0
            for word in query_words:
                if len(word) > 2:  # Ignorer les petits mots
                    if word in full_text:
                        partial_score += 2
                    # Chercher aussi les variantes (pluriel, etc.)
                    if word.rstrip('s') in full_text or word + 's' in full_text:
                        partial_score += 1
            
            total_score = exact_score * 2 + partial_score
            
            # Bonus si titre correspond exactement
            if query_lower in doc.title.lower():
                total_score += 10
            
            if total_score > 0:
                scores.append((total_score, doc.content))
        
        # Trier par score décroissant et retourner top_k
        scores.sort(reverse=True, key=lambda x: x[0])
        return [content for _, content in scores[:top_k]]
    
    def get_all_docs(self) -> List[KnowledgeDoc]:
        """Retourner tous les documents"""
        return list(self.docs.values())
    
    def load_from_files(self, kb_dir: Path = KB_DIR):
        """Charger des documents depuis des fichiers Markdown et CSV.

        - .md: contenu complet du fichier comme `content`.
               `doc_id` = nom du fichier sans extension, `title` = nom capitalisé.
        - .csv: header requis: id,title,content[,category].
               Chaque ligne devient un document.
        """
        if not kb_dir.exists():
            return
        # 1) Fichiers Markdown
        for md_file in kb_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding='utf-8')
                doc_id = md_file.stem
                title = md_file.stem.replace("_", " ").title()
                doc = KnowledgeDoc(doc_id, title, content, "custom")
                self.add_document(doc)
                print(f"[INFO] Fichier markdown chargé: {md_file.name}")
            except Exception as e:
                print(f"[WARN] Erreur lecture {md_file.name}: {e}")
        
        # 2) Fichiers CSV (schéma simple)
        for csv_file in kb_dir.glob("*.csv"):
            try:
                with csv_file.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    fieldnames = [h.strip() for h in (reader.fieldnames or [])]
                    required = {"id", "title", "content"}
                    if not fieldnames or not required.issubset(set(fieldnames)):
                        print(f"[WARN] Schéma CSV invalide dans {csv_file.name}. Colonnes requises: id,title,content[,category]")
                        continue
                    count = 0
                    for row in reader:
                        doc_id = (row.get("id") or "").strip()
                        title = (row.get("title") or "").strip()
                        content = (row.get("content") or "").strip()
                        category = (row.get("category") or "custom").strip() or "custom"
                        if not doc_id or not title or not content:
                            continue
                        self.add_document(KnowledgeDoc(doc_id, title, content, category))
                        count += 1
                    print(f"[INFO] Fichier CSV chargé: {csv_file.name} ({count} documents)")
            except Exception as e:
                print(f"[WARN] Échec chargement CSV {csv_file.name}: {e}")
    
    def export_json(self, output_file: Path):
        """Exporter knowledge base en JSON"""
        data = {
            doc_id: {
                "title": doc.title,
                "content": doc.content,
                "category": doc.category
            }
            for doc_id, doc in self.docs.items()
        }
        output_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"[INFO] Knowledge base exportée: {output_file}")


# -----------------------------------
# Instance globale
# -----------------------------------
_kb_instance: Optional[KnowledgeBase] = None


def get_knowledge_base(use_chromadb: bool = True) -> KnowledgeBase:
    """Obtenir l'instance globale de knowledge base"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase(use_chromadb=use_chromadb)
        _kb_instance.load_from_files()
    return _kb_instance
