"""
Script de conversion de la Knowledge Base en format embeddings
Convertit tous les CSV existants au format id,title,content,category
et initialise ChromaDB avec les embeddings
"""

import csv
import sys
import shutil
from pathlib import Path

# Ajouter le repertoire parent au path pour importer les modules backend
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.knowledge_base import KnowledgeBase, KnowledgeDoc

# Chemins
KB_DIR = Path(__file__).parent.parent / "knowledge_base"
KB_FORMATTED_DIR = KB_DIR / "formatted"
KB_FORMATTED_DIR.mkdir(exist_ok=True)


def convert_circuits_csv():
    """Convertir circuits.csv au format KB"""
    print("\n[1/4] Conversion circuits.csv...")
    input_file = KB_DIR / "circuits.csv"
    output_file = KB_FORMATTED_DIR / "circuits_kb.csv"

    if not input_file.exists():
        print(f"  [WARN] {input_file.name} n'existe pas, ignore")
        return

    circuits = []
    with input_file.open('r', encoding='utf-8') as f_in:
        # Lire toutes les lignes pour traiter le format special
        lines = f_in.readlines()

        for idx, line in enumerate(lines[1:], 1):  # Ignorer header
            # Parser manuellement car le CSV a un format bizarre
            parts = line.strip().strip('"').split('","')
            if len(parts) < 2:
                continue

            # Extraire les donnees
            nom = parts[0].replace('""', '"').strip() if len(parts) > 0 else ''
            lieu = parts[2].replace('""', '"').strip() if len(parts) > 2 else ''
            courses = parts[3].replace('""', '"').strip() if len(parts) > 3 else ''
            annees = parts[4].replace('""', '"').strip() if len(parts) > 4 else ''
            nb_gp = parts[5].replace('""', '"').strip() if len(parts) > 5 else ''

            if not nom:
                continue

            # Creer un contenu structure
            content = f"Circuit: {nom}. "
            if lieu:
                content += f"Situe a {lieu}. "
            if courses:
                content += f"Courses: {courses}. "
            if annees:
                content += f"Annees d'activite: {annees}. "
            if nb_gp:
                content += f"{nb_gp} Grands Prix organises."

            circuits.append({
                'id': f'circuit_{idx}',
                'title': nom,
                'content': content,
                'category': 'circuits'
            })

    # Ecrire le fichier formate
    with output_file.open('w', encoding='utf-8', newline='') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=['id', 'title', 'content', 'category'])
        writer.writeheader()
        writer.writerows(circuits)

    print(f"  [OK] {len(circuits)} circuits convertis -> {output_file.name}")


def convert_constructeurs_csv():
    """Convertir constructeurs.csv au format KB"""
    print("\n[2/4] Conversion constructeurs.csv...")
    input_file = KB_DIR / "constructeurs.csv"
    output_file = KB_FORMATTED_DIR / "constructeurs_kb.csv"

    if not input_file.exists():
        print(f"  [WARN] {input_file.name} n'existe pas, ignore")
        return

    with input_file.open('r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        constructeurs = []

        for idx, row in enumerate(reader, 1):
            nom = row.get('Constructor Name', '').strip().strip('"')
            moteur = row.get('Engine Manufacturer', '').strip().strip('"')
            pays_license = row.get('Licensed In Country', '').strip().strip('"')
            pays_base = row.get('Base Country', '').strip().strip('"')
            saisons = row.get('Seasons Active', '').strip().strip('"')
            victoires = row.get('Wins', '').strip().strip('"')

            if not nom:
                continue

            # Creer un contenu structure
            content = f"Constructeur: {nom}. "
            if moteur:
                content += f"Moteur: {moteur}. "
            if pays_license:
                content += f"Licence: {pays_license}. "
            if pays_base:
                content += f"Base: {pays_base}. "
            if saisons:
                content += f"Saisons actives: {saisons}. "
            if victoires:
                content += f"Victoires: {victoires}."

            constructeurs.append({
                'id': f'constructeur_{idx}',
                'title': nom,
                'content': content,
                'category': 'constructeurs'
            })

    # Ecrire le fichier formate
    with output_file.open('w', encoding='utf-8', newline='') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=['id', 'title', 'content', 'category'])
        writer.writeheader()
        writer.writerows(constructeurs)

    print(f"  [OK] {len(constructeurs)} constructeurs convertis -> {output_file.name}")


