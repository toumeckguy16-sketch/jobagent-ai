"""
auth/firebase_config.py
Initialisation Firebase Admin SDK
"""

import os
import json
import firebase_admin
from firebase_admin import credentials, firestore, auth as fb_auth
from pathlib import Path

# --- Chemin vers le fichier JSON ---
BASE_DIR    = Path(__file__).resolve().parent
SERVICE_KEY = BASE_DIR / "serviceAccountKey.json"

# --- Clients globaux ---
_real_db = None
firebase = None
_init_errors = []

def init_firebase():
    global _real_db, firebase, _init_errors
    if not firebase_admin._apps:
        # --- Priorite 1 : fichier JSON local (dev local) ---
        if SERVICE_KEY.exists():
            try:
                cred = credentials.Certificate(str(SERVICE_KEY))
                firebase = firebase_admin.initialize_app(cred)
                _real_db = firestore.client()
                return _real_db
            except Exception as e:
                err = f"Fichier JSON local : {e}"
                print(err)
                _init_errors.append(err)
        else:
            _init_errors.append("Fichier JSON local : serviceAccountKey.json introuvable.")
        
        # --- Priorite 2 : FIREBASE_SERVICE_ACCOUNT_JSON (Streamlit secrets ou env) ---
        service_account_json = None
        try:
            import streamlit as st
            if "FIREBASE_SERVICE_ACCOUNT_JSON" in st.secrets:
                service_account_json = st.secrets["FIREBASE_SERVICE_ACCOUNT_JSON"]
        except Exception as e:
            _init_errors.append(f"Lecture streamlit.secrets (FIREBASE_SERVICE_ACCOUNT_JSON) echouee : {e}")
            
        if not service_account_json:
            service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")
            
        if service_account_json:
            try:
                if service_account_json.strip().startswith("{"):
                    service_account_info = json.loads(service_account_json)
                else:
                    with open(service_account_json, 'r', encoding='utf-8') as f:
                        service_account_info = json.load(f)
                cred = credentials.Certificate(service_account_info)
                firebase = firebase_admin.initialize_app(cred)
                _real_db = firestore.client()
                return _real_db
            except Exception as e:
                err = f"FIREBASE_SERVICE_ACCOUNT_JSON (env/secret) : {e}"
                print(err)
                _init_errors.append(err)
        else:
            _init_errors.append("FIREBASE_SERVICE_ACCOUNT_JSON : Non configure (absent de st.secrets et os.environ).")

        # --- Priorite 3 : variables d'environnement individuelles / secrets Streamlit ---
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
                err = f"Variables individuelles (env/secret) : {e}"
                print(err)
                _init_errors.append(err)
        else:
            _init_errors.append("Variables individuelles : FIREBASE_PRIVATE_KEY non configure.")

        # Si on arrive ici, aucune methode n'a fonctionne
        errors_str = "\n  - ".join(_init_errors)
        raise ValueError(
            f"Firebase non configure. Details des tentatives :\n  - {errors_str}"
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
            errors_str = "\n  - ".join(_init_errors)
            raise RuntimeError(
                "Le client Firestore n'a pas pu etre initialise.\n"
                "Veuillez configurer correctement Firebase sur Streamlit Cloud dans vos Secrets.\n"
                f"Details des erreurs rencontrees :\n  - {errors_str}"
            )
        return getattr(client, name)

    def __bool__(self):
        return get_db() is not None

# L'instance de proxy exportee pour tout le projet
db = FirestoreProxy()

# --- Initialisation au chargement ---
try:
    init_firebase()
    print("Firebase initialise avec succes")
except Exception as e:
    print(f"Avertissement Firebase a l'importation : {e}")
    _real_db = None
