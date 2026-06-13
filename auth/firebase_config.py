"""
auth/firebase_config.py
Initialisation Firebase Admin SDK
"""

import os
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, auth as fb_auth

# ── Chemin vers le fichier JSON ──────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
SERVICE_KEY = BASE_DIR / "serviceAccountKey.json"

# ── Clients globaux ───────────────────────────────────────────
db       = None
firebase = None

def init_firebase():
    global db, firebase
    if not firebase_admin._apps:
        # ── Priorité 1 : fichier JSON local (dev local) ──
        if SERVICE_KEY.exists():
            cred = credentials.Certificate(str(SERVICE_KEY))
        else:
            # ── Priorité 2 : variables d'environnement / secrets Streamlit Cloud ──
            private_key = os.environ.get("FIREBASE_PRIVATE_KEY", "")
            # Streamlit stocke les sauts de ligne littéraux comme \\n
            private_key = private_key.replace("\\n", "\n")
            service_account_info = {
                "type": "service_account",
                "project_id": os.environ.get("FIREBASE_PROJECT_ID", ""),
                "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID", ""),
                "private_key": private_key,
                "client_email": os.environ.get("FIREBASE_CLIENT_EMAIL", ""),
                "client_id": os.environ.get("FIREBASE_CLIENT_ID", ""),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_CERT_URL", ""),
                "universe_domain": "googleapis.com",
            }
            if not service_account_info["private_key"]:
                raise ValueError(
                    "Firebase non configuré : fichier serviceAccountKey.json absent "
                    "et variables d'environnement FIREBASE_PRIVATE_KEY manquantes."
                )
            cred = credentials.Certificate(service_account_info)
        firebase = firebase_admin.initialize_app(cred)
    else:
        firebase = firebase_admin.get_app()
    db = firestore.client()
    return db

# ── Initialisation au chargement ─────────────────────────────
try:
    init_firebase()
    print("Firebase initialisé avec succès")
except Exception as e:
    print(f"Avertissement Firebase : {e}")
    db = None