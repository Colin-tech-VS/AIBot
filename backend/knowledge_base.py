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
        
        # Charger les fichiers du répertoire (pas de docs par défaut hardcodés)
        # Cela permet de contrôler la KB via les fichiers uniquement
        self.load_from_files()
    
    def _init_chromadb(self):
        """Initialize ChromaDB for embeddings"""
        try:
            # Configuration moderne ChromaDB 1.4.0+
            self.client = chromadb.PersistentClient(
                path=str(KB_DIR / "chroma")
            )
            self.collection = self.client.get_or_create_collection(
                name="f1_knowledge",
                metadata={"hnsw:space": "cosine"}
            )
            doc_count = self.collection.count()
            print(f"[INFO] ChromaDB initialized: {doc_count} documents in collection")
        except Exception as e:
            print(f"[WARN] ChromaDB init failed: {e}. Using simple search.")
            self.use_chromadb = False
    
    
    def add_document(self, doc: KnowledgeDoc, skip_chromadb: bool = False):
        """Ajouter un document à la knowledge base"""
        self.docs[doc.doc_id] = doc

        # Ne pas ajouter à ChromaDB si skip_chromadb=True (car déjà persisté)
        if not skip_chromadb and self.use_chromadb and self.collection:
            try:
                # Utiliser upsert pour éviter les erreurs de doublons
                self.collection.upsert(
                    ids=[doc.doc_id],
                    documents=[doc.content],
                    metadatas=[{"title": doc.title, "category": doc.category}]
                )
            except Exception as e:
                print(f"[WARN] ChromaDB upsert failed for {doc.title}: {e}")
    
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
        """Recherche simple par mots-clés - améliorée pour chercher en profondeur
        
        Avec seuil minimum de pertinence pour éviter les faux positifs
        """
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
            
            # SEUIL MINIMUM: au moins 2 points (au moins 1 mot matché ou titre partiel)
            if total_score >= 2:
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

        # Si ChromaDB est actif et contient déjà des documents, charger depuis ChromaDB
        if self.use_chromadb and self.collection and self.collection.count() > 0:
            print(f"[INFO] Chargement depuis ChromaDB ({self.collection.count()} documents)")
            try:
                # Récupérer tous les documents de ChromaDB
                results = self.collection.get(
                    include=["documents", "metadatas"]
                )
                if results and results["ids"]:
                    for i, doc_id in enumerate(results["ids"]):
                        content = results["documents"][i]
                        metadata = results["metadatas"][i]
                        title = metadata.get("title", doc_id)
                        category = metadata.get("category", "custom")
                        doc = KnowledgeDoc(doc_id, title, content, category)
                        # Ajouter au dict local SANS re-ajouter à ChromaDB
                        self.add_document(doc, skip_chromadb=True)
                    print(f"[INFO] {len(results['ids'])} documents chargés depuis ChromaDB")
                    return
            except Exception as e:
                print(f"[WARN] Erreur chargement depuis ChromaDB: {e}")
                print("[INFO] Chargement depuis fichiers CSV...")

        # Sinon, charger depuis les fichiers CSV/MD
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
        total_csv_docs = 0
        for csv_file in kb_dir.glob("*.csv"):
            try:
                with csv_file.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.DictReader(f)
                    fieldnames = [h.strip() for h in (reader.fieldnames or [])]
                    required = {"id", "title", "content"}
                    if not fieldnames or not required.issubset(set(fieldnames)):
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
                    total_csv_docs += count
            except Exception as e:
                print(f"[WARN] Échec chargement CSV {csv_file.name}: {e}")

        if total_csv_docs > 0:
            print(f"[INFO] Total: {total_csv_docs} documents chargés depuis fichiers CSV")
    
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


def reload_knowledge_base() -> KnowledgeBase:
    """Forcer le rechargement de la knowledge base (vide le cache et recharge les fichiers)"""
    global _kb_instance
    _kb_instance = None
    _kb_instance = KnowledgeBase(use_chromadb=True)
    _kb_instance.load_from_files()
    print(f"[INFO] Knowledge base rechargée. {len(_kb_instance.docs)} documents en mémoire.")
    return _kb_instance
