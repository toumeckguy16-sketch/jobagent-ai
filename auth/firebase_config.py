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
    if not SERVICE_KEY.exists():
        raise FileNotFoundError(
            f"serviceAccountKey.json introuvable dans : {BASE_DIR}"
        )
    if not firebase_admin._apps:
        cred     = credentials.Certificate(str(SERVICE_KEY))
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