def convert_pilotes_csv():
    """Convertir le fichier des pilotes au format KB"""
    print("\n[3/4] Conversion pilotes.csv...")
    input_file = KB_DIR / "Classement des pilotes de Formule 1 par nombre de victoires en Grand Prix.csv"
    output_file = KB_FORMATTED_DIR / "pilotes_kb.csv"

    if not input_file.exists():
        print(f"  [WARN] {input_file.name} n'existe pas, ignore")
        return

    pilotes = []
    with input_file.open('r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        # La premiere ligne est un en-tete tablescraper, la 2e est le vrai header
        first_row = next(reader, None)
        if not first_row:
            print("  [WARN] Fichier vide")
            return

        # Maintenant reader pointe sur les donnees reelles
        for idx, row in enumerate(reader, 1):
            rang = row.get('tablescraper-selected-row', '').strip().strip('"')
            pilote = row.get('tablescraper-selected-row 2', '').strip().strip('"')
            nationalite = row.get('tablescraper-selected-row 3', '').strip().strip('"')
            periode = row.get('tablescraper-selected-row 4', '').strip().strip('"')
            participations = row.get('tablescraper-selected-row 5', '').strip().strip('"')
            victoires = row.get('tablescraper-selected-row 6', '').strip().strip('"')

            if not pilote or not rang:
                continue

            # Creer un contenu structure
            content = f"Pilote: {pilote}. "
            if nationalite:
                content += f"Nationalite: {nationalite}. "
            if periode:
                content += f"Periode: {periode}. "
            if participations:
                content += f"{participations} participations. "
            if victoires:
                content += f"{victoires} victoires en Grand Prix."

            pilotes.append({
                'id': f'pilote_{idx}',
                'title': pilote,
                'content': content,
                'category': 'pilotes'
            })

    # Ecrire le fichier formate
    with output_file.open('w', encoding='utf-8', newline='') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=['id', 'title', 'content', 'category'])
        writer.writeheader()
        writer.writerows(pilotes)

    print(f"  [OK] {len(pilotes)} pilotes convertis -> {output_file.name}")


def convert_classements_constructeurs_csv():
    """Convertir classements constructeurs.csv au format KB"""
    print("\n[4/4] Conversion classements constructeurs.csv...")
    input_file = KB_DIR / "classemnts constructeurs.csv"
    output_file = KB_FORMATTED_DIR / "classements_constructeurs_kb.csv"

    if not input_file.exists():
        print(f"  [WARN] {input_file.name} n'existe pas, ignore")
        return

    with input_file.open('r', encoding='utf-8') as f_in:
        reader = csv.DictReader(f_in)
        classements = []

        for idx, row in enumerate(reader, 1):
            # Utiliser les vrais noms de colonnes francais
            constructeur = row.get('Constructeur', row.get('Constructor', '')).strip().strip('"')
            nationalite = row.get('Nationalité', row.get('Nationality', '')).strip().strip('"')
            victoires = row.get('Victoires', row.get('Wins', '')).strip().strip('"')
            periode = row.get("Période d'activité", row.get('Period', '')).strip().strip('"')
            premiere_victoire = row.get('Première victoire', row.get('First Win', '')).strip().strip('"')
            derniere_victoire = row.get('Dernière victoire', row.get('Last Win', '')).strip().strip('"')

            if not constructeur:
                continue

            # Creer un contenu structure
            content = f"Constructeur: {constructeur}. "
            if nationalite:
                content += f"Nationalite: {nationalite}. "
            if victoires:
                content += f"{victoires} victoires. "
            if periode:
                content += f"Periode d'activite: {periode}. "
            if premiere_victoire:
                content += f"Premiere victoire: {premiere_victoire}. "
            if derniere_victoire:
                content += f"Derniere victoire: {derniere_victoire}."

            classements.append({
                'id': f'classement_{idx}',
                'title': constructeur,
                'content': content,
                'category': 'classements'
            })

    # Ecrire le fichier formate
    with output_file.open('w', encoding='utf-8', newline='') as f_out:
        writer = csv.DictWriter(f_out, fieldnames=['id', 'title', 'content', 'category'])
        writer.writeheader()
        writer.writerows(classements)

    print(f"  [OK] {len(classements)} classements convertis -> {output_file.name}")


