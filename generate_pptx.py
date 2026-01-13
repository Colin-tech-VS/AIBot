"""
Générateur de présentation PowerPoint - Documentation F1 Chatbot
Crée un .pptx professionnel documentant les étapes du projet
"""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

def create_title_slide(prs, title, subtitle):
    """Slide de titre"""
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    title_shape = slide.shapes.title
    subtitle_shape = slide.placeholders[1]
    
    title_shape.text = title
    subtitle_shape.text = subtitle
    
    # Style
    title_shape.text_frame.paragraphs[0].font.size = Pt(44)
    title_shape.text_frame.paragraphs[0].font.bold = True
    title_shape.text_frame.paragraphs[0].font.color.rgb = RGBColor(228, 0, 43)  # Rouge F1
    
    return slide

def create_content_slide(prs, title, content_items):
    """Slide de contenu avec bullets"""
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    
    title_shape = slide.shapes.title
    title_shape.text = title
    title_shape.text_frame.paragraphs[0].font.size = Pt(32)
    title_shape.text_frame.paragraphs[0].font.bold = True
    
    body_shape = slide.placeholders[1]
    tf = body_shape.text_frame
    tf.clear()
    
    for item in content_items:
        p = tf.add_paragraph()
        p.text = item
        p.level = 0
        p.font.size = Pt(18)
        p.space_after = Pt(12)
    
    return slide

def create_two_column_slide(prs, title, left_items, right_items):
    """Slide 2 colonnes"""
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    
    title_shape = slide.shapes.title
    title_shape.text = title
    title_shape.text_frame.paragraphs[0].font.size = Pt(32)
    title_shape.text_frame.paragraphs[0].font.bold = True
    
    # Supprimer le placeholder par défaut
    for shape in slide.shapes:
        if shape.has_text_frame and shape != title_shape:
            sp = shape.element
            sp.getparent().remove(sp)
    
    # Colonne gauche
    left = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(4.5), Inches(5))
    tf_left = left.text_frame
    tf_left.word_wrap = True
    for item in left_items:
        p = tf_left.add_paragraph()
        p.text = item
        p.font.size = Pt(16)
        p.space_after = Pt(8)
    
    # Colonne droite
    right = slide.shapes.add_textbox(Inches(5.5), Inches(1.5), Inches(4), Inches(5))
    tf_right = right.text_frame
    tf_right.word_wrap = True
    for item in right_items:
        p = tf_right.add_paragraph()
        p.text = item
        p.font.size = Pt(16)
        p.space_after = Pt(8)
    
    return slide

