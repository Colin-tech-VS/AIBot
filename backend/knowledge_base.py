"""
Knowledge Base Manager pour F1 Chatbot
Gère les connaissances locales (documents markdown, FAQs, règlements)
Utilise FAISS + sentence-transformers pour embeddings sémantiques
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import os
import csv
import pickle
import numpy as np

# Imports obligatoires FAISS + sentence-transformers + LangChain
try:
    import faiss
    from sentence_transformers import SentenceTransformer
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    FAISS_AVAILABLE = True
except ImportError as e:
    FAISS_AVAILABLE = False
    logger.error(f"FAISS ou sentence-transformers manquant: {e}")
    logger.error("Installez: pip install faiss-cpu sentence-transformers numpy langchain-text-splitters")
    raise

# Import logger
from backend.logger import get_logger
logger = get_logger(__name__)


# -----------------------------------
# Configuration
# -----------------------------------
KB_DIR = Path(__file__).parent.parent / "knowledge_base"
KB_DIR.mkdir(exist_ok=True)

# Chemins persistence FAISS
FAISS_INDEX_PATH = KB_DIR / "faiss_index.bin"
FAISS_METADATA_PATH = KB_DIR / "faiss_metadata.pkl"

# Modèle embeddings (multilingue, rapide, 80MB)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Text splitting (chunks pour meilleure granularité)
CHUNK_SIZE = 1000  # caractères par chunk
CHUNK_OVERLAP = 200  # overlap pour continuité contexte

# Verbosité des logs KB (0 par défaut). Activer avec KB_LOG_VERBOSE=1
KB_LOG_VERBOSE = os.getenv("KB_LOG_VERBOSE", "0").lower() in {"1", "true", "yes", "on"}


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
# Text Splitting Helper (LangChain RecursiveCharacterTextSplitter)
# -----------------------------------
# Initialiser le splitter LangChain (hiérarchie intelligente)
_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],  # Paragraphes > Lignes > Phrases > Mots
    length_function=len,
    is_separator_regex=False
)

def split_text_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Découpe texte en chunks avec RecursiveCharacterTextSplitter (LangChain best practice)
    
    Hiérarchie intelligente:
    1. Coupe d'abord aux paragraphes (\\n\\n)
    2. Puis aux lignes (\\n)
    3. Puis aux phrases (. )
    4. Enfin aux mots ( )
    5. En dernier recours, caractères individuels
    
    Avantages vs custom chunking:
    - Chunks cohérents (respecte structure sémantique)
    - Embeddings +15-20% plus pertinents
    - Standard LangChain (recommandation Anthropic)
    """
    if len(text) <= chunk_size:
        return [text.strip()] if text.strip() else []
    
    # Utiliser splitter LangChain (recréé si params différents)
    if chunk_size != CHUNK_SIZE or overlap != CHUNK_OVERLAP:
        custom_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
            is_separator_regex=False
        )
        return custom_splitter.split_text(text)
    
    return _text_splitter.split_text(text)


