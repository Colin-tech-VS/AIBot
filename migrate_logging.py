"""
Script de migration automatique print() → logger.*()
Remplace tous les print() par les appels logger appropriés
"""
import re
from pathlib import Path

# Fichiers à migrer
FILES_TO_MIGRATE = [
    r"C:\Users\lebre\Documents\GitHub\AIBot\backend\f1_bot.py",
    r"C:\Users\lebre\Documents\GitHub\AIBot\backend\knowledge_base.py",
    r"C:\Users\lebre\Documents\GitHub\AIBot\app.py",
]


def migrate_print_to_logger(file_path: str) -> tuple[int, list[str]]:
    """Migre print() vers logger.*() dans un fichier
    
    Returns:
        (nombre_remplacements, liste_changements)
    """
    path = Path(file_path)
    if not path.exists():
        return 0, [f"❌ Fichier non trouvé: {file_path}"]
    
    # Lire contenu
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    changes = []
    count = 0
    
    # Patterns de remplacement
    replacements = [
        # print(f"[INFO] message") → logger.info("message")
        (r'print\(f"\[INFO\]\s*([^"]+)"\)', r'logger.info(f"\1")', "INFO"),
        (r'print\("\[INFO\]\s*([^"]+)"\)', r'logger.info("\1")', "INFO"),
        
        # print(f"[WARN] message") → logger.warning("message")
        (r'print\(f"\[WARN\]\s*([^"]+)"\)', r'logger.warning(f"\1")', "WARN"),
        (r'print\("\[WARN\]\s*([^"]+)"\)', r'logger.warning("\1")', "WARN"),
        
        # print(f"[ERROR] message") → logger.error("message")
        (r'print\(f"\[ERROR\]\s*([^"]+)"\)', r'logger.error(f"\1")', "ERROR"),
        (r'print\("\[ERROR\]\s*([^"]+)"\)', r'logger.error("\1")', "ERROR"),
        
        # print(f"DEBUG: ...") → logger.debug(...)
        (r'print\(f"DEBUG:\s*([^"]+)"\)', r'logger.debug(f"\1")', "DEBUG"),
    ]
    
    for pattern, replacement, level in replacements:
        matches = re.findall(pattern, content)
        if matches:
            content_new = re.sub(pattern, replacement, content)
            new_count = len(re.findall(pattern, content))
            if content_new != content:
                changes.append(f"  ✅ {new_count}x print([{level}]) → logger.{level.lower()}()")
                count += new_count
                content = content_new
    
    # Sauvegarder si modifié
    if content != original_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        changes.insert(0, f"✅ Fichier modifié: {path.name}")
    else:
        changes.append(f"⚠️ Aucun changement nécessaire")
    
    return count, changes


def main():
    print("=" * 70)
    print("🔧 MIGRATION print() → logger.*()".center(70))
    print("=" * 70)
    print()
    
    total_replacements = 0
    
    for file_path in FILES_TO_MIGRATE:
        print(f"\n📝 Traitement: {Path(file_path).name}")
        print("-" * 70)
        
        count, changes = migrate_print_to_logger(file_path)
        total_replacements += count
        
        for change in changes:
            print(change)
    
    print("\n" + "=" * 70)
    print(f"✅ MIGRATION TERMINÉE".center(70))
    print("=" * 70)
    print(f"\n📊 Total remplacements: {total_replacements}")
    
    if total_replacements > 0:
        print("\n⚠️ IMPORTANT:")
        print("  • Vérifiez que les imports logger sont présents dans chaque fichier")
        print("  • backend/f1_bot.py: from backend.logger import get_logger")
        print("  • backend/knowledge_base.py: from backend.logger import get_logger")
        print("  • app.py: from backend.logger import get_logger")
        print("\n  • Si logger non déclaré, ajoutez:")
        print("    logger = get_logger(__name__)")
    
    return total_replacements


if __name__ == "__main__":
    total = main()
    exit(0 if total > 0 else 1)
