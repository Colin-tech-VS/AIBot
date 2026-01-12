"""
Script pour importer automatiquement un dossier de CSV vers ChromaDB
"""

import csv
import sys
from pathlib import Path
from typing import Dict

# Ajouter le repertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.knowledge_base import get_knowledge_base, KnowledgeDoc


def process_folder_to_kb(folder_path: str) -> Dict:
    """
    Traiter un dossier et ajouter tous les CSV a la KB avec conversion ChromaDB

    Args:
        folder_path: Chemin absolu vers le dossier a traiter

    Returns:
        Dict avec status, count, et details
    """
    try:
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            return {"status": "error", "message": "Dossier invalide", "count": 0}

        kb = get_knowledge_base()
        count = 0

        print(f"\n[INFO] Traitement du dossier: {folder}")

        # Parcourir recursivement tous les CSV
        for csv_file in folder.rglob("*.csv"):
            try:
                # Ignorer les fichiers deja convertis (*_kb.csv)
                if csv_file.stem.endswith("_kb"):
                    continue

                # Lire le CSV
                with csv_file.open('r', encoding='utf-8', errors='ignore') as f:
                    reader = csv.DictReader(f)
                    fieldnames = reader.fieldnames

                    if not fieldnames:
                        continue

                    # Si c'est deja au format KB (id, title, content)
                    if set(['id', 'title', 'content']).issubset(set(fieldnames)):
                        for row in reader:
                            doc_id = row.get('id', '').strip()
                            title = row.get('title', '').strip()
                            content = row.get('content', '').strip()
                            category = row.get('category', 'imported').strip() or 'imported'

                            if doc_id and title and content:
                                doc = KnowledgeDoc(doc_id, title, content, category)
                                kb.add_document(doc)
                                count += 1
                    else:
                        # Sinon, convertir le CSV entier en un document
                        # Relire le fichier
                        f.seek(0)
                        reader = csv.DictReader(f)
                        rows = list(reader)

                        if not rows:
                            continue

                        # Creer le contenu
                        content_lines = []
                        for row in rows:
                            line_parts = [f"{k}: {v}" for k, v in row.items() if v and v.strip()]
                            if line_parts:
                                content_lines.append(", ".join(line_parts))

                        if not content_lines:
                            continue

                        content = "\n".join(content_lines)

                        # Generer doc_id unique base sur le chemin relatif
                        rel_path = csv_file.relative_to(folder)
                        doc_id = str(rel_path).replace("\\", "_").replace("/", "_").replace(".csv", "")
                        title = csv_file.stem.replace("_", " ").title()

                        doc = KnowledgeDoc(doc_id, title, content, "imported")
                        kb.add_document(doc)
                        count += 1

            except Exception as e:
                print(f"[WARN] Erreur lecture {csv_file.name}: {e}")
                continue

        print(f"[SUCCESS] {count} documents ajoutes depuis {folder.name}")

        # Afficher le total dans ChromaDB
        if kb.collection:
            total = kb.collection.count()
            print(f"[INFO] Total documents dans ChromaDB: {total}")

        return {
            "status": "success",
            "count": count,
            "folder": str(folder),
            "total_in_db": kb.collection.count() if kb.collection else len(kb.docs)
        }

    except Exception as e:
        print(f"[ERROR] {e}")
        return {"status": "error", "message": str(e), "count": 0}


if __name__ == "__main__":
    # Exemple: importer le dossier f1_wiki_csv
    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        # Par defaut, importer f1_wiki_csv
        folder_path = str(Path(__file__).parent.parent / "knowledge_base" / "f1_wiki_csv")

    print("=" * 60)
    print("IMPORT DE DOSSIER VERS CHROMADB")
    print("=" * 60)

    result = process_folder_to_kb(folder_path)

    print("\n" + "=" * 60)
    if result["status"] == "success":
        print(f"[SUCCESS] {result['count']} documents importes!")
        print(f"[INFO] Total dans ChromaDB: {result.get('total_in_db', 'N/A')}")
    else:
        print(f"[ERROR] {result.get('message', 'Erreur inconnue')}")
    print("=" * 60)
