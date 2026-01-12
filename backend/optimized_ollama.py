"""
Gestionnaire Ollama optimisé pour latence ultra-basse
Paramètres et streaming optimisés pour Nemotron-3-nano
"""

import subprocess
import time
import json
import sys
from pathlib import Path
from typing import Generator, Optional, Dict
from dataclasses import dataclass


@dataclass
class OllamaConfig:
    """Configuration optimisée pour Nemotron-3-nano"""
    model: str = "nemotron-3-nano"
    temperature: float = 0.3          # Légèrement supérieure pour variation (modèle plus petit)
    top_p: float = 0.85               # Nucleus sampling (plus strict)
    num_ctx: int = 2048               # Context window acceptable pour nano model
    num_predict: int = 512            # Max tokens (nano peut supporter plus)
    top_k: int = 15                   # Beam search strict
    repeat_penalty: float = 1.2       # Pénalité élevée pour répétitions
    timeout: int = 30                 # 30s max (nano = très rapide)


OLLAMA_PATHS = [
    r"C:\\Users\\cococ\\AppData\\Local\\Programs\\Ollama\\ollama.exe",
    r"C:\\Program Files\\Ollama\\ollama.exe",
    "ollama",
]


def resolve_ollama_path() -> str:
    """Trouver le chemin vers ollama.exe"""
    for p in OLLAMA_PATHS:
        if p == "ollama":
            return p
        if Path(p).exists():
            return p
    return OLLAMA_PATHS[0]


class OptimizedOllama:
    """Wrapper Ollama optimisé pour latence ultra-basse"""
    
    def __init__(self, config: OllamaConfig = None):
        self.config = config or OllamaConfig()
        self.ollama_path = resolve_ollama_path()
        self._test_connection()
    
    def _test_connection(self) -> bool:
        """Vérifier que Ollama est accessible"""
        try:
            result = subprocess.run(
                [self.ollama_path, "list"],
                capture_output=True,
                timeout=5,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            print(f"[WARN] Ollama non accessible: {e}")
            return False
    
    def call_sync(self, prompt: str, timeout: int = None) -> str:
        """
        Appel synchrone optimisé
        - Ultra compact (prompt < 600 tokens)
        - Réponse courte (< 256 tokens)
        - Latence <2s
        """
        timeout = timeout or self.config.timeout
        
        try:
            cmd = [
                self.ollama_path,
                "run",
                self.config.model,
                prompt
            ]
            
            start = time.time()
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            elapsed = time.time() - start
            
            if result.returncode == 0:
                response = result.stdout.strip()
                print(f"[INFO] Ollama réponse en {elapsed:.2f}s ({len(response)} chars)")
                return response
            else:
                return f"[ERREUR] Ollama: {result.stderr.strip()}"
        
        except subprocess.TimeoutExpired:
            return "[ERREUR] Timeout Ollama (>30s)"
        except FileNotFoundError:
            return f"[ERREUR] Ollama non trouvé à {self.ollama_path}"
        except Exception as e:
            return f"[ERREUR] Ollama: {type(e).__name__}: {e}"
    
    def call_streaming(self, prompt: str) -> Generator[str, None, None]:
        """
        Streaming de la réponse pour UX instantanée
        Envoie chaque token au fur et à mesure
        """
        try:
            cmd = [
                self.ollama_path,
                "run",
                self.config.model,
                prompt
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            
            # Streaming ligne par ligne
            for line in process.stdout:
                if line.strip():
                    yield line.strip() + " "
            
            process.wait(timeout=self.config.timeout)
        
        except subprocess.TimeoutExpired:
            process.kill()
            yield "[ERREUR] Timeout"
        except Exception as e:
            yield f"[ERREUR] {type(e).__name__}"
    
    def get_model_info(self) -> Dict:
        """Obtenir les infos du modèle"""
        try:
            result = subprocess.run(
                [self.ollama_path, "show", self.config.model],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return {
                    "model": self.config.model,
                    "status": "available",
                    "info": result.stdout[:500]
                }
        except Exception as e:
            return {
                "model": self.config.model,
                "status": "error",
                "error": str(e)
            }


# Instance globale
_ollama_instance: Optional[OptimizedOllama] = None


def get_ollama(config: OllamaConfig = None) -> OptimizedOllama:
    """Obtenir l'instance Ollama optimisée"""
    global _ollama_instance
    if _ollama_instance is None:
        _ollama_instance = OptimizedOllama(config)
    return _ollama_instance
