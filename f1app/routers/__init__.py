# Routers package - lazy import pour éviter les erreurs circulaires
def get_routers():
    """Retourne tous les routers de l'application."""
    from f1app.routers.chat import router as chat_router
    from f1app.routers.kb import router as kb_router
    from f1app.routers.health import router as health_router
    return chat_router, kb_router, health_router

__all__ = ["get_routers"]
