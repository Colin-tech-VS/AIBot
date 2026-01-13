"""
Système de cache optimisé pour chatbot F1
TTL intelligent, invalidation et stats
"""

import time
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path


class CacheEntry:
    """Entrée de cache avec TTL et métadonnées"""
    def __init__(self, value: Any, ttl_seconds: int = 300):
        self.value = value
        self.created_at = time.time()
        self.ttl_seconds = ttl_seconds
        self.hits = 0
    
    def is_expired(self) -> bool:
        """Vérifier si l'entrée a expiré"""
        return (time.time() - self.created_at) > self.ttl_seconds
    
    def record_hit(self):
        """Enregistrer un accès au cache"""
        self.hits += 1
    
    def age_seconds(self) -> float:
        """Âge de l'entrée en secondes"""
        return time.time() - self.created_at


class OptimizedCache:
    """Cache local avec TTL, stats et persistance optionnelle"""
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache: Dict[str, CacheEntry] = {}
        self.cache_dir = cache_dir
        self.stats = {
            "hits": 0,
            "misses": 0,
            "expired": 0,
            "total_requests": 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Récupérer une valeur du cache"""
        self.stats["total_requests"] += 1
        
        if key not in self.cache:
            self.stats["misses"] += 1
            return None
        
        entry = self.cache[key]
        if entry.is_expired():
            del self.cache[key]
            self.stats["expired"] += 1
            self.stats["misses"] += 1
            return None
        
        entry.record_hit()
        self.stats["hits"] += 1
        return entry.value
    
    def set(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        """Stocker une valeur dans le cache"""
        self.cache[key] = CacheEntry(value, ttl_seconds)
    
    def invalidate(self, pattern: str = None) -> int:
        """Invalider les entrées correspondant à un pattern (glob)"""
        if pattern is None:
            count = len(self.cache)
            self.cache.clear()
            return count
        
        import fnmatch
        expired_keys = [k for k in self.cache if fnmatch.fnmatch(k, pattern)]
        for k in expired_keys:
            del self.cache[k]
        return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtenir les statistiques du cache"""
        total = self.stats["total_requests"]
        hit_rate = (self.stats["hits"] / total * 100) if total > 0 else 0
        
        return {
            "total_requests": total,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "expired": self.stats["expired"],
            "hit_rate": f"{hit_rate:.1f}%",
            "entries_count": len(self.cache),
            "memory_kb": sum(
                len(json.dumps(e.value, default=str).encode())
                for e in self.cache.values()
            ) / 1024
        }
    
    def cleanup_expired(self) -> int:
        """Nettoyer les entrées expirées"""
        before = len(self.cache)
        expired_keys = [k for k, v in self.cache.items() if v.is_expired()]
        for k in expired_keys:
            del self.cache[k]
        return before - len(self.cache)


# Instance globale
_cache_instance: Optional[OptimizedCache] = None


def get_cache() -> OptimizedCache:
    """Obtenir l'instance globale du cache"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = OptimizedCache()
    return _cache_instance


# TTL constants (en secondes)
CACHE_TTL = {
    "news_articles": 600,          # 10 min (actualités)
    "web_search": 900,             # 15 min (recherche web)
    "kb_search": 1200,             # 20 min (KB)
    "standings": 1800,             # 30 min (standings StandF1.com)
}
