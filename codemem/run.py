"""
run.py — Point d'entrée unique du projet
=========================================
Lance l'application Streamlit depuis la racine du projet.
Utilisation :
    python run.py              # Lance l'app normalement
    python run.py --check      # Vérifie la config sans lancer
    python run.py --mock       # Force le mode démo (sans API)
    python run.py --no-auth    # Sans page de connexion (accès direct)
    python run.py --port 8502  # Port personnalisé
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
from config.settings import settings
def check_config() -> bool:
    """Vérifie que tout est bien configuré avant de lancer"""
    print("\nVérification de la configuration...\n")
    print(settings.summary())
    # Fichiers critiques
    critical_files = [
        ROOT / "orchestrator.py",
        ROOT / "agents" / "scraper_agent.py",
        ROOT / "agents" / "extractor_agent.py",
        ROOT / "agents" / "analyst_agent.py",
        ROOT / "agents" / "coach_agent.py",
        ROOT / "utils"  / "cv_parser.py",
        ROOT / "ui"     / "app.py",
        ROOT / "ui"     / "login_page.py",
        ROOT / "auth"   / "firebase_config.py",
        ROOT / "auth"   / "auth_manager.py",
        ROOT / "auth"   / "serviceAccountKey.json",
        ROOT / "config" / "settings.py",
    ]
    missing = [f for f in critical_files if not f.exists()]
    if missing:
        for f in missing:
            print(f"  Fichier manquant : {f.relative_to(ROOT)}")
        return False
    print("  Tous les fichiers sont présents")
    errors = settings.validate()
    if errors:
        print("\n  Problèmes détectés :\n")
        for e in errors:
            print(f"    {e}")
        return False
    print("  Configuration valide\n")
    return True
def run_app(port: str, no_auth: bool = False):
    """Lance l'application Streamlit"""
    # Si --no-auth, lancer directement app.py sans login
    app_path = ROOT / "ui" / "app.py" if no_auth else ROOT / "run_streamlit.py"
    print(f"\nLancement de JobAgent AI sur http://localhost:{port}")
    print("Ctrl+C pour arrêter\n")
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port",              port,
        "--server.headless",          "false",
        "--browser.gatherUsageStats", "false",
    ]
    subprocess.run(cmd, cwd=str(ROOT))
def main():
    parser = argparse.ArgumentParser(
        description="JobAgent AI — Système Multi-Agents de Recherche d'Emploi"
    )
    parser.add_argument("--check",   action="store_true",
                        help="Vérifie la configuration sans lancer l'app")
    parser.add_argument("--mock",    action="store_true",
                        help="Force le mode démo (sans API)")
    parser.add_argument("--no-auth", action="store_true",
                        help="Lance l'app sans page de connexion")
    parser.add_argument("--port",    default=str(settings.STREAMLIT_PORT),
                        help="Port Streamlit (défaut : 8501)")
    args = parser.parse_args()
    # Mode mock
    if args.mock:
        os.environ["USE_MOCK_MODE"]  = "True"
        settings.USE_MOCK_MODE       = True
        print("Mode démo (mock) activé")
    # Mode sans auth
    if args.no_auth:
        os.environ["JOBAGENT_NO_AUTH"] = "1"
    print("=" * 55)
    print("    JobAgent AI — Système Multi-Agents")
    print("    Mainto Studio &copy; 2026")
    print("=" * 55)
    ok = check_config()
    if args.check:
        sys.exit(0 if ok else 1)
    if not ok and not settings.USE_MOCK_MODE:
        print("Corrigez les erreurs ou lancez avec --mock\n")
        sys.exit(1)
    run_app(port=args.port, no_auth=args.no_auth)
if __name__ == "__main__":
    main()