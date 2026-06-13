"""
config/settings.py
==================
Module de configuration centralisé.
Lit le fichier .env et expose toutes les variables de configuration
comme un objet unique importable partout dans le projet.
Usage dans n'importe quel fichier :
    from config.settings import settings
    print(settings.OPENAI_MODEL)      # gpt-4o-mini
    print(settings.GROQ_MODEL)        # llama-3.3-70b-versatile
    print(settings.OLLAMA_MODEL)      # mistral
    print(settings.TAVILY_API_KEY)    # tvly-...
Récapitulatif des LLMs par agent :
┌──────────────────┬──────────────────────────┬─────────────────┐
│ Agent            
│ LLM                      
│ Fournisseur     
│
├──────────────────┼──────────────────────────┼─────────────────┤
│ CVParser         
│ llama-3.3-70b-versatile  │ Groq (gratuit)  │
│ ExtractorAgent   
│ AnalystAgent     
│ CoachAgent       
│ ScraperAgent     
│ minimax-m2.5                 
│ gpt-4o-mini              
│ gpt-4o-mini              
│ —                        
│ Ollama (local)  │
│ OpenAI          
│ OpenAI          
│
│
│ Tavily (search) │
└──────────────────┴──────────────────────────┴─────────────────┘
"""
import os
from pathlib import Path
from dotenv import load_dotenv
# ── Charger le .env depuis la racine du projet ──────────────
# Peu importe d'où on lance Python, settings.py trouve toujours le .env
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")
class Settings:
    """Centralise toute la configuration de l'application"""
    # ── Chemins ──────────────────────────────────────────────
    ROOT_DIR:  Path = ROOT_DIR
    DATA_DIR:  Path = ROOT_DIR / "data"
    CHROMA_DIR: Path = ROOT_DIR / Path(
        os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db")
    )
    # ── OpenAI (AnalystAgent + CoachAgent) ───────────────────
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL:   str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # ── Groq / Llama (CVParser) ──────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL:   str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    # ── Ollama (ExtractorAgent — modèle local) ───────────────
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL:    str = os.getenv("OLLAMA_MODEL", "mistral")
    # ── Tavily (ScraperAgent — recherche web) ────────────────
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    # ── ChromaDB (CoachAgent — RAG) ──────────────────────────
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "data/chroma_db")
    # ── Application ──────────────────────────────────────────
    USE_MOCK_MODE:  bool = os.getenv("USE_MOCK_MODE", "True").lower() == "true"
    STREAMLIT_PORT: int  = int(os.getenv("STREAMLIT_PORT", "8501"))
    def validate(self) -> list:
        """
        Vérifie que toutes les variables obligatoires sont renseignées.
        Retourne une liste d'erreurs (liste vide = tout est OK).
        Appelée par run.py avant le lancement de l'application.
        """
        errors = []
        if self.USE_MOCK_MODE:
            # En mode démo, aucune clé n'est requise
            return errors
        #── OpenAI ───────────────────────────────────────────
        if not self.OPENAI_API_KEY or self.OPENAI_API_KEY.startswith("sk-xxx"):
            errors.append("❌OPENAI_API_KEY manquante ou invalide "
                "(utilisée par AnalystAgent et CoachAgent)"
            )
        # ── Groq ─────────────────────────────────────────────
        if not self.GROQ_API_KEY or self.GROQ_API_KEY.startswith("gsk_xxx"):
            errors.append("❌GROQ_API_KEY manquante ou invalide "
                "(utilisée par CVParser — obtenez-la sur console.groq.com)"
            )
        # ── Tavily ───────────────────────────────────────────
        if not self.TAVILY_API_KEY or self.TAVILY_API_KEY.startswith("tvly-xxx"):
            errors.append("❌TAVILY_API_KEY manquante ou invalide "
                "(utilisée par ScraperAgent — obtenez-la sur tavily.com)"
            )
        # ── Ollama ───────────────────────────────────────────
        # On vérifie qu'Ollama est accessible (pas de clé API, juste une URL)
        ollama_ok = self._check_ollama()
        if not ollama_ok:
            errors.append(f"❌Ollama inaccessible sur {self.OLLAMA_BASE_URL} "
                f"(utilisé par ExtractorAgent) — "
                f"Lancez : ollama serve  |  Puis : ollama pull {self.OLLAMA_MODEL}"
            )
        return errors
    def _check_ollama(self) -> bool:
        """Vérifie qu'Ollama tourne et que le modèle est disponible"""
        try:
            import requests as req
            # Vérifier que le serveur répond
            r = req.get(self.OLLAMA_BASE_URL, timeout=3)
            if "ollama" not in r.text.lower() and r.status_code != 200:
                return False
            # Vérifier que le modèle est téléchargé
            r2 = req.get(f"{self.OLLAMA_BASE_URL}/api/tags", timeout=3)
            models = [m["name"] for m in r2.json().get("models", [])]
            return any(self.OLLAMA_MODEL in m for m in models)
        except Exception:
            return False
    def summary(self) -> str:
        """
        Affiche un résumé lisible de la configuration active.
        Appelée par run.py au démarrage.
        """
        mode = "🟡DÉMO (données fictives)" if self.USE_MOCK_MODE else "🟢 PRODUCTION"
        ollama_status = "✅accessible" if self._check_ollama() else "❌inaccessible"
        openai_status = "✅ configurée" if self.OPENAI_API_KEY else "❌ manquante"
        groq_status = "✅ configurée" if self.GROQ_API_KEY else "❌ manquante"
        tavily_status = "✅ configurée" if self.TAVILY_API_KEY else "❌ manquante"
        return f"""
  Configuration active :
─────────────────────────────────────────────
  Mode              : {mode}
─────────────────────────────────────────────
  OpenAI API Key    : {openai_status}
└─ Modèle       : {self.OPENAI_MODEL}  (Analyste + Coach)
  Groq API Key      : {groq_status}
└─ Modèle       : {self.GROQ_MODEL}  (CVParser)
  Ollama            : {ollama_status}
└─ URL          : {self.OLLAMA_BASE_URL}
└─ Modèle       : {self.OLLAMA_MODEL}  (Extracteur)
  Tavily API Key    : {tavily_status}
└─ Usage        : ScraperAgent
  ChromaDB          : {self.CHROMA_DIR}
─────────────────────────────────────────────
"""
# ── Instance globale ────────────────────────────────────────
# Importez toujours cet objet, jamais la classe directement
settings = Settings()
# Créer les dossiers au premier import
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
# Injecter les clés dans l'environnement pour LangChain
# (LangChain lit automatiquement ces variables d'environnement)
if settings.OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
if settings.GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = settings.GROQ_API_KEY
if settings.TAVILY_API_KEY:
    os.environ["TAVILY_API_KEY"] = settings.TAVILY_API_KEY