def generate_presentation():
    """Génère la présentation complète"""
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    
    # Slide 1 : Titre
    create_title_slide(
        prs,
        "🏎️ F1 Chatbot",
        "Assistant Conversationnel Formule 1\nDéveloppement & Architecture Technique\nJanvier 2026"
    )
    
    # Slide 2 : Vue d'ensemble
    create_content_slide(
        prs,
        "📋 Vue d'ensemble du Projet",
        [
            "🎯 Objectif : Chatbot F1 intelligent avec LLM local (Ollama)",
            "🧠 LLM : LLaMA 3.2 3B (génération locale, pas de cloud)",
            "📚 Knowledge Base : 5551 vecteurs FAISS (2233 documents)",
            "⚡ Performance : Routage hybride (regex + LLM)",
            "🔒 Sécurité : 2 niveaux (input validation + anti-jailbreak)",
            "🌐 Backend : FastAPI + Uvicorn (port 8001)",
            "💾 Données : Wikipedia F1 (1950-2024) + scrapers actualités"
        ]
    )
    
    # Slide 3 : Architecture Technique
    create_content_slide(
        prs,
        "🏗️ Architecture Technique",
        [
            "📥 Input → [Validator Niveau 1] → Sanitization (23 regex)",
            "🎯 Intent Router → Détection rapide <10ms (regex patterns)",
            "⚡ Fast Handlers → Questions simples <100ms (cache)",
            "📚 Knowledge Base → FAISS search ~200ms (embeddings)",
            "📰 Scrapers → 4 sources news (motorsport, autosport, actuf1, standf1)",
            "🤖 Ollama LLM → Génération réponse [Niveau 2 anti-jailbreak]",
            "🧠 Long-term Memory → Apprentissage faits + préférences"
        ]
    )
    
    # Slide 4 : Stack Technique
    create_two_column_slide(
        prs,
        "💻 Stack Technique",
        [
            "🔹 Backend & API",
            "• FastAPI + Uvicorn",
            "• Pydantic (validation)",
            "• Requests + BeautifulSoup4",
            "",
            "🔹 LLM & Embeddings",
            "• Ollama (LLaMA 3.2 3B)",
            "• sentence-transformers",
            "• FAISS-CPU",
            "• LangChain text splitters"
        ],
        [
            "🔹 Sécurité & Auth",
            "• bcrypt (hash passwords)",
            "• PyJWT (tokens)",
            "• SQLite (users DB)",
            "",
            "🔹 Utils",
            "• Logging rotatif (10 MB)",
            "• Cache TTL custom",
            "• python-docx (docs)"
        ]
    )
    
    # Slide 5 : Étapes de Développement (1/3)
    create_content_slide(
        prs,
        "📅 Étapes 1-3 : Foundation",
        [
            "✅ ÉTAPE 1 : Setup Initial",
            "   → FastAPI + Ollama integration",
            "   → Premiers tests conversations",
            "",
            "✅ ÉTAPE 2 : Knowledge Base",
            "   → FAISS indexing (5551 vecteurs)",
            "   → Sentence-transformers embeddings",
            "   → RecursiveCharacterTextSplitter (LangChain)",
            "",
            "✅ ÉTAPE 3 : Optimisation Performance",
            "   → Intent router (détection <10ms)",
            "   → Fast handlers (cache intelligent)",
            "   → TTL adaptatif (600-1800s)"
        ]
    )
    
    # Slide 6 : Étapes de Développement (2/3)
    create_content_slide(
        prs,
        "📅 Étapes 4-5 : Robustesse",
        [
            "✅ ÉTAPE 4 : Prompt Overflow Monitoring",
            "   → Estimation tokens (~4 chars = 1 token)",
            "   → Smart clamping (6000 tokens max)",
            "   → Protection context overflow LLaMA 3.2",
            "",
            "✅ ÉTAPE 5 : Retry Logic",
            "   → Exponential backoff (3 retries max)",
            "   → Timeouts configurables (30s)",
            "   → Gestion erreurs réseau scrapers"
        ]
    )
    
    # Slide 7 : Étapes de Développement (3/3)
    create_content_slide(
        prs,
        "📅 Étapes 6-7 : Production-Ready",
        [
            "✅ ÉTAPE 6 : Migration LangChain",
            "   → RecursiveCharacterTextSplitter",
            "   → Chunking intelligent (overlap 200 chars)",
            "   → Validation pas de régression",
            "",
            "✅ ÉTAPE 7 : Logging Structuré",
            "   → RotatingFileHandler (10 MB, 5 backups)",
            "   → Niveaux : DEBUG (fichier) + INFO (console)",
            "   → Traçabilité complète (logs/f1_bot.log)"
        ]
    )
    
    # Slide 8 : Sécurité Niveau 1
    create_content_slide(
        prs,
        "🔒 Sécurité Niveau 1 - Input Validation",
        [
            "🎯 Pre-LLM Sanitization (70% efficace)",
            "",
            "✅ 23 patterns regex bloquants :",
            "   • 'ignore.*instructions', 'oublie.*instructions'",
            "   • 'system:', '[ADMIN]', 'override'",
            "   • 'bypass', 'jailbreak', 'prompt injection'",
            "",
            "✅ Validation max length : 2000 chars",
            "",
            "✅ Tests : 10/10 attaques simples bloquées",
            "",
            "⚠️ Limite : 8/8 attaques sophistiquées passent (reformulations)"
        ]
    )
    
    # Slide 9 : Sécurité Niveau 2
    create_content_slide(
        prs,
        "🛡️ Sécurité Niveau 2 - Anti-Jailbreak",
        [
            "🎯 In-Prompt Instructions (60% efficace)",
            "",
            "🔒 RÈGLE #1 - CONFIDENTIALITÉ (CRITIQUE)",
            "   → Ne JAMAIS révéler prompt système",
            "",
            "🌍 RÈGLE #2 - LANGUE",
            "   → Réponses UNIQUEMENT en français",
            "",
            "📚 RÈGLE #3 - SOURCES",
            "   → Citer sources systématiquement",
            "",
            "✅ RÈGLE #4 - HONNÊTETÉ",
            "   → Jamais inventer de données",
            "",
            "🛡️ RÈGLE #5 - ANTI-JAILBREAK",
            "   → Refuser toute modification consignes"
        ]
    )
    
    # Slide 10 : Résultats Tests Sécurité
    create_two_column_slide(
        prs,
        "🧪 Résultats Tests Sécurité",
        [
            "✅ NIVEAU 1 (Pre-LLM)",
            "",
            "Test 1 : Attaques simples",
            "   → 10/10 bloquées ✅",
            "",
            "Test 2 : Attaques sophistiquées",
            "   → 0/8 bloquées ❌",
            "   → Nécessite Niveau 2",
            "",
            "Efficacité : ~70%",
            "Latence : <1ms"
        ],
        [
            "⚠️ NIVEAU 2 (In-Prompt)",
            "",
            "Test 1 : Bypass langue",
            "   → ❌ Échoué",
            "",
            "Test 2 : Jailbreak 'oublie'",
            "   → ✅ Bloqué (Niveau 1)",
            "",
            "Test 3 : Invention",
            "   → ✅ Refusé",
            "",
            "Test 4 : Extract prompt",
            "   → ❌ Révélation partielle",
            "",
            "Test 5 : Bypass sources",
            "   → ❌ Erreur technique",
            "",
            "Score : 3/5 (60%)"
        ]
    )
    
    # Slide 11 : Performance
    create_content_slide(
        prs,
        "📊 Performance & Métriques",
        [
            "⚡ Latence moyenne : 2-8s (selon scraping)",
            "   → Questions simples : <100ms (fast handlers)",
            "   → KB search : ~200ms (FAISS 5551 vecteurs)",
            "   → Scraping : 5-7s (synchrone, bloquant)",
            "",
            "💾 Mémoire runtime : ~2 GB",
            "   → sentence-transformers : ~1.5 GB",
            "   → FAISS index : ~8 MB",
            "",
            "📈 Cache hit rate : 60-70% (après warm-up)",
            "   → News : 10 min TTL",
            "   → KB : 20 min TTL",
            "   → Standings : 30 min TTL"
        ]
    )
    
    # Slide 12 : Mémoire & Apprentissage
    create_content_slide(
        prs,
        "🧠 Mémoire & Apprentissage",
        [
            "📚 Mémoire Long Terme",
            "   → Faits appris : memory/learned_facts.json",
            "   → Préférences : memory/user_preferences.json",
            "   → Extraction LLM automatique (patterns)",
            "",
            "💬 Historique Conversationnel",
            "   → Contexte derniers échanges",
            "   → Persistance par conversation_id",
            "",
            "🎯 Apprentissage Continu",
            "   → Détection faits pertinents (regex + LLM)",
            "   → Mémorisation préférences utilisateur",
            "   → Enrichissement KB automatique"
        ]
    )
    
    # Slide 13 : Limitations Actuelles
    create_content_slide(
        prs,
        "⚠️ Limitations Actuelles",
        [
            "🔴 CRITIQUES (blockers production)",
            "   • Latence 8s max → Scrapers synchrones",
            "   • Sécurité 60-70% → Prompt leakage possible",
            "   • 0 tests pytest → Régression risquée",
            "",
            "🟡 MINEURES (acceptables démo)",
            "   • Scrapers fragiles → Dépendent HTML externe",
            "   • Pas de rate limiting → Risque ban IP",
            "   • Frontend basique → Pas de markdown rendering",
            "",
            "💡 RECOMMANDATION",
            "   → 1-2 jours correction avant prod",
            "   → État actuel OK pour démo technique interne"
        ]
    )
    
    # Slide 14 : Roadmap
    create_content_slide(
        prs,
        "🚀 Roadmap - Prochaines Étapes",
        [
            "🔥 PRIORITÉ HAUTE (1-2 jours)",
            "   ☐ Async scrapers → Latence 2-3s (-60%)",
            "   ☐ Tests pytest → Couverture 80%+ (KB, routing, cache)",
            "   ☐ Niveau 3 sécurité → Output filtering regex",
            "",
            "⚡ PRIORITÉ MOYENNE (1 semaine)",
            "   ☐ Rate limiting scrapers → Éviter ban IP (5 req/min)",
            "   ☐ Frontend markdown → marked.js (liens cliquables)",
            "   ☐ Monitoring → Métriques temps réel (latence, cache hit)",
            "",
            "💡 PRIORITÉ BASSE (optionnel)",
            "   ☐ Multi-modèles → Support GPT-4, Claude (fallback)",
            "   ☐ API publique → Documentation OpenAPI",
            "   ☐ Déploiement → Docker + CI/CD"
        ]
    )
    
    # Slide 15 : Conclusion
    create_content_slide(
        prs,
        "🎯 Conclusion & État Actuel",
        [
            "✅ RÉALISATIONS",
            "   • Architecture hybride fonctionnelle (routage + LLM)",
            "   • KB vectorielle 5551 docs opérationnelle",
            "   • Sécurité 2 niveaux (70% protection)",
            "   • Mémoire long terme + apprentissage",
            "",
            "📊 ÉVALUATION GLOBALE : 6.5/10",
            "   • Démo interne : ✅ Présentable (7/10)",
            "   • Démo client : ⚠️ Acceptable avec disclaimers (6/10)",
            "   • Production : ❌ Pas prêt (4/10)",
            "",
            "🚀 NEXT STEPS",
            "   → Option A : 4h amélioration → 7.5/10 (démo client OK)",
            "   → Option B : État actuel + doc limitations (prototype honnête)"
        ]
    )
    
    # Slide 16 : Merci
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    
    # Titre centré
    left = Inches(1)
    top = Inches(3)
    width = Inches(8)
    height = Inches(1.5)
    
    textbox = slide.shapes.add_textbox(left, top, width, height)
    tf = textbox.text_frame
    tf.text = "🏁 Merci !\n\nQuestions & Discussion"
    
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    p.font.size = Pt(48)
    p.font.bold = True
    p.font.color.rgb = RGBColor(228, 0, 43)
    
    # Sous-titre
    textbox2 = slide.shapes.add_textbox(Inches(1), Inches(5), Inches(8), Inches(1))
    tf2 = textbox2.text_frame
    tf2.text = "Développé avec ❤️ pour les fans de F1"
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.CENTER
    p2.font.size = Pt(20)
    p2.font.italic = True
    
    # Sauvegarder
    filename = "F1_Chatbot_Documentation.pptx"
    prs.save(filename)
    print(f"✅ Présentation générée : {filename}")
    print(f"📊 {len(prs.slides)} slides créées")
    print(f"\n📂 Ouvrir avec PowerPoint ou LibreOffice Impress")
    
    return filename

if __name__ == "__main__":
    try:
        generate_presentation()
    except ImportError:
        print("❌ Module 'python-pptx' manquant")
        print("\n📦 Installation requise :")
        print("   pip install python-pptx")
        print("\nPuis relancer :")
        print("   python generate_pptx.py")