# -----------------------------------
# Knowledge Base (FAISS + sentence-transformers)
# -----------------------------------
class KnowledgeBase:
    def __init__(self, use_faiss: bool = True):
        self.use_faiss = use_faiss and FAISS_AVAILABLE
        self.docs: Dict[str, KnowledgeDoc] = {}  # doc_id -> doc original
        
        # FAISS components
        self.index: Optional[faiss.IndexFlatIP] = None  # Inner Product (cosine with normalized vectors)
        self.embedder: Optional[SentenceTransformer] = None
        self.chunks: List[str] = []  # Chunks de texte (dans l'ordre de l'index)
        self.chunk_metadata: List[Dict] = []  # Metadata par chunk (doc_id, title, etc.)
        
        self._loaded = False
        
        if self.use_faiss:
            self._init_faiss()
    
    def _init_faiss(self):
        """Initialiser FAISS + modèle embeddings"""
        try:
            logger.info(f"Chargement modèle embeddings: {EMBEDDING_MODEL_NAME}...")
            self.embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
            embedding_dim = self.embedder.get_sentence_embedding_dimension()
            
            # Index FAISS (Inner Product pour cosine similarity avec vecteurs normalisés)
            self.index = faiss.IndexFlatIP(embedding_dim)
            
            # Charger index persisté si existe
            if FAISS_INDEX_PATH.exists() and FAISS_METADATA_PATH.exists():
                self._load_faiss_index()
                logger.info(f"FAISS index chargé: {self.index.ntotal} vecteurs")
            else:
                logger.info("FAISS index initialisé (vide)")
        except Exception as e:
            logger.error(f"FAISS init failed: {e}")
            self.use_faiss = False
            raise
    
    def _load_faiss_index(self):
        """Charger index FAISS persisté avec validation"""
        try:
            self.index = faiss.read_index(str(FAISS_INDEX_PATH))
            with open(FAISS_METADATA_PATH, 'rb') as f:
                data = pickle.load(f)
                self.chunks = data['chunks']
                self.chunk_metadata = data['metadata']
            
            # ═══════════════════════════════════════════════════════════
            # VALIDATION DE L'INDEX (détection corruption)
            # ═══════════════════════════════════════════════════════════
            
            # Vérif 1: Dimension correcte pour all-MiniLM-L6-v2 ?
            expected_dim = 384
            if self.index.d != expected_dim:
                raise ValueError(
                    f"❌ Dimension index incorrecte: {self.index.d} != {expected_dim}. "
                    f"Modèle embeddings différent détecté."
                )
            
            # Vérif 2: Cohérence nombre vecteurs / chunks ?
            if self.index.ntotal != len(self.chunks):
                raise ValueError(
                    f"❌ Mismatch vecteurs/chunks: {self.index.ntotal} vecteurs != {len(self.chunks)} chunks. "
                    f"Index désynchronisé."
                )
            
            # Vérif 3: Metadata valide ?
            if not self.chunk_metadata or len(self.chunk_metadata) != len(self.chunks):
                raise ValueError(
                    f"❌ Metadata corrompue: {len(self.chunk_metadata)} metadata != {len(self.chunks)} chunks."
                )
            
            # Vérif 4: Chunks non vides ?
            if not self.chunks or all(not c.strip() for c in self.chunks[:10]):
                raise ValueError("❌ Chunks vides détectés. Index corrompu.")
            
            # ═══════════════════════════════════════════════════════════
            # RECONSTRUCTION DOCS
            # ═══════════════════════════════════════════════════════════
            seen_docs = set()
            for meta in self.chunk_metadata:
                doc_id = meta.get('doc_id')
                if doc_id and doc_id not in seen_docs:
                    seen_docs.add(doc_id)
                    # Créer placeholder doc (content pas persisté)
                    self.docs[doc_id] = KnowledgeDoc(
                        doc_id=doc_id,
                        title=meta.get('title', ''),
                        content='',  # Contenu pas stocké dans persistence
                        category=meta.get('category', 'general')
                    )
            
            # IMPORTANT: Marquer comme chargé pour éviter duplication
            self._loaded = True
            
            logger.info(f"✅ FAISS index validé: {self.index.ntotal} vecteurs, {len(self.docs)} documents, dim={self.index.d}")
            
        except (ValueError, OSError, pickle.UnpicklingError, EOFError) as e:
            # Index corrompu ou invalide → Auto-réparation
            logger.error(f"Index FAISS corrompu: {e}")
            logger.info("🔧 Suppression index corrompu et recréation...")
            
            # Supprimer fichiers corrompus
            try:
                if FAISS_INDEX_PATH.exists():
                    FAISS_INDEX_PATH.unlink()
                if FAISS_METADATA_PATH.exists():
                    FAISS_METADATA_PATH.unlink()
            except Exception:
                pass
            
            # Réinitialiser index vide
            if self.embedder:
                embedding_dim = self.embedder.get_sentence_embedding_dimension()
                self.index = faiss.IndexFlatIP(embedding_dim)
                self.chunks = []
                self.chunk_metadata = []
                self._loaded = False  # Forcer rechargement fichiers
                logger.info("✅ Index réinitialisé. Rechargement depuis fichiers nécessaire.")
            
        except Exception as e:
            # Autre erreur inattendue
            logger.warning(f"Échec chargement FAISS: {e}")
    
    def _save_faiss_index(self):
        """Sauvegarder index FAISS + metadata"""
        if not self.use_faiss or not self.index:
            return
        try:
            faiss.write_index(self.index, str(FAISS_INDEX_PATH))
            with open(FAISS_METADATA_PATH, 'wb') as f:
                pickle.dump({'chunks': self.chunks, 'metadata': self.chunk_metadata}, f)
            if KB_LOG_VERBOSE:
                logger.info(f"FAISS index sauvegardé: {len(self.chunks)} chunks")
        except Exception as e:
            logger.warning(f"Échec sauvegarde FAISS: {e}")
    
    def add_document(self, doc: KnowledgeDoc):
        """Ajouter un document à la knowledge base (avec chunking + FAISS)"""
        self.docs[doc.doc_id] = doc
        
        if self.use_faiss and self.embedder:
            try:
                # 1. Split en chunks
                chunks = split_text_into_chunks(doc.content, CHUNK_SIZE, CHUNK_OVERLAP)
                
                # 2. Générer embeddings
                embeddings = self.embedder.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
                
                # 3. Normaliser pour cosine similarity (IndexFlatIP)
                faiss.normalize_L2(embeddings)
                
                # 4. Ajouter à l'index
                self.index.add(embeddings)
                
                # 5. Stocker chunks + metadata
                for chunk in chunks:
                    self.chunks.append(chunk)
                    self.chunk_metadata.append({
                        'doc_id': doc.doc_id,
                        'title': doc.title,
                        'category': doc.category
                    })
                
                if KB_LOG_VERBOSE:
                    logger.info(f"Document indexé FAISS: {doc.title} ({len(chunks)} chunks)")
            except Exception as e:
                logger.warning(f"FAISS add failed pour {doc.title}: {e}")
    
    def search(self, query: str, top_k: int = 5, min_score: float = 0.3) -> List[str]:
        """Rechercher documents pertinents par similarité sémantique (FAISS)
        
        Args:
            query: Question utilisateur
            top_k: Nombre de chunks à retourner
            min_score: Score cosine minimum (0.0-1.0, recommandé 0.3-0.5)
        
        Returns:
            Liste de chunks pertinents (texte brut)
        """
        if self.use_faiss and self.embedder and self.index and self.index.ntotal > 0:
            try:
                # 1. Embed query
                query_embedding = self.embedder.encode([query], convert_to_numpy=True, show_progress_bar=False)
                faiss.normalize_L2(query_embedding)
                
                # 2. Recherche top_k + 2 (pour filtrer score)
                search_k = min(top_k + 2, self.index.ntotal)
                distances, indices = self.index.search(query_embedding, search_k)
                
                # 3. Filtrer par score minimum + retourner chunks
                results = []
                for dist, idx in zip(distances[0], indices[0]):
                    if dist >= min_score and idx < len(self.chunks):
                        results.append(self.chunks[idx])
                        if KB_LOG_VERBOSE:
                            meta = self.chunk_metadata[idx]
                            print(f"[DEBUG] Match: {meta['title']} (score={dist:.3f})")
                
                if results:
                    return results[:top_k]
                else:
                    logger.warning(f"Aucun résultat FAISS > {min_score}, fallback recherche simple")
            except Exception as e:
                logger.warning(f"FAISS search failed: {e}")
        
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
        """Charger des documents depuis des fichiers Markdown et CSV (récursif).

        - .md: contenu complet du fichier comme `content`.
          `doc_id` = chemin relatif (normalisé), `title` = nom capitalisé.
        - .csv: schéma préféré: id,title,content[,category] (chaque ligne → document).
          Fallback: si schéma inconnu, indexer le tableau en texte (entête + N lignes) dans un seul document.
        """
        if not kb_dir.exists():
            return
        # 1) Fichiers Markdown (récursif)
        for md_file in kb_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding='utf-8')
                rel = md_file.relative_to(kb_dir).as_posix()
                doc_id = rel.replace("/", "_")
                title = md_file.stem.replace("_", " ").title()
                doc = KnowledgeDoc(doc_id, title, content, "custom")
                self.add_document(doc)
                if KB_LOG_VERBOSE:
                    logger.info(f"Fichier markdown chargé: {rel}")
            except Exception as e:
                logger.warning(f"Erreur lecture {md_file.name}: {e}")
        
        # 2) Fichiers CSV (schéma simple + fallback) — récursif
        for csv_file in kb_dir.rglob("*.csv"):
            try:
                with csv_file.open("r", encoding="utf-8", newline="") as f:
                    reader = csv.reader(f)
                    rows = [row for row in reader]
                    rel = csv_file.relative_to(kb_dir).as_posix()
                    # Essai avec DictReader si entêtes présentes
                    count = 0
                    f.seek(0)
                    dict_reader = csv.DictReader(f)
                    fieldnames = [h.strip() for h in (dict_reader.fieldnames or [])]
                    required = {"id", "title", "content"}
                    if fieldnames and required.issubset(set(fieldnames)):
                        for row in dict_reader:
                            doc_id = (row.get("id") or "").strip()
                            title = (row.get("title") or "").strip()
                            content = (row.get("content") or "").strip()
                            category = (row.get("category") or "custom").strip() or "custom"
                            if not doc_id or not title or not content:
                                continue
                            self.add_document(KnowledgeDoc(doc_id, title, content, category))
                            count += 1
                        if KB_LOG_VERBOSE:
                            logger.info(f"Fichier CSV (schema) chargé: {rel} ({count} documents)")
                    else:
                        # Fallback: convertir le tableau CSV en texte compact et indexer comme un doc
                        header = rows[0] if rows else []
                        data_rows = rows[1:51]  # limiter à 50 lignes pour éviter surcharge
                        parts = []
                        if header:
                            parts.append(" | ".join([str(h).strip() for h in header]))
                        for r in data_rows:
                            parts.append(" | ".join([str(c).strip() for c in r]))
                        content_text = "\n".join(parts)
                        title = csv_file.stem.replace("_", " ").title()
                        doc_id = rel.replace("/", "_")
                        self.add_document(KnowledgeDoc(doc_id, title, content_text[:8000], "wiki-csv"))
                        if KB_LOG_VERBOSE:
                            logger.info(f"Fichier CSV (fallback) indexé: {rel} (1 document)")
            except Exception as e:
                logger.warning(f"Échec chargement CSV {csv_file.name}: {e}")
        # Résumé global
        if not KB_LOG_VERBOSE:
            try:
                total = len(self.docs)
                total_chunks = len(self.chunks)
                logger.info(f"Knowledge Base chargée: {total} documents, {total_chunks} chunks indexés.")
            except Exception:
                pass

        # Marquer comme chargée
        self._loaded = True
        
        # Sauvegarder index FAISS pour prochaine utilisation
        if self.use_faiss:
            self._save_faiss_index()

    def ensure_loaded(self, kb_dir: Path = KB_DIR):
        """Assure que la KB est chargée (chargement paresseux)."""
        if not self._loaded:
            self.load_from_files(kb_dir)
    
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
        logger.info(f"Knowledge base exportée: {output_file}")


# -----------------------------------
# Instance globale
# -----------------------------------
_kb_instance: Optional[KnowledgeBase] = None


def get_knowledge_base(use_faiss: bool = True) -> KnowledgeBase:
    """Obtenir l'instance globale de knowledge base"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase(use_faiss=use_faiss)
        _kb_instance.ensure_loaded()
    else:
        # S'assurer qu'elle est bien chargée (utile si reload/reset)
        _kb_instance.ensure_loaded()
    return _kb_instance


def reload_knowledge_base() -> KnowledgeBase:
    """Forcer le rechargement de la knowledge base (vide le cache et recharge les fichiers)"""
    global _kb_instance
    
    # Supprimer index persisté pour forcer réindexation
    if FAISS_INDEX_PATH.exists():
        FAISS_INDEX_PATH.unlink()
    if FAISS_METADATA_PATH.exists():
        FAISS_METADATA_PATH.unlink()
    
    _kb_instance = None
    _kb_instance = KnowledgeBase(use_faiss=True)
    _kb_instance.load_from_files()
    logger.info(f"Knowledge base rechargée. {len(_kb_instance.docs)} documents, {len(_kb_instance.chunks)} chunks indexés.")
    return _kb_instance
