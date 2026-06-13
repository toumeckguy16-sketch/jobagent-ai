"""
auth/firebase_config.py
Initialisation Firebase Admin SDK
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, auth as fb_auth
from pathlib import Path

# ── Chemin vers le fichier JSON ──────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
SERVICE_KEY = BASE_DIR / "serviceAccountKey.json"

# ── Clients globaux ───────────────────────────────────────────
_real_db = None
firebase = None

def init_firebase():
    global _real_db, firebase
    if not firebase_admin._apps:
        # ── Priorité 1 : fichier JSON local (dev local) ──
        if SERVICE_KEY.exists():
            try:
                cred = credentials.Certificate(str(SERVICE_KEY))
                firebase = firebase_admin.initialize_app(cred)
                _real_db = firestore.client()
                return _real_db
            except Exception as e:
                print(f"Erreur d'initialisation avec serviceAccountKey.json : {e}")
        
        # ── Priorité 2 : FIREBASE_SERVICE_ACCOUNT_JSON (Streamlit secrets ou env) ──
        # On essaie d'abord de récupérer via streamlit secrets, puis via os.environ
        service_account_json = None
        try:
            import streamlit as st
            if "FIREBASE_SERVICE_ACCOUNT_JSON" in st.secrets:
                service_account_json = st.secrets["FIREBASE_SERVICE_ACCOUNT_JSON"]
        except Exception:
            pass
            
        if not service_account_json:
            service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")
            
        if service_account_json:
            try:
                # Si c'est un chemin de fichier, ou directement le contenu JSON
                if service_account_json.strip().startswith("{"):
                    service_account_info = json.loads(service_account_json)
                else:
                    # C'est peut-être un chemin vers un fichier
                    with open(service_account_json, 'r', encoding='utf-8') as f:
                        service_account_info = json.load(f)
                cred = credentials.Certificate(service_account_info)
                firebase = firebase_admin.initialize_app(cred)
                _real_db = firestore.client()
                return _real_db
            except Exception as e:
                print(f"Erreur d'initialisation avec FIREBASE_SERVICE_ACCOUNT_JSON : {e}")

        # ── Priorité 3 : variables d'environnement individuelles / secrets Streamlit ──
        def get_secret(key):
            try:
                import streamlit as st
                if key in st.secrets:
                    return st.secrets[key]
            except Exception:
                pass
            return os.environ.get(key, "")

        private_key = get_secret("FIREBASE_PRIVATE_KEY")
        if private_key:
            # Streamlit/env stocke parfois les sauts de ligne comme \\n
            private_key = private_key.replace("\\n", "\n")
            try:
                service_account_info = {
                    "type": "service_account",
                    "project_id": get_secret("FIREBASE_PROJECT_ID"),
                    "private_key_id": get_secret("FIREBASE_PRIVATE_KEY_ID"),
                    "private_key": private_key,
                    "client_email": get_secret("FIREBASE_CLIENT_EMAIL"),
                    "client_id": get_secret("FIREBASE_CLIENT_ID"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "client_x509_cert_url": get_secret("FIREBASE_CLIENT_CERT_URL"),
                    "universe_domain": "googleapis.com",
                }
                cred = credentials.Certificate(service_account_info)
                firebase = firebase_admin.initialize_app(cred)
                _real_db = firestore.client()
                return _real_db
            except Exception as e:
                print(f"Erreur d'initialisation avec variables individuelles : {e}")

        # Si on arrive ici, aucune méthode n'a fonctionné
        raise ValueError(
            "Firebase non configuré : serviceAccountKey.json absent, "
            "FIREBASE_SERVICE_ACCOUNT_JSON absent, et variables d'environnement manquantes ou invalides."
        )
    else:
        firebase = firebase_admin.get_app()
        _real_db = firestore.client()
        return _real_db

def get_db():
    global _real_db
    if _real_db is None:
        try:
            _real_db = init_firebase()
        except Exception as e:
            print(f"Erreur get_db : {e}")
            _real_db = None
    return _real_db

class FirestoreProxy:
    def __getattr__(self, name):
        client = get_db()
        if client is None:
            raise RuntimeError(
                "Le client Firestore n'a pas pu être initialisé. "
                "Veuillez vérifier que le fichier serviceAccountKey.json est présent ou "
                "que le secret FIREBASE_SERVICE_ACCOUNT_JSON (ou les variables individuelles) est configuré."
            )
        return getattr(client, name)

    def __bool__(self):
        return get_db() is not None

# L'instance de proxy exportée pour tout le projet
db = FirestoreProxy()

# ── Initialisation au chargement ─────────────────────────────
try:
    init_firebase()
    print("Firebase initialisé avec succès")
except Exception as e:
    print(f"Avertissement Firebase à l'importation : {e}")
    _real_db = None