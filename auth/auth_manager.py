"""
auth/auth_manager.py
Gestion Login / Register / Google OAuth via Firebase REST API
"""
import os
import requests
import time
from datetime import datetime
from auth.firebase_config import db, fb_auth
FIREBASE_API_KEY = "AIzaSyDPzWlUWTTJglkNcwNe-SdfqDfZXFrChCs"
URL_REFRESH = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
# ── URLs Firebase Auth REST ───────────────────────────────────
URL_SIGNUP  = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
URL_SIGNIN  = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
URL_GOOGLE  = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={FIREBASE_API_KEY}"
URL_RESET   = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_API_KEY}"
class AuthManager:
    """Gère l'authentification Firebase (email/password + Google)"""
    # ─────────────────────────────────────────
    #  INSCRIPTION EMAIL / MOT DE PASSE
    # ─────────────────────────────────────────
    @staticmethod
    def register(email: str, password: str, full_name: str) -> dict:
        """
        Crée un compte Firebase et enregistre le profil dans Firestore.
        Returns: {"success": True, "user": {...}} ou {"success": False, "error": "..."}
        """
        payload = {
            "email":             email,
            "password":          password,
            "returnSecureToken": True,
        }
        resp = requests.post(URL_SIGNUP, json=payload)
        data = resp.json()
        if "error" in data:
            return {"success": False, "error": AuthManager._translate_error(data["error"]["message"])}
        uid = data["localId"]
        # Mettre à jour le displayName
        requests.post(
            f"https://identitytoolkit.googleapis.com/v1/accounts:update?key={FIREBASE_API_KEY}",
            json={"idToken": data["idToken"], "displayName": full_name, "returnSecureToken": False}
        )
        # Sauvegarder dans Firestore
        AuthManager._save_user_firestore(uid, {
            "uid":        uid,
            "email":      email,
            "full_name":  full_name,
            "provider":   "email",
            "created_at": datetime.now().isoformat(),
            "last_login": datetime.now().isoformat(),
        })
        return {
            "success":    True,
            "user": {
                "uid":           uid,
                "email":         email,
                "full_name":     full_name,
                "provider":      "email",
                "id_token":      data["idToken"],
                "refresh_token": data.get("refreshToken", ""),
                "expires_at":    time.time() + int(data.get("expiresIn", 3600)),
            }
        }
    # ─────────────────────────────────────────
    #  CONNEXION EMAIL / MOT DE PASSE
    # ─────────────────────────────────────────
    @staticmethod
    def login(email: str, password: str) -> dict:
        payload = {
            "email":             email,
            "password":          password,
            "returnSecureToken": True,
        }
        resp = requests.post(URL_SIGNIN, json=payload)
        data = resp.json()
        if "error" in data:
            return {"success": False, "error": AuthManager._translate_error(data["error"]["message"])}
        uid = data["localId"]
        # Mettre à jour last_login
        AuthManager._update_last_login(uid)
        # Récupérer le profil Firestore
        profile = AuthManager._get_user_firestore(uid)
        full_name = profile.get("full_name", data.get("displayName", "Utilisateur"))
        return {
            "success": True,
            "user": {
                "uid":           uid,
                "email":         email,
                "full_name":     full_name,
                "provider":      "email",
                "id_token":      data["idToken"],
                "refresh_token": data.get("refreshToken", ""),
                "expires_at":    time.time() + int(data.get("expiresIn", 3600)),
            }
        }
    # ──────────────────────────────────────────
    #  RÉINITIALISATION MOT DE PASSE
    # ──────────────────────────────────────────
    @staticmethod
    def reset_password(email: str) -> dict:
        payload = {"requestType": "PASSWORD_RESET", "email": email}
        resp = requests.post(URL_RESET, json=payload)
        data = resp.json()
        if "error" in data:
            return {"success": False, "error": AuthManager._translate_error(data["error"]
["message"])}
        return {"success": True}
    # ─────────────────────────────────────────
    #  FIRESTORE — UTILITAIRES
    # ─────────────────────────────────────────
    @staticmethod
    def _save_user_firestore(uid: str, user_data: dict):
        db.collection("users").document(uid).set(user_data)
    @staticmethod
    def _get_user_firestore(uid: str) -> dict:
        doc = db.collection("users").document(uid).get()
        return doc.to_dict() if doc.exists else {}
    @staticmethod
    def _update_last_login(uid: str):
        try:
            db.collection("users").document(uid).update({
                "last_login": datetime.now().isoformat()
            })
        except Exception:
            pass
    # ──────────────────────────────────────────
    #  TRADUCTION DES ERREURS FIREBASE
    # ─────────────────────────────────────────
    @staticmethod
    def _translate_error(code: str) -> str:
        errors = {
            "EMAIL_EXISTS":               "Cette adresse email est déjà utilisée.",
            "INVALID_EMAIL":              "Adresse email invalide.",
            "WEAK_PASSWORD":              "Mot de passe trop faible (minimum 6 caractères).",
            "EMAIL_NOT_FOUND":            "Aucun compte trouvé avec cet email.",
            "INVALID_PASSWORD":           "Mot de passe incorrect.",
            "USER_DISABLED":              "Ce compte a été désactivé.",
            "TOO_MANY_ATTEMPTS_TRY_LATER":"Trop de tentatives. Réessayez plus tard.",
            "INVALID_LOGIN_CREDENTIALS":  "Email ou mot de passe incorrect.",
        }
        return errors.get(code, f"Erreur : {code}")

    @staticmethod
    def save_profile(uid: str, profile: dict):
        """Sauvegarde le profil candidat dans Firestore"""
        try:
            db.collection("users").document(uid).set({
                "candidate_profile":  profile,
                "profile_updated_at": datetime.now().isoformat()
            }, merge=True)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde profil : {e}")
            return False

    @staticmethod
    def load_profile(uid: str) -> dict:
        """Charge le profil candidat depuis Firestore"""
        try:
            doc = db.collection("users").document(uid).get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("candidate_profile", None)
            return None
        except Exception as e:
            print(f"Erreur chargement profil : {e}")
            raise e

    @staticmethod
    def refresh_id_token(refresh_token_str: str) -> dict:
        """Rafraîchit le token Firebase silencieusement (sans déconnecter l'utilisateur)."""
        try:
            resp = requests.post(
                URL_REFRESH,
                data={"grant_type": "refresh_token", "refresh_token": refresh_token_str},
                timeout=5
            )
            data = resp.json()
            if "id_token" in data:
                return {
                    "success": True,
                    "id_token": data["id_token"],
                    "refresh_token": data.get("refresh_token", refresh_token_str)
                }
            return {"success": False, "error": str(data.get("error", "Refresh failed"))}
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": "network_error"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_preferences(uid: str, prefs: dict) -> bool:
        """Sauvegarde les préférences utilisateur (thème, etc.) dans Firestore."""
        try:
            db.collection("users").document(uid).set({
                "preferences": prefs,
                "prefs_updated_at": datetime.now().isoformat()
            }, merge=True)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde préférences : {e}")
            return False

    @staticmethod
    def load_preferences(uid: str) -> dict:
        """Charge les préférences utilisateur depuis Firestore."""
        try:
            doc = db.collection("users").document(uid).get()
            if doc.exists:
                return doc.to_dict().get("preferences", {})
            return {}
        except Exception as e:
            print(f"Erreur chargement préférences : {e}")
            raise e

    @staticmethod
    def save_job_search_results(uid: str, pipeline_result: dict):
        """Sauvegarde les résultats de la recherche (offres et scores) dans Firestore"""
        try:
            db.collection("users").document(uid).set({
                "pipeline_result": pipeline_result,
                "search_updated_at": datetime.now().isoformat()
            }, merge=True)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde offres : {e}")
            return False

    @staticmethod
    def load_job_search_results(uid: str) -> dict:
        """Charge les résultats de la recherche depuis Firestore"""
        try:
            doc = db.collection("users").document(uid).get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("pipeline_result", None)
            return None
        except Exception as e:
            print(f"Erreur chargement offres : {e}")
            raise e

    @staticmethod
    def save_chat_history(uid: str, chat_sessions: dict):
        """Sauvegarde l'historique complet des sessions de chat dans Firestore"""
        try:
            db.collection("users").document(uid).set({
                "chat_sessions": chat_sessions,
                "chat_updated_at": datetime.now().isoformat()
            }, merge=True)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde chat : {e}")
            return False

    @staticmethod
    def load_chat_history(uid: str) -> dict:
        """Charge l'historique de toutes les sessions de chat depuis Firestore"""
        try:
            doc = db.collection("users").document(uid).get()
            if doc.exists:
                data = doc.to_dict()
                return data.get("chat_sessions", {})
            return {}
        except Exception as e:
            print(f"Erreur chargement chat : {e}")
            raise e
    @staticmethod
    def save_job_history(uid: str, pipeline_result: dict):
        """Ajoute une recherche à l'historique de l'utilisateur dans une sous-collection"""
        if db is None: return False
        try:
            # On utilise un document indexé par timestamp pour l'historique
            now = datetime.now()
            timestamp = now.strftime("%Y%m%d_%H%M%S")
            history_entry = {
                "id": timestamp,
                "date": now.isoformat(),
                "query": pipeline_result.get("user_profile", "")[:150],
                "job_count": len(pipeline_result.get("jobs_with_skills", [])),
                "pipeline_result": pipeline_result
            }
            # Sauvegarde dans la sous-collection 'job_history'
            db.collection("users").document(uid).collection("job_history").document(timestamp).set(history_entry)
            return True
        except Exception as e:
            print(f"Erreur sauvegarde historique : {e}")
            return False

    @staticmethod
    def get_job_history(uid: str, limit: int = 20):
        """Récupère l'historique des recherches trié par date décroissante"""
        if db is None: return []
        try:
            from firebase_admin import firestore
            docs = db.collection("users").document(uid).collection("job_history")\
                     .order_by("date", direction=firestore.Query.DESCENDING).limit(limit).stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"Erreur lecture historique : {e}")
            return []
    @staticmethod
    def get_saved_profiles(uid: str):
        """Récupère la liste des profils sauvegardés pour cet utilisateur"""
        if db is None: return []
        try:
            docs = db.collection("users").document(uid).collection("saved_profiles").stream()
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            print(f"Erreur lecture profils : {e}")
            return []

    @staticmethod
    def load_saved_profile(uid: str, profile_id: str):
        """Charge un profil spécifique depuis la collection saved_profiles"""
        if db is None: return None
        try:
            doc = db.collection("users").document(uid).collection("saved_profiles").document(profile_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"Erreur chargement profil : {e}")
            return None