def initialize_chromadb():
    """Initialiser ChromaDB avec tous les fichiers formatesM"""
    print("\n" + "="*60)
    print("INITIALISATION DE CHROMADB AVEC EMBEDDINGS")
    print("="*60)

    # Creer une nouvelle instance de KB avec ChromaDB active
    kb = KnowledgeBase(use_chromadb=True)

    # Charger tous les fichiers CSV formates
    formatted_files = list(KB_FORMATTED_DIR.glob("*.csv"))

    if not formatted_files:
        print("[WARN] Aucun fichier formate trouve!")
        return kb

    total_docs = 0
    for csv_file in formatted_files:
        print(f"\n[LOAD] Chargement de {csv_file.name}...")
        with csv_file.open('r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                doc = KnowledgeDoc(
                    doc_id=row['id'],
                    title=row['title'],
                    content=row['content'],
                    category=row['category']
                )
                kb.add_document(doc)
                count += 1
            print(f"  [OK] {count} documents ajoutes")
            total_docs += count

    print(f"\n{'='*60}")
    print(f"[SUCCES] TOTAL: {total_docs} documents charges dans ChromaDB")
    print(f"[INFO] Dossier persistence: {KB_DIR / 'chroma'}")
    print(f"{'='*60}")

    return kb


def test_search(kb):
    """Tester la recherche avec embeddings"""
    print("\n" + "="*60)
    print("TEST DE RECHERCHE AVEC EMBEDDINGS")
    print("="*60)

    test_queries = [
        "Lewis Hamilton victoires",
        "Circuit Monaco",
        "Ferrari championnat",
        "Max Verstappen",
        "Mercedes constructeur"
    ]

    for query in test_queries:
        print(f"\n[RECHERCHE] '{query}'")
        results = kb.search(query, top_k=3)

        if results:
            print(f"  [OK] {len(results)} resultats trouves:")
            for i, result in enumerate(results, 1):
                preview = result[:100].replace('\n', ' ')
                print(f"     {i}. {preview}...")
        else:
            print(f"  [WARN] Aucun resultat")


def copy_formatted_to_kb():
    """Copier les fichiers formates vers le repertoire KB principal"""
    print("\n" + "="*60)
    print("COPIE DES FICHIERS FORMATES VERS KB PRINCIPAL")
    print("="*60)

    formatted_files = list(KB_FORMATTED_DIR.glob("*_kb.csv"))
    if not formatted_files:
        print("[WARN] Aucun fichier formate a copier")
        return

    copied = 0
    for file in formatted_files:
        dest = KB_DIR / file.name
        try:
            shutil.copy2(file, dest)
            print(f"[OK] {file.name} copie vers {KB_DIR.name}/")
            copied += 1
        except Exception as e:
            print(f"[WARN] Echec copie {file.name}: {e}")

    print(f"\n[SUCCES] {copied} fichiers copies vers le repertoire KB principal")


def main():
    print("="*60)
    print("CONVERSION DE LA KNOWLEDGE BASE EN FORMAT EMBEDDINGS")
    print("="*60)

    # Etape 1: Convertir tous les CSV
    print("\n[ETAPE 1] CONVERSION DES FICHIERS CSV")
    print("-"*60)
    convert_circuits_csv()
    convert_constructeurs_csv()
    convert_pilotes_csv()
    convert_classements_constructeurs_csv()

    # Etape 2: Copier vers KB principal
    print("\n[ETAPE 2] COPIE VERS KB PRINCIPAL")
    print("-"*60)
    copy_formatted_to_kb()

    # Etape 3: Initialiser ChromaDB
    print("\n[ETAPE 3] INITIALISATION DE CHROMADB")
    print("-"*60)
    kb = initialize_chromadb()

    # Etape 4: Tester la recherche
    test_search(kb)

    print("\n" + "="*60)
    print("[SUCCES] CONVERSION TERMINEE AVEC SUCCES!")
    print("="*60)
    print("\n[INFO] Les fichiers originaux sont conserves.")
    print(f"[INFO] Fichiers formates dans: {KB_FORMATTED_DIR}")
    print(f"[INFO] Fichiers KB copies dans: {KB_DIR}")
    print(f"[INFO] Base ChromaDB dans: {KB_DIR / 'chroma'}")
    print("\n[INFO] Vous pouvez maintenant demarrer le serveur!")


if __name__ == "__main__":
    main()
