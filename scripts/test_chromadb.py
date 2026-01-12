"""
Script de test pour vérifier ChromaDB et la Knowledge Base
"""

import sys
from pathlib import Path

# Ajouter le repertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.knowledge_base import get_knowledge_base


def test_knowledge_base():
    """Tester la knowledge base et ChromaDB"""
    print("=" * 60)
    print("TEST DE LA KNOWLEDGE BASE ET CHROMADB")
    print("=" * 60)

    # Initialiser la KB
    print("\n[1] Initialisation de la Knowledge Base...")
    kb = get_knowledge_base()

    # Statistiques
    print("\n[2] Statistiques:")
    print(f"  - ChromaDB actif: {kb.use_chromadb}")
    print(f"  - Documents en memoire: {len(kb.docs)}")
    if kb.collection:
        print(f"  - Documents dans ChromaDB: {kb.collection.count()}")

    # Répartition par catégorie
    print("\n[3] Repartition par categorie:")
    categories = {}
    for doc in kb.docs.values():
        categories[doc.category] = categories.get(doc.category, 0) + 1
    for cat, count in sorted(categories.items()):
        print(f"  - {cat}: {count} documents")

    # Tests de recherche sémantique
    print("\n[4] Tests de recherche semantique:")

    test_queries = [
        ("Lewis Hamilton pilote", "Recherche pilote"),
        ("Ferrari constructeur victoires", "Recherche constructeur"),
        ("Circuit Monaco Grand Prix", "Recherche circuit"),
        ("Max Verstappen champion", "Recherche champion actuel"),
    ]

    for query, description in test_queries:
        print(f"\n  [{description}]")
        print(f"  Requete: '{query}'")
        results = kb.search(query, top_k=2)
        for i, result in enumerate(results, 1):
            # Afficher les 100 premiers caractères
            preview = result.replace("\n", " ")[:100]
            print(f"    {i}. {preview}...")

    print("\n" + "=" * 60)
    print("TEST TERMINE AVEC SUCCES")
    print("=" * 60)


if __name__ == "__main__":
    test_knowledge_base()
