"""Vérifier l'état des dépendances du projet"""
import sys
import subprocess

# Liste des dépendances principales
DEPS_PROD = [
    "fastapi",
    "uvicorn", 
    "jinja2",
    "requests",
    "beautifulsoup4",
    "pydantic",
    "numpy",
    "sentence-transformers",
    "langchain-text-splitters",
    "bcrypt",
    "PyJWT",
    "python-docx",
    "faiss-cpu"
]

DEPS_DEV = [
    "ruff",
    "black",
    "transformers",
    "peft",
    "datasets",
    "accelerate"
]

# Usage dans le code
USAGE_MAP = {
    "fastapi": ["app.py", "backend/main.py", "backend/auth/routes.py"],
    "uvicorn": ["app.py (serveur)"],
    "jinja2": ["app.py (templates HTML)"],
    "requests": ["app.py", "backend/f1_bot.py", "backend/fast_handlers.py", "backend/standings_utils.py", "backend/wiki_utils.py", "knowledge_base/wiki_tables_to_csv.py"],
    "beautifulsoup4": ["backend/f1_bot.py", "backend/fast_handlers.py", "backend/standings_utils.py"],
    "pydantic": ["app.py", "backend/main.py", "backend/f1_bot.py", "backend/auth/models.py"],
    "numpy": ["backend/knowledge_base.py"],
    "sentence-transformers": ["backend/knowledge_base.py (embeddings)"],
    "langchain-text-splitters": ["backend/knowledge_base.py (chunking)"],
    "bcrypt": ["backend/auth/security.py (hash password)"],
    "PyJWT": ["backend/auth/security.py (JWT tokens)"],
    "python-docx": ["scripts/generate_guide_docx.py"],
    "faiss-cpu": ["backend/knowledge_base.py (recherche vectorielle)"],
    "ruff": ["DEV - Linting (non utilisé dans code)"],
    "black": ["DEV - Formatage (non utilisé dans code)"],
    "transformers": ["scripts/train_lora_f1.py"],
    "peft": ["scripts/train_lora_f1.py (LoRA fine-tuning)"],
    "datasets": ["scripts/train_lora_f1.py"],
    "accelerate": ["scripts/train_lora_f1.py"]
}

def check_installed():
    """Vérifier quelles dépendances sont installées"""
    try:
        import pkg_resources
        installed = {pkg.key: pkg.version for pkg in pkg_resources.working_set}
    except:
        print(" Impossible d'importer pkg_resources\n")
        return {}
    
    print("=" * 80)
    print("📦 BILAN DES DÉPENDANCES - F1 Chatbot")
    print("=" * 80)
    
    print("\n🔧 DÉPENDANCES PRODUCTION (requirements.txt)")
    print("-" * 80)
    
    prod_installed = 0
    prod_missing = 0
    
    for dep in DEPS_PROD:
        version = installed.get(dep.lower())
        usage = USAGE_MAP.get(dep, ["Inconnu"])
        
        if version:
            status = f" {version:15}"
            prod_installed += 1
            active = " ACTIF" if any("app.py" in u or "backend/" in u for u in usage) else "⚪ INACTIF"
        else:
            status = " NON INSTALLÉ"
            prod_missing += 1
            active = " MANQUANT"
        
        print(f"{dep:30} {status:20} {active}")
        if version:
            for u in usage[:2]:  # Limiter à 2 exemples
                print(f"{'':30}    → {u}")
    
    print(f"\n Production: {prod_installed}/{len(DEPS_PROD)} installées")
    
    print("\n DÉPENDANCES DÉVELOPPEMENT (requirements-dev.txt)")
    print("-" * 80)
    
    dev_installed = 0
    dev_missing = 0
    
    for dep in DEPS_DEV:
        version = installed.get(dep.lower())
        usage = USAGE_MAP.get(dep, ["Inconnu"])
        
        if version:
            status = f" {version:15}"
            dev_installed += 1
            active = " ACTIF" if "scripts/" in str(usage) else " OPTIONNEL"
        else:
            status = " NON INSTALLÉ"
            dev_missing += 1
            active = " OPTIONNEL"
        
        print(f"{dep:30} {status:20} {active}")
        if version:
            for u in usage[:2]:
                print(f"{'':30}    → {u}")
    
    print(f"\n Développement: {dev_installed}/{len(DEPS_DEV)} installées")
    
    # Vérifier les dépendances cachées
    print("\n DÉPENDANCES SECONDAIRES IMPORTANTES")
    print("-" * 80)
    
    secondary = {
        "torch": "sentence-transformers (backend ML)",
        "faiss": "faiss-cpu (binding)",
        "sqlite3": "backend/auth/database.py (built-in)",
        "langchain-core": "langchain-text-splitters"
    }
    
    for dep, desc in secondary.items():
        version = installed.get(dep.lower())
        if version:
            print(f"{dep:30}  {version:15} → {desc}")
        else:
            # sqlite3 est built-in
            if dep == "sqlite3":
                try:
                    import sqlite3
                    print(f"{dep:30}  built-in       → {desc}")
                except:
                    print(f"{dep:30}  NON INSTALLÉ  → {desc}")
            else:
                print(f"{dep:30}  NON INSTALLÉ  → {desc}")
    
    # Résumé final
    print("\n" + "=" * 80)
    print(" RÉSUMÉ")
    print("=" * 80)
    
    total_critical = len(DEPS_PROD)
    critical_ok = prod_installed
    
    if prod_missing == 0:
        print(" Toutes les dépendances critiques sont installées")
    else:
        print(f" {prod_missing} dépendance(s) critique(s) manquante(s)")
    
    print(f" Production: {critical_ok}/{total_critical} ({critical_ok*100//total_critical}%)")
    print(f" Développement: {dev_installed}/{len(DEPS_DEV)} ({dev_installed*100//len(DEPS_DEV) if dev_installed else 0}%)")
    
    # Recommandations
    print("\n RECOMMANDATIONS")
    print("-" * 80)
    
    if prod_missing > 0:
        print("1. Installer les dépendances manquantes:")
        print("   pip install -r requirements.txt")
    
    unused = []
    if "ruff" in installed and "ruff" not in ["scripts/", "backend/"]:
        unused.append("ruff")
    if "black" in installed and "black" not in ["scripts/", "backend/"]:
        unused.append("black")
    
    if unused:
        print(f"2. Dépendances dev installées mais non utilisées: {', '.join(unused)}")
        print("   → Peuvent être désinstallées si espace disque limité")
    
    # Vérifier les dépendances lourdes
    heavy = {
        "torch": installed.get("torch"),
        "transformers": installed.get("transformers"),
        "sentence-transformers": installed.get("sentence-transformers")
    }
    
    heavy_total = sum(1 for v in heavy.values() if v)
    if heavy_total > 0:
        print(f"\n Dépendances lourdes détectées ({heavy_total}/3):")
        for name, ver in heavy.items():
            if ver:
                print(f"   - {name} {ver}")
        print("   → Espace disque requis: ~2-5 GB")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    check_installed()
