"""
Interface Utilisateur Streamlit — JobAgent AI
Deux thèmes : Sombre (#0F0F0F / #E5E5E5 / #FF6B00)
              Clair  (#FFFFFF / #16A34A / #DC2626)
Quiz QCM avec correction automatique et score final.
"""

import streamlit as st
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ajouter le dossier parent au path pour les imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import run_pipeline
from agents.scraper_agent import ScraperAgent
from agents.extractor_agent import ExtractorAgent
from agents.analyst_agent import AnalystAgent
from agents.coach_agent import CoachAgent
from utils.cv_parser        import CVParser

# Forcer le rechargement de AuthManager pour éviter les imports obsolètes
import importlib
import auth.auth_manager
importlib.reload(auth.auth_manager)
from auth.auth_manager import AuthManager
# ============================================================
# CONFIGURATION DE LA PAGE
# ============================================================
st.set_page_config(
    page_title="JobAgent AI",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SESSION STATE
# ============================================================
def init_session():
    """Initialise les variables de session State."""
    defaults = {
        "pipeline_result": None,
        "selected_job": None,
        "chat_history": {},
        "chats": [],
        "current_chat": None,
        "show_chat_history": False,
        "quiz_questions": [],
        "quiz_answers": {},
        "quiz_submitted": False,
        "use_mock": False,
        "candidate_profile": None,
        "profile_source": None,
        "cv_filename": None,
        "user_profile_text": "",
        "theme": "dark",
        "current_page": None,  # Défini après chargement du profil
        "previous_page": None,
        "profile_image_url": None,
        "job_history": [],
        "rejected_sites": {},
        "prep_view": "quiz",
        # ── Réseau & session ──
        "network_error_count": 0,
        "network_last_ok": None,
        "prefs_loaded": False,
        "chat_loaded": False,
        "profile_checked_empty": False,
        "profile_load_attempts": 0,
        "is_new_user": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # ── Restauration du thème depuis les query_params (alimenté par localStorage via JS) ──
    qp_theme = st.query_params.get("theme", None)
    if qp_theme in ("dark", "light"):
        st.session_state.theme = qp_theme

    # ── Chargement données Firebase si utilisateur connecté ──
    if st.session_state.get("logged_in") and st.session_state.get("user"):
        uid = st.session_state.user.get("uid")

        # Rafraîchissement du token basé sur l'expiration réelle
        refresh_tok = st.session_state.user.get("refresh_token", "")
        expires_at = st.session_state.user.get("expires_at", 0)
        if not expires_at:
            expires_at = time.time() + 3600
            st.session_state.user["expires_at"] = expires_at

        # Si le token a expiré ou expire dans moins de 5 min (300s)
        if refresh_tok and time.time() > expires_at - 300:
            try:
                import json
                result = AuthManager.refresh_id_token(refresh_tok)
                if result.get("success"):
                    st.session_state.user["id_token"]      = result["id_token"]
                    st.session_state.user["refresh_token"] = result["refresh_token"]
                    st.session_state.user["expires_at"]    = time.time() + 3600
                    st.session_state.network_error_count   = 0
                    st.session_state.network_last_ok       = datetime.now().isoformat()
                    
                    # Synchroniser la session en localStorage
                    user_json = json.dumps(st.session_state.user).replace("'", "\\'")
                    st.markdown(f"""
                    <script>
                    try {{
                        localStorage.setItem('jobagent_session', '{user_json}');
                    }} catch(e) {{}}
                    </script>
                    """, unsafe_allow_html=True)
                elif result.get("error") == "network_error":
                    # Incrémenter le compteur d'erreurs réseau consécutives
                    st.session_state.network_error_count = st.session_state.get("network_error_count", 0) + 1
                    
                    # Tolérance panne réseau : déconnexion forcée uniquement après 10 échecs consécutifs
                    # OU si expiré depuis plus de 30 minutes (1800s)
                    if time.time() > expires_at + 1800 or st.session_state.network_error_count > 10:
                        st.session_state.logged_in = False
                        st.session_state.user = None
                        st.session_state.candidate_profile = None
                        st.markdown("""
                        <script>
                        try {
                            localStorage.removeItem('jobagent_session');
                        } catch(e) {}
                        </script>
                        """, unsafe_allow_html=True)
                        st.rerun()
                else:
                    # Erreur Firebase critique (token révoqué, compte désactivé, etc.)
                    # Sécurité : déconnexion forcée immédiate
                    st.session_state.logged_in = False
                    st.session_state.user = None
                    st.session_state.candidate_profile = None
                    st.markdown("""
                    <script>
                    try {
                        localStorage.removeItem('jobagent_session');
                    } catch(e) {}
                    </script>
                    """, unsafe_allow_html=True)
                    st.rerun()
            except Exception:
                pass

        # Chargement des préférences (thème Firebase) — une seule fois par session
        if not st.session_state.get("prefs_loaded"):
            try:
                prefs = AuthManager.load_preferences(uid)
                if prefs.get("theme") in ("dark", "light") and not qp_theme:
                    # Appliquer le thème Firebase uniquement si pas déjà défini par URL
                    st.session_state.theme = prefs["theme"]
                    st.query_params["theme"] = prefs["theme"]
                st.session_state.prefs_loaded = True
            except Exception:
                pass # Retenter au prochain run si réseau indisponible

        # Chargement du profil candidat si absent
        if st.session_state.get("candidate_profile") is None and not st.session_state.get("profile_checked_empty"):
            st.session_state.profile_load_attempts = st.session_state.get("profile_load_attempts", 0) + 1
            try:
                profile = AuthManager.load_profile(uid)
                if profile:
                    st.session_state.candidate_profile = profile
                    st.session_state.user_profile_text = profile.get("profile_text", "")
                    st.session_state.profile_source    = profile.get("profile_source", "text")
                    st.session_state.cv_filename       = profile.get("cv_filename", None)
                    if profile.get("saved_pipeline_result"):
                        st.session_state.pipeline_result = profile["saved_pipeline_result"]
                    elif st.session_state.get("pipeline_result") is None:
                        pipeline_result = AuthManager.load_job_search_results(uid)
                        if pipeline_result:
                            st.session_state.pipeline_result = pipeline_result
                else:
                    # Le profil n'existe pas encore dans Firestore
                    st.session_state.profile_checked_empty = True
            except Exception:
                # Mode dégradé si échecs répétés (permet d'accéder hors-ligne)
                if st.session_state.profile_load_attempts >= 3:
                    st.session_state.profile_checked_empty = True
                pass

        # Chargement de l'historique de chat (une seule fois pour éviter le lag)
        if not st.session_state.get("chat_loaded"):
            try:
                history = AuthManager.load_chat_history(uid)
                if isinstance(history, dict) and history:
                    st.session_state.chat_history = history
                    if "chats_list" in history:
                        st.session_state.chats = history["chats_list"]
                    else:
                        migrated = [
                            {"id": f"Historique : {k}", "messages": v}
                            for k, v in history.items()
                            if k != "chats_list" and isinstance(v, list)
                        ]
                        st.session_state.chats = migrated
                        history["chats_list"] = migrated
                        AuthManager.save_chat_history(uid, history)
                elif not isinstance(st.session_state.chat_history, dict):
                    st.session_state.chat_history = {}
                st.session_state.chat_loaded = True
            except Exception:
                pass  # Conserver l'historique en mémoire si Firebase indisponible

        # ── Détermination de la page par défaut après authentification ──
        if st.session_state.get("current_page") is None:
            if st.session_state.get("candidate_profile") is not None:
                # Vérifier si le profil est incomplet (sans résumé ni compétences ni texte)
                prof = st.session_state.candidate_profile
                is_incomplete = not prof.get("summary") and not prof.get("hard_skills") and not prof.get("profile_text")
                if is_incomplete or st.session_state.get("is_new_user"):
                    st.session_state.current_page = "Profil"
                else:
                    st.session_state.current_page = "Dashboard"
            elif st.session_state.get("profile_checked_empty") or st.session_state.get("is_new_user"):
                # Pas de profil ou nouvel utilisateur
                st.session_state.current_page = "Profil"

init_session()

# ── Injection JS : lecture/écriture du thème dans localStorage ───────────────
st.markdown("""
<script>
(function() {
    try {
        const saved = localStorage.getItem('jobagent_theme');
        const params = new URLSearchParams(window.parent.location.search);
        if (saved && !params.has('theme')) {
            // Thème en localStorage mais absent de l'URL → rediriger pour que Python le lise
            params.set('theme', saved);
            window.parent.history.replaceState(null, '', '?' + params.toString());
            window.parent.location.reload();
        } else if (params.has('theme')) {
            // Synchroniser localStorage avec l'URL courante
            localStorage.setItem('jobagent_theme', params.get('theme'));
        }
    } catch(e) {}
})();
</script>
""", unsafe_allow_html=True)

# ============================================================
# THàË†MES (DARK / LIGHT)
# ============================================================
THEMES = {
    "dark": {
        "bg_main":      "#0F0F0F",
        "bg_card":      "#1A1A1A",
        "bg_sidebar":   "#111111",
        "bg_input":     "#1F1F1F",
        "text_main":    "#E5E5E5",
        "text_muted":   "#888888",
        "text_subtle":  "#555555",
        "accent":       "#FF6B00",
        "accent_hover": "#FF8C33",
        "border":       "#2A2A2A",
        "border_focus": "#FF6B00",
        "success":      "#22C55E",
        "error":        "#EF4444",
        "warning":      "#F59E0B",
        "progress":     "#FF6B00",
        "bg_backdrop":  "rgba(0, 0, 0, 0.7)",
        "toggle_label": "Thème clair",
    },
    "light": {
        "bg_main":      "#FFFFFF",
        "bg_card":      "#F5F5F5",
        "bg_sidebar":   "#FAFAFA",
        "bg_input":     "#FFFFFF",
        "text_main":    "#111111",
        "text_muted":   "#555555",
        "text_subtle":  "#999999",
        "accent":       "#DC2626",
        "accent_hover": "#16A34A",
        "border":       "#E0E0E0",
        "border_focus": "#DC2626",
        "success":      "#16A34A",
        "error":        "#DC2626",
        "warning":      "#D97706",
        "progress":     "#DC2626",
        "bg_backdrop":  "rgba(255, 255, 255, 0.4)",
        "toggle_label": "Thème sombre",
    }
}

T = THEMES[st.session_state.theme]

# ── Écran de chargement pendant la résolution de la redirection ──
if st.session_state.get("logged_in") and st.session_state.get("current_page") is None:
    st.markdown(f"""
    <div style='display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh;'>
        <div class='loader' style='border: 4px solid {T["border"]}; border-top: 4px solid {T["accent"]}; border-radius: 50%; width: 45px; height: 45px; animation: spin 1s linear infinite; margin-bottom: 20px;'></div>
        <div style='font-family: "Syne", sans-serif; font-size: 1.25em; font-weight: 700; color: {T["text_main"]}; letter-spacing: -0.5px;'>Chargement de votre espace personnalisé...</div>
    </div>
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    html, body, .stApp {{
        background-color: {T["bg_main"]} !important;
    }}
    </style>
    """, unsafe_allow_html=True)
    time.sleep(0.4)
    st.rerun()

@st.dialog("Analyse de compatibilité")
def show_job_analysis(job):
    """Affiche les détails de l'analyse dans un popup."""
    score = job.get("score", 0)
    color = T["success"] if score >= 75 else T["warning"] if score >= 50 else T["error"]
    
    st.markdown(f"### {job['title']}")
    st.markdown(f"<div style='color:{T['accent']}; font-weight:700; margin-top:-15px; margin-bottom:15px;'>{job.get('company', 'Entreprise inconnue')}</div>", unsafe_allow_html=True)
    
    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        st.markdown(f"""
        <div style='text-align:center; background:{T["bg_main"]};
                    border-radius:10px; padding:20px;
                    border:2px solid {color};'>
            <div style='font-family:Roboto,sans-serif; font-size:2.2em;
                        font-weight:800; color:{color};'>{score}%</div>
            <div style='color:{T["text_muted"]}; font-size:0.8em;'>Match</div>
        </div>
        """, unsafe_allow_html=True)
        
        vector_score = job.get("vector_score", "N/A")
        llm_score = job.get("llm_score", "N/A")
        vec_display = f"{vector_score}%" if isinstance(vector_score, (int, float)) else vector_score
        llm_display = f"{llm_score}%" if isinstance(llm_score, (int, float)) else llm_score
        
        st.markdown(f"""
        <div style='text-align:center; margin-top:8px; font-family:Roboto,sans-serif; font-size:0.85em; color:{T["text_main"]}; line-height:1.4;'>
            Score vectoriel : <strong>{vec_display}</strong><br>
            Score LLM : <strong>{llm_display}</strong>
        </div>
        """, unsafe_allow_html=True)
    
    with col_s2:
        st.markdown(f"**Localisation :** {job.get('location', 'N/A')}")
        st.markdown(f"**Source :** {job.get('source', 'N/A')}")
        st.markdown(f"**Secteurs :** {', '.join(job.get('sectors', [])) if job.get('sectors') else 'N/A'}")
    
    st.markdown("<hr>", unsafe_allow_html=True)
    
    matching = job.get("matching_skills", [])
    missing = job.get("missing_skills", [])
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("✅ **Compétences correspondantes**")
        if matching:
            html_skills = "".join(f"<span class='skill-pill'>{s}</span>" for s in matching)
            st.markdown(html_skills, unsafe_allow_html=True)
        else:
            st.write("Aucune correspondance directe.")
            
    with c2:
        st.markdown("❌ **Compétences manquantes**")
        if missing:
            html_missing = "".join([
                f"<span style='display:inline-block; background:{T['error']}15; color:{T['error']}; "
                f"border:1px solid {T['error']}44; padding:3px 12px; border-radius:20px; "
                f"font-size:0.8em; margin:3px;'>{s}</span>" 
                for s in missing
            ])
            st.markdown(html_missing, unsafe_allow_html=True)
        else:
            st.write("Profil complet pour ce poste !")
            
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"💡 **Recommandations du Coach**")
    recs = job.get("recommendations", [])
    if recs:
        for r in recs:
            st.markdown(f"- {r}")
    else:
        st.write("Aucune recommandation spécifique.")
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Fermer", use_container_width=True):
        st.rerun()

# ============================================================
# CSS DYNAMIQUE
# ============================================================
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700;900&family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap');

html, body, .stApp {{
    background-color: {T['bg_main']} !important;
    font-family: 'DM Sans', sans-serif;
    color: {T['text_main']} !important;
}}

header[data-testid="stHeader"] {{
    background-color: {T['bg_main']} !important;
    background: transparent !important;
}}

[data-testid="stSidebar"] {{
    background: {T['bg_sidebar']} !important;
    border-right: 1px solid {T['border']};
}}

[data-testid="stSidebar"] * {{ color: {T['text_main']} !important; }}

h1, h2, h3 {{
    font-family: 'Roboto', sans-serif !important;
    color: {T['text_main']} !important;
}}

h1 {{
    font-size: 1.5em !important;
}}

/* Boutons transparents avec bordure orange (Interface principale) */
.stButton > button {{
    background: transparent !important;
    color: {T['text_main']} !important;
    border: 1px solid {T['accent']} !important;
    border-radius: 8px !important;
    font-family: 'Roboto', sans-serif !important;
    font-weight: 500 !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}}

/* Navigation Sidebar - Minimalisme Monochrome */
[data-testid="stSidebar"] .stButton > button {{
    justify-content: flex-start !important;
    padding-left: 0.5rem !important;
    border: none !important;
    height: 34px !important; /* Boutons plus compacts */
    margin: 0 !important;
    background: transparent !important;
    color: {T['text_main']} !important;
}}

/* Réduction de l'espace entre les éléments de la sidebar */
[data-testid="stSidebar"] [data-testid="element-container"] {{
    margin-bottom: -18px !important;
}}

[data-testid="stSidebar"] {{
    width: 250px !important;
    transition: all 0.3s ease !important;
}}

/* === MINI SIDEBAR : GARDER UNIQUEMENT LES ICÔNES === */
section[data-testid="stSidebar"][aria-expanded="false"] {{
    margin-left: 0 !important;
    width: 60px !important;
    min-width: 60px !important;
    transform: translateX(0) !important;
    overflow: hidden !important;
}}

/* Masquer le texte mais garder l'icône (1er caractère) */
section[data-testid="stSidebar"][aria-expanded="false"] .stButton button p {{
    font-size: 0 !important;
    line-height: 0 !important;
    color: transparent !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] .stButton button p::first-letter {{
    font-size: 1.6rem !important;
    visibility: visible !important;
    color: {T['text_main']} !important;
    margin-left: 5px !important;
}}

/* Masquer logo, infos profil et boutons de déconnexion */
section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-logo,
section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-profile-info,
section[data-testid="stSidebar"][aria-expanded="false"] .btn-logout-sidebar,
section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="column"]:nth-child(2) {{
    display: none !important;
}}

/* Forcer l'affichage de l'avatar au centre */
section[data-testid="stSidebar"][aria-expanded="false"] .sidebar-profile-container {{
    display: flex !important;
    justify-content: center !important;
    width: 100% !important;
    position: fixed !important;
    bottom: 20px !important;
    left: 0 !important;
    padding: 0 !important;
}}

section[data-testid="stSidebar"][aria-expanded="false"] #profile-pic-sidebar {{
    width: 42px !important;
    height: 42px !important;
    margin: 0 !important;
    border: 2px solid {T['accent']} !important;
}}

/* Centrer les icônes de nav */
section[data-testid="stSidebar"][aria-expanded="false"] .stButton button {{
    padding: 0 !important;
    justify-content: center !important;
    width: 100% !important;
    height: 50px !important;
}}

/* ============================================== */

[data-testid="stSidebar"] .stButton > button > div {{
    display: flex !important;
    justify-content: flex-start !important;
    width: 100% !important;
    align-items: center !important;
}}

[data-testid="stSidebar"] .stButton > button p {{
    text-align: left !important;
    margin: 0 !important;
    font-size: 0.9em !important;
    white-space: nowrap !important;
}}

/* Icônes plus grandes */
.nav-icon {{
    font-size: 1.3em !important;
    margin-right: 12px !important;
}}

[data-testid="stSidebar"] .stButton > button:hover {{
    background: #55555522 !important;
    border-color: transparent !important;
    color: {T['text_main']} !important;
}}

.stButton > button:hover {{
    background: {T['accent']}11 !important;
    border-color: {T['accent_hover']} !important;
}}

.stButton > button:active, .stButton > button:focus {{
    background: {T['accent']}22 !important;
    border-color: {T['accent']} !important;
    transform: scale(0.97) !important;
}}

.btn-logout-sidebar > button {{
    border: 1px solid #555555 !important;
    border-radius: 18px !important;
    font-size: 0.7em !important;
    padding: 2px 10px !important;
    height: 28px !important;
    background: #2A2A2A55 !important;
    color: #FFFFFF !important;
}}

/* ── Bouton Retour ── */
@keyframes back-ripple {{
    0%   {{ box-shadow: 0 0 0 0px {T['accent']}55; }}
    100% {{ box-shadow: 0 0 0 14px {T['accent']}00; }}
}}
.btn-back > button {{
    background: #000000 !important;
    color: #FFFFFF !important;
    border: 1px solid #2A2A2A !important;
    border-radius: 10px !important;
    font-size: 0.82em !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    transition: color 0.2s ease !important;
}}
.btn-back > button:hover {{
    background: #111111 !important;
    border-color: #444444 !important;
    color: #FFFFFF !important;
}}
.btn-back > button:active {{
    background: #000000 !important;
    animation: back-ripple 0.5s ease-out forwards !important;
    border-color: {T['accent']}88 !important;
    transform: scale(0.97) !important;
}}

.stButton > button:disabled {{
    background: {T['border']} !important;
    border-color: {T['border']} !important;
    color: {T['text_muted']} !important;
    transform: none !important;
    box-shadow: none !important;
}}

.stTextInput input, .stTextArea textarea {{
    background: {T['bg_input']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 8px !important;
    color: {T['text_main']} !important;
    font-family: 'DM Sans', sans-serif !important;
}}

.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {T['border_focus']} !important;
    box-shadow: 0 0 0 2px {T['accent']}33 !important;
}}

/* Style du Chat Input (Noir) */
[data-testid="stChatInput"] {{
    background-color: {T['bg_main']} !important;
    border-top: 1px solid {T['border']} !important;
}}

[data-testid="stChatInput"] textarea {{
    background-color: {T['bg_card']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 26px !important;
    color: {T['text_main']} !important;
    -webkit-text-fill-color: {T['text_main']} !important;
}}

[data-testid="stChatInput"] textarea::placeholder {{
    color: {T['text_muted']} !important;
    opacity: 1 !important;
}}

[data-testid="stChatInput"] button {{
    background-color: transparent !important;
    color: {T['accent']} !important;
}}

/* Forcer le fond sombre sur le conteneur du bas */
[data-testid="stBottomBlockContainer"], .stChatInputContainer {{
    background-color: {T['bg_main']} !important;
}}
    
[data-testid="stTabs"] button {{
    font-family: 'Roboto', sans-serif !important;
    font-weight: 600 !important;
    color: {T['text_muted']} !important;
    background: transparent !important;
}}

[data-testid="stTabs"] button[aria-selected="true"] {{
    color: {T['accent']} !important;
    border-bottom: 2px solid {T['accent']} !important;
}}

[data-testid="stExpander"] {{
    background-color: {T['bg_card']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 10px !important;
}}

[data-testid="stExpander"] summary {{
    background-color: {T['bg_card']} !important;
    color: {T['text_main']} !important;
    font-family: 'Roboto', sans-serif !important;
}}

[data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
    background-color: {T['bg_main']} !important;
}}

/* ── Popover : adaptatif au thème ── */
[data-testid="stPopover"] > div > button {{
    background-color: {T['bg_main']} !important;
    color: {T['text_main']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 8px !important;
}}

/* Corps du popover */
[data-testid="stPopoverBody"],
[data-testid="stPopoverBody"] > div,
[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"],
[data-testid="stPopoverBody"] [data-testid="stVerticalBlock"] > div,
[data-testid="stPopoverBody"] section {{
    background-color: {T['bg_main']} !important;
    color: {T['text_main']} !important;
}}

/* Boutons à l'intérieur du popover */
[data-testid="stPopoverBody"] button {{
    background-color: {T['bg_card']} !important;
    color: {T['text_main']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 8px !important;
}}
[data-testid="stPopoverBody"] button:hover {{
    background-color: {T['accent']} !important;
    border-color: {T['accent']} !important;
}}
[data-testid="stPopoverBody"] button p,
[data-testid="stPopoverBody"] button span,
[data-testid="stPopoverBody"] div p {{
    color: {T['text_main']} !important;
}}
[data-testid="stPopoverBody"] hr {{
    display: none !important;
}}

[data-testid="stAlert"] {{
    background: {T['bg_card']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 10px !important;
    color: {T['text_main']} !important;
}}

[data-testid="stMetric"] {{
    background: {T['bg_card']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 10px !important;
    padding: 14px !important;
}}

[data-testid="stMetricValue"] {{
    color: {T['accent']} !important;
    font-family: 'Roboto', sans-serif !important;
    font-weight: 700 !important;
}}

[data-testid="stProgressBar"] > div > div {{
    background: {T['progress']} !important;
}}

::-webkit-scrollbar {{ width: 5px; }}
::-webkit-scrollbar-track {{ background: {T['bg_main']}; }}
::-webkit-scrollbar-thumb {{ background: {T['border']}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {T['accent']}; }}

hr {{ border-color: {T['border']} !important; }}

/* Style des radio boutons (QCM propositions) */
div[data-testid="stRadio"] label,
div[data-testid="stRadio"] label p,
div[data-testid="stRadio"] label span,
div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p {{
    color: {'#FFFFFF' if st.session_state.theme == 'dark' else '#111111'} !important;
    font-weight: 500 !important;
}}

/* === STYLE DU POPUP (MODAL) === */
div[data-testid="stDialog"], 
div[data-testid="stModal"] {{
    background-color: transparent !important;
}}

div[data-baseweb="backdrop"] {{
    background-color: {T['bg_backdrop']} !important;
    backdrop-filter: blur(12px) !important;
    -webkit-backdrop-filter: blur(12px) !important;
}}

div[role="dialog"] {{
    background-color: {T['bg_card']} !important;
    color: {T['text_main']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 12px !important;
    box-shadow: 0 10px 40px rgba(0,0,0,0.4) !important;
}}

div[data-testid="stDialog"] > div:first-child,
div[data-testid="stModal"] > div:first-child,
div[role="dialog"] {{
    background-color: {T['bg_card']} !important;
    color: {T['text_main']} !important;
    border: 1px solid {T['border']} !important;
    box-shadow: 0 10px 50px rgba(0,0,0,0.7) !important;
    border-radius: 12px !important;
}}

div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p, 
div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] li,
div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] h3,
div[role="dialog"] [data-testid="stMarkdownContainer"] * {{
    color: {T['text_main']} !important;
}}

div[data-testid="stDialog"] hr, div[role="dialog"] hr {{
    border-color: {T['border']} !important;
    opacity: 0.5 !important;
}}

/* ➔ €➔ € Composants custom ➔ €➔ € */
.card {{
    background: {T['bg_card']};
    border: 1px solid {T['border']};
    border-radius: 12px;
    padding: 20px;
    margin: 12px 0;
}}

.card-accent {{
    background: {T['bg_card']};
    border: 1px solid {T['border']};
    border-top: 3px solid {T['accent']};
    border-radius: 12px;
    padding: 28px;
    margin: 12px 0;
    box-shadow: 0 4px 15px rgba(0,0,0,0.1);
}}

.skill-pill {{
    display: inline-block;
    background: {T['accent']}22;
    color: {T['accent']};
    border: 1px solid {T['accent']}44;
    padding: 3px 12px;
    border-radius: 20px;
    font-size: 0.8em;
    margin: 3px;
    font-family: 'DM Sans', sans-serif;
}}

.section-label {{
    font-family: 'Roboto', sans-serif;
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 2px;
    color: {T['text_subtle']};
    text-transform: uppercase;
    margin: 20px 0 10px 0;
}}

.hero {{
    background: {T['bg_card']};
    border: 1px solid {T['border']};
    border-radius: 14px;
    padding: 32px 36px;
    margin-bottom: 24px;
}}

.hero-title {{
    font-family: 'Roboto', sans-serif;
    font-size: 2.2em;
    font-weight: 800;
    color: {T['text_main']};
    margin: 0 0 6px 0;
    letter-spacing: -1px;
}}

.hero-sub {{
    color: {T['accent']};
    font-size: 0.95em;
}}

.stat-card {{
    background: {T['bg_card']};
    border: 1px solid {T['border']};
    border-radius: 10px;
    padding: 18px;
    text-align: center;
}}

.stat-number {{
    font-family: 'Roboto', sans-serif;
    font-size: 1.9em;
    font-weight: 800;
    color: {T['accent']};
}}

.stat-label {{
    font-size: 0.8em;
    color: {T['text_muted']};
    margin-top: 3px;
}}

.agent-row {{
    background: {T['bg_card']};
    border-radius: 8px;
    padding: 9px 14px;
    margin: 5px 0;
    font-size: 0.87em;
    display: flex;
    align-items: center;
    gap: 8px;
}}

.quiz-card {{
    background: {T['bg_card']};
    border-left: 3px solid {T['accent']};
    border-radius: 0 10px 10px 0;
    padding: 18px 22px;
    margin: 14px 0;
}}

.quiz-ok {{
    border-left-color: {T['success']} !important;
    background: {T['success']}0D !important;
}}

.quiz-fail {{
    border-left-color: {T['error']} !important;
    background: {T['error']}0D !important;
}}

.option-correct {{
    padding: 10px 14px; margin: 5px 0;
    background: {T['success']}15;
    border: 1px solid {T['success']}55;
    border-radius: 8px;
    color: {T['success']};
    font-weight: 700; font-size: 0.9em;
}}

.option-wrong {{
    padding: 10px 14px; margin: 5px 0;
    background: {T['error']}10;
    border: 1px solid {T['error']}44;
    border-radius: 8px;
    color: {T['error']};
    font-size: 0.9em;
}}

.option-neutral {{
    padding: 10px 14px; margin: 5px 0;
    background: {T['bg_main']};
    border: 1px solid {T['border']};
    border-radius: 8px;
    color: {T['text_muted']};
    font-size: 0.9em;
}}

.explanation-box {{
    background: {T['accent']}11;
    border: 1px solid {T['accent']}33;
    border-radius: 8px;
    padding: 12px 16px;
    margin: 8px 0 18px 0;
    font-size: 0.86em;
    color: {T['text_main']};
    line-height: 1.7;
}}

.score-box {{
    background: {T['bg_card']};
    border: 1px solid {T['border']};
    border-radius: 14px;
    padding: 28px;
    text-align: center;
    margin: 20px 0;
}}

.chat-user {{
    background: {T['accent']}15;
    border: 1px solid {T['accent']}33;
    border-radius: 12px 12px 4px 12px;
    padding: 12px 16px;
    margin: 8px 0 8px 40px;
    color: {T['text_main']};
    font-size: 0.9em;
}}

.chat-bot {{
    background: {T['bg_card']};
    border: 1px solid {T['border']};
    border-radius: 12px 12px 12px 4px;
    padding: 12px 16px;
    margin: 8px 40px 8px 0;
    color: {T['text_main']};
    font-size: 0.9em;
}}

.mono {{ font-family: 'DM Mono', monospace; font-size: 0.85em; color: {T['accent']}; }}

/* Masquer le placeholder lors du clic (focus) sur le chat coach */
[data-testid="stChatInput"] textarea:focus::placeholder {{
    color: transparent !important;
    -webkit-text-fill-color: transparent !important;
}}
[data-testid="stChatInput"] textarea:focus::-webkit-input-placeholder {{
    color: transparent !important;
    -webkit-text-fill-color: transparent !important;
}}

/* Curseur bien visible (blanc en mode sombre, noir en mode clair) */
[data-testid="stChatInput"] textarea {{
    caret-color: {'#FFFFFF' if st.session_state.get('theme', 'dark') == 'dark' else '#000000'} !important;
}}
</style>
""", unsafe_allow_html=True)

# Bandeau d'avertissement en cas d'instabilité réseau
if st.session_state.get("network_error_count", 0) > 0:
    st.markdown(f"""
    <div style='background: {T["warning"]}22; border: 1px solid {T["warning"]}; 
                border-radius: 8px; padding: 10px 16px; margin-bottom: 20px;
                color: {T["text_main"]}; font-size: 0.9em; font-weight: 500;'>
        ⚠️ Connexion réseau instable. Mode hors-ligne temporaire activé. Tentative de reconnexion en cours ({st.session_state.network_error_count} échecs)...
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# FONCTION PIPELINE DE RECHERCHE
# ============================================================
def _run_search_pipeline(user_profile: str):
    """Exécute le pipeline de recherche d'emploi."""
    with st.spinner("Les agents travaillent pour vous..."):
        # Réinitialiser les filtres de source pour la nouvelle recherche
        st.session_state.pop("sel_src_list", None)
        progress = st.progress(0)

        if st.session_state.use_mock:
            progress.progress(10, text="ScraperAgent — collecte des offres...")
            time.sleep(0.5)
            raw_jobs = ScraperAgent.mock_scrape(user_profile)

            progress.progress(40, text="ExtractorAgent — extraction des compétences...")
            time.sleep(0.5)
            jobs_with_skills = ExtractorAgent.mock_extract(raw_jobs)

            progress.progress(70, text="AnalystAgent — calcul des compatibilités...")
            time.sleep(0.5)
            scored_jobs = AnalystAgent.mock_analyze(user_profile, jobs_with_skills)

            progress.progress(100, text="Terminé !")

            st.session_state.pipeline_result = {
                "user_profile": user_profile,
                "jobs_with_skills": jobs_with_skills,
                "compatibility_scores": scored_jobs,
                "best_match": scored_jobs[0] if scored_jobs else None,
            }
        else:
        
            result = run_pipeline(user_profile=user_profile)
            progress.progress(100, text="Terminé !")
            st.session_state.pipeline_result = result

        if st.session_state.get("logged_in") and st.session_state.get("user"):
            uid = st.session_state.user.get("uid")
            AuthManager.save_job_search_results(uid, st.session_state.pipeline_result)
            # Attacher les résultats au profil actif et le sauvegarder
            if st.session_state.candidate_profile:
                st.session_state.candidate_profile["saved_pipeline_result"] = st.session_state.pipeline_result
                AuthManager.save_profile(uid, st.session_state.candidate_profile)
            # Sauvegarder également dans l'historique permanent
            AuthManager.save_job_history(uid, st.session_state.pipeline_result)

        n = len(st.session_state.pipeline_result.get("compatibility_scores", []))
        st.success(f"{n} offres trouvées et analysées !")
        st.balloons()

# ============================================================
# SIDEBAR ET NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown(f"""
    <div class='sidebar-logo' style='padding: 0 10px 30px 10px; margin-top: -30px; text-align: center;'>
        <div style='font-family:Roboto,sans-serif; font-size:1.4em; font-weight:900;
                    color:{T["text_main"]}; letter-spacing: -0.5px;'>JobAgent AI</div></div>
    """, unsafe_allow_html=True)


    def nav_button(icon, label, page_name):
        is_active = st.session_state.current_page == page_name
        # Streamlit n'interprète pas le HTML dans st.button, on utilise le texte brut
        full_label = f"{icon}   {label}"
        
        if is_active:
             st.markdown(f"<style>div[data-testid='stSidebar'] .stButton button:has(p:contains('{label}')) {{ background: #55555533 !important; font-weight: 700 !important; border-radius: 10px !important; }}</style>", unsafe_allow_html=True)

        if st.button(full_label, key=f"nav_{page_name}", use_container_width=True):
            st.session_state.current_page = page_name
            st.rerun()

    # Ordre : Dashboard, Profil, Offres, Analyse, Entretien, Paramètres
    nav_button("⌘", "Dashboard", "Dashboard")
    nav_button("◎", "Mon Profil", "Profil")
    nav_button("▤", "Offres d'emploi", "Offres d'emploi")
    nav_button("⌁", "Analyse", "Analyse")
    nav_button("◌", "Préparer l'entretien", "Préparation à l'entretien")
    nav_button("⚙", "Paramètres", "Paramètres")

    # Espace réduit — profil remonté
    st.markdown("<div style='height: 5vh;'></div>", unsafe_allow_html=True)

    # Zone Utilisateur (Disposition précise Design SaaS)
    if st.session_state.candidate_profile:
        p = st.session_state.candidate_profile
        img_url = p.get("profile_image_url")
        if not img_url:
            img_url = "https://ui-avatars.com/api/?name=" + p.get("full_name", "U").replace(" ", "+") + "&background=FF6B00&color=fff"
        
        # Masquage correct de l'uploader via CSS
        st.markdown("<style>[data-testid='stSidebar'] div[data-testid='stFileUploader'] { display: none !important; }</style>", unsafe_allow_html=True)
        uploaded_img = st.file_uploader("Upload", type=["png", "jpg", "jpeg"], key="sidebar_img_upload_hidden")
        
        if uploaded_img:
            if uploaded_img.size <= 5 * 1024 * 1024:
                st.session_state.candidate_profile["profile_image_url"] = "https://via.placeholder.com/150" 
                st.success("Photo mise à jour !")
                st.rerun()

        # Layout : Avatar | Info | Logout (Mettre à niveau)
        col_prof, col_logout = st.columns([3, 2], gap="small")
        
        with col_prof:
            st.markdown(f"""
            <div class='sidebar-profile-container' style='display: flex; align-items: center; gap: 8px; margin-top: 10px;'>
                <img src='{img_url}' id='profile-pic-sidebar' 
                     style='width: 38px; height: 38px; border-radius: 50%; object-fit: cover; cursor: pointer; border: 1px solid #444;' 
                     title='Double-cliquez pour changer de photo'/>
                <div class='sidebar-profile-info' style='overflow: hidden; white-space: nowrap; text-overflow: ellipsis; line-height: 1.1;'>
                    <div style='font-size: 0.85em; font-weight: 700; color: {T["text_main"]};'>{p.get("full_name", "Candidat").split()[0]}...</div>
                    <div style='font-size: 0.7em; color: {T["text_muted"]};'>Free</div>
                </div>
            </div>
            
            <script>
            setTimeout(() => {{
                const profilePic = window.parent.document.getElementById('profile-pic-sidebar');
                if (profilePic) {{
                    profilePic.addEventListener('dblclick', function() {{
                        const uploader = window.parent.document.querySelector('input[type="file"]');
                        if (uploader) uploader.click();
                    }});
                }}
            }}, 1000);
            </script>
            """, unsafe_allow_html=True)
        
        with col_logout:
            # Utilisation d'un popover simple (juste la flèche)
            with st.popover(" ", use_container_width=True):
                if st.button("Déconnexion ↥", key="btn_logout_final", use_container_width=True):
                    st.session_state.logged_in = False
                    st.session_state.user = None
                    st.session_state.candidate_profile = None
                    st.query_params["no_restore"] = "1"
                    st.markdown("""
                    <script>
                    try {
                        localStorage.removeItem('jobagent_session');
                    } catch(e) {}
                    </script>
                    """, unsafe_allow_html=True)
                    st.rerun()

                st.markdown("""
                <div style='
                    font-size: 0.72em;
                    font-weight: 700;
                    letter-spacing: 1px;
                    text-transform: uppercase;
                    color: #555555;
                    margin: 12px 0 6px;
                '>Basculer vers</div>
                """, unsafe_allow_html=True)
                
                if st.session_state.get("logged_in") and st.session_state.get("user"):
                    uid = st.session_state.user.get("uid")
                    saved_profiles = AuthManager.get_saved_profiles(uid)
                    
                    if not saved_profiles:
                        st.markdown("<div style='font-size: 0.7em; color: #888; font-style: italic;'>Aucun profil sauvegardé</div>", unsafe_allow_html=True)
                    else:
                        current_active_title = st.session_state.candidate_profile.get("job_title") if st.session_state.get("candidate_profile") else None
                        seen_titles = set()
                        unique_profiles = []
                        for sp in saved_profiles:
                            title = sp.get("job_title", "Profil sans titre")
                            # Ignorer le profil actuellement actif pour ne pas le proposer dans "Basculer vers"
                            if title not in seen_titles and title != current_active_title:
                                seen_titles.add(title)
                                unique_profiles.append(sp)

                        if not unique_profiles:
                            st.markdown("<div style='font-size: 0.7em; color: #888; font-style: italic;'>Aucun autre profil sauvegardé</div>", unsafe_allow_html=True)
                        else:
                            for i, sp in enumerate(unique_profiles):
                                sp_title = sp.get("job_title", "Profil sans titre")
                                if st.button(f"\U0001f4c4 {sp_title}", key=f"switch_p_{sp.get('id', 'unk')}_{i}", use_container_width=True):
                                    from auth.firebase_config import db

                                    # 1. Sauvegarder le profil ACTUEL + ses offres avant de switcher
                                    current_p = st.session_state.candidate_profile
                                    if current_p:
                                        cur_id = current_p.get("id")
                                        if not cur_id:
                                            cur_id = current_p.get("job_title", "Profil").replace("/", "-") + "_" + datetime.now().strftime("%Y%m%d%H%M%S")
                                            current_p["id"] = cur_id
                                        # Attacher les offres actuelles au profil avant sauvegarde
                                        if st.session_state.get("pipeline_result"):
                                            current_p["saved_pipeline_result"] = st.session_state.pipeline_result
                                        db.collection("users").document(uid).collection("saved_profiles").document(cur_id).set(current_p)

                                    # 2. Charger le nouveau profil
                                    st.session_state.candidate_profile = sp
                                    st.session_state.user_profile_text = sp.get("summary", "")
                                    st.session_state.profile_source = sp.get("profile_source", "cv")
                                    st.session_state.cv_filename = sp.get("cv_filename", None)

                                    # Restaurer les offres liées à ce profil
                                    st.session_state.pipeline_result = sp.get("saved_pipeline_result", None)
                                    st.session_state.selected_job = None

                                    # Réinitialiser le chat et le quiz (données spécifiques à l'ancien profil)
                                    st.session_state.current_chat = None
                                    st.session_state.chats = []
                                    st.session_state.chat_history = {}
                                    st.session_state.quiz_questions = []
                                    st.session_state.quiz_answers = {}
                                    st.session_state.quiz_submitted = False
                                    st.session_state.quiz_current_index = 0
                                    st.session_state.prep_view = "quiz"

                                    # 3. Mettre à jour le profil actif dans Firebase
                                    AuthManager.save_profile(uid, sp)

                                    # Charger l'historique de chat du nouveau profil
                                    history = AuthManager.load_chat_history(uid)
                                    if isinstance(history, dict) and history:
                                        st.session_state.chat_history = history
                                        st.session_state.chats = history.get("chats_list", [])

                                    # 4. Supprimer le nouveau profil des "sauvegardés" (il devient l'actif)
                                    for duplicate_sp in saved_profiles:
                                        if duplicate_sp.get("job_title") == sp_title and "id" in duplicate_sp:
                                            db.collection("users").document(uid).collection("saved_profiles").document(duplicate_sp['id']).delete()

                                    st.rerun()
                




    st.markdown(f"""
    <div style='text-align:center; color:{T["text_subtle"]}; font-size:0.65em; margin-top: 5px;'>
        Mainto Studio &copy; 2026
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# AFFICHAGE DE LA PAGE COURANTE
# ============================================================
page = st.session_state.current_page


if page == "Dashboard":
    user_name = st.session_state.user.get("full_name", "") if st.session_state.get("user") else ""
    welcome_msg = f"Bon retour, {user_name} !" if user_name else "Bon retour !"
    st.markdown(f"""
    <div class='hero'>
        <div style='font-size: 0.85em; font-weight: 700; color: {T["accent"]}; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 6px;'>{welcome_msg}</div>
        <h1 class='hero-title'>JobAgent AI</h1>
        <p class='hero-sub'>
            Système multi-agents de recherche d'emploi personnalisé &nbsp;·&nbsp; Cameroun
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.pipeline_result:
        jobs = st.session_state.pipeline_result.get("compatibility_scores", [])
        if jobs:
            high = sum(1 for j in jobs if j.get("score", 0) >= 75)
            avg = int(sum(j.get("score", 0) for j in jobs) / len(jobs)) if jobs else 0
            min_score = min([j.get("score", 0) for j in jobs]) if jobs else 0
            
            st.markdown("### Statistiques des Offres")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(f"<div class='stat-card'><div class='stat-number'>{len(jobs)}</div><div class='stat-label'>Offres totales</div></div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div class='stat-card'><div class='stat-number'>{high}</div><div class='stat-label'>Très compatibles</div></div>", unsafe_allow_html=True)
            with c3: st.markdown(f"<div class='stat-card'><div class='stat-number'>{avg}%</div><div class='stat-label'>Score moyen</div></div>", unsafe_allow_html=True)
            with c4: st.markdown(f"<div class='stat-card'><div class='stat-number'>{min_score}%</div><div class='stat-label'>Score minimum</div></div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            c5, c6 = st.columns(2)
            sources = {}
            for j in jobs: 
                sources[j.get("source", "N/A")] = sources.get(j.get("source", "N/A"), 0) + 1
            with c5: st.markdown(f"<div class='stat-card'><div class='stat-number'>{len(sources.keys())}</div><div class='stat-label'>Nombre de Sources</div></div>", unsafe_allow_html=True)
            with c6:
                src_txt = "<br>".join([f"<b>{k}</b>: {v}" for k,v in sources.items()])
                st.markdown(f"<div class='stat-card'><div class='stat-label'>Répartition</div><div style='font-size:0.85em;color:{T['text_main']}'>{src_txt}</div></div>", unsafe_allow_html=True)
    else:
        st.info("Lancez d'abord la recherche depuis votre Profil pour voir les statistiques.")

    # --- SECTION SITES REJETÉS ---
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.markdown('### 🚫 Sites Rejetés')
    
    if st.session_state.get("rejected_sites"):
        sorted_sites = sorted(
            st.session_state.rejected_sites.items(),
            key=lambda x: x[1]["rejected_count"],
            reverse=True
        )
        rows = ""
        for site, info in sorted_sites:
            main_reason = max(info["reasons"], key=info["reasons"].get) if info.get("reasons") else "—"
            count = info.get("rejected_count", 0)
            last  = info.get("last_rejected", "—")
            rows += (
                "<tr style='border-bottom:1px solid " + T["border"] + "44;'>"
                "<td style='padding:10px;font-weight:600;color:" + T["text_main"] + ";'>" + str(site) + "</td>"
                "<td style='padding:10px;font-weight:700;color:" + T["error"] + ";'>" + str(count) + "</td>"
                "<td style='padding:10px;color:" + T["text_muted"] + ";'>" + str(main_reason) + "</td>"
                "<td style='padding:10px;color:" + T["text_subtle"] + ";font-size:0.85em;'>" + str(last) + "</td>"
                "</tr>"
            )
        table_html = (
            "<div style='background:" + T["bg_card"] + ";border:1px solid " + T["border"] + ";"
            "border-radius:12px;overflow:hidden;margin-top:10px;'>"
            "<table style='width:100%;border-collapse:collapse;font-family:Roboto,sans-serif;font-size:0.85em;'>"
            "<thead><tr style='background:" + T["bg_main"] + ";border-bottom:1px solid " + T["border"] + ";text-align:left;'>"
            "<th style='padding:10px 12px;color:" + T["text_muted"] + ";font-size:0.72em;text-transform:uppercase;letter-spacing:1px;'>Site</th>"
            "<th style='padding:10px 12px;color:" + T["text_muted"] + ";font-size:0.72em;text-transform:uppercase;letter-spacing:1px;'>Rejets</th>"
            "<th style='padding:10px 12px;color:" + T["text_muted"] + ";font-size:0.72em;text-transform:uppercase;letter-spacing:1px;'>Raison principale</th>"
            "<th style='padding:10px 12px;color:" + T["text_muted"] + ";font-size:0.72em;text-transform:uppercase;letter-spacing:1px;'>Dernier rejet</th>"
            "</tr></thead>"
            "<tbody>" + rows + "</tbody>"
            "</table></div>"
        )
        st.markdown(table_html, unsafe_allow_html=True)
    else:
        st.markdown(
            "<div style='color:" + T["text_muted"] + ";font-style:italic;font-size:0.85em;margin-top:10px;'>"
            "Aucune offre n'a été rejetée lors des dernières collectes.</div>",
            unsafe_allow_html=True
        )


    # --- SECTION HISTORIQUE ---
    st.markdown("<br><hr>", unsafe_allow_html=True)
    st.markdown('### Historique des Collectes')
    
    if st.session_state.get("logged_in") and st.session_state.get("user"):
        uid = st.session_state.user.get("uid")
        # On pourrait mettre en cache l'historique dans st.session_state.job_history
        # mais pour la fraîcheur, on récupère les 10 dernières
        history = AuthManager.get_job_history(uid, limit=10)
        
        if history:
            for entry in history:
                try:
                    dt_obj = datetime.fromisoformat(entry["date"])
                    dt_str = dt_obj.strftime("%d/%m/%Y à %H:%M")
                except Exception:
                    dt_str = entry["date"]
                
                query_prev = entry.get("query", "Recherche")
                count = entry.get("job_count", 0)
                
                h_col1, h_col2 = st.columns([4, 1])
                with h_col1:
                    st.markdown(f"""
                    <div class='card' style='margin:0; padding:12px 18px; border-left:4px solid {T["accent"]}33;'>
                        <div style='font-family:Roboto,sans-serif; font-weight:700; font-size:0.95em;'>{dt_str}</div>
                        <div style='font-size:0.82em; color:{T["text_muted"]}; margin-top:3px;'>
                            Profil : {query_prev[:120]}...
                        </div>
                        <div style='font-size:0.75em; color:{T["accent"]}; font-weight:600; margin-top:5px;'>
                            {count} offres trouvées
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                with h_col2:
                    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                    if st.button("Charger", key=f"btn_hist_{entry['id']}", use_container_width=True):
                        st.session_state.pipeline_result = entry["pipeline_result"]
                        # On met aussi à jour le profil texte pour le coach
                        if "user_profile" in entry["pipeline_result"]:
                            st.session_state.user_profile_text = entry["pipeline_result"]["user_profile"]
                        
                        st.success("Recherche chargée depuis l'historique !")
                        time.sleep(0.5)
                        st.session_state.current_page = "Offres d'emploi"
                        st.rerun()
        else:
            st.markdown(f"<div style='color:{T['text_muted']}; font-style:italic;'>Aucune collecte enregistrée.</div>", unsafe_allow_html=True)
    else:
        st.warning("Connectez-vous pour enregistrer et consulter votre historique de collectes.")

elif page == "Profil":
    st.markdown("<h1>Mon profil</h1>", unsafe_allow_html=True)

    # ---- Notification temporaire CV chargé ----
    if st.session_state.get("cv_just_loaded"):
        st.session_state.cv_just_loaded = False
        src_label = f"CV : {st.session_state.cv_filename}" if st.session_state.profile_source == "cv" \
                    else "Profil saisi manuellement"
        st.markdown(f"""
        <style>
        @keyframes fadeOut {{
            0%   {{ opacity: 1; transform: translateY(0); }}
            80%  {{ opacity: 1; }}
            100% {{ opacity: 0; transform: translateY(-8px); }}
        }}
        #cv-success-toast {{
            background: linear-gradient(135deg, #1a472a, #2d6a4f);
            border: 1px solid #52b788;
            border-left: 4px solid #52b788;
            color: #d8f3dc;
            padding: 14px 20px;
            border-radius: 10px;
            font-size: 0.95em;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 16px;
            box-shadow: 0 4px 20px rgba(82, 183, 136, 0.2);
            animation: fadeOut 0.8s ease-out 4.2s forwards;
        }}
        </style>
        <div id="cv-success-toast">
            <span style="font-size:1.3em;">&#10003;</span>
            <span>CV chargé avec succès &mdash; <em style="font-weight:400;">{src_label}</em></span>
        </div>
        <script>
        setTimeout(() => {{
            const toast = window.parent.document.getElementById('cv-success-toast');
            if (toast) toast.remove();
        }}, 5000);
        </script>
        """, unsafe_allow_html=True)
    if st.session_state.candidate_profile:
        p = st.session_state.candidate_profile
        
        unique_skills = []
        seen_skills = set()
        for s in p.get("hard_skills", []) + p.get("tools", []):
            sl = s.strip().lower()
            if sl and sl not in seen_skills:
                seen_skills.add(sl)
                unique_skills.append(s.strip())
                
        skills_pills = "".join(
            f"<span class='skill-pill'>{s}</span>"
            for s in unique_skills[:30]
        )
        
        unique_langs = []
        seen_langs = set()
        for l in p.get("languages", []):
            ll = l.strip().lower()
            if ll and ll not in seen_langs:
                seen_langs.add(ll)
                unique_langs.append(l.strip())
                
        lang_pills = "".join(
            f"<span class='skill-pill'>{l}</span>"
            for l in unique_langs
        )
        
        # Génération HTML pour les expériences professionnelles
        exp_html = ""
        experiences = [e for e in (p.get("experiences") or []) if e.get("title") or e.get("company")]
        if experiences:
            exp_html = f"""
<div style='margin-top:15px;'>
<div style='color:{T["text_subtle"]}; font-size:0.75em; font-weight:700; letter-spacing:1px; text-transform:uppercase; margin-bottom:8px;'>Expérience professionnelle</div>
"""
            for exp in experiences:
                tech_pills = "".join([f"<span style='font-size: 0.7em; background: {T['border']}22; color: {T['text_muted']}; padding: 2px 8px; border-radius: 4px; margin-right: 4px; border: 1px solid {T['border']}44;'>{t}</span>" for t in exp.get("technologies", [])])
                exp_html += f"""
<div style='margin-bottom:18px; border-left: 2px solid {T["border"]}33; padding-left: 15px; position: relative;'>
<div style='font-weight:700; font-size:1em; color:{T["text_main"]}; margin-bottom: 2px;'>{exp.get("title", "Poste non spécifié")}</div>
<div style='font-size:0.85em; color:{T["accent"]}; font-weight: 500;'>{exp.get("company", "Entreprise non spécifiée")}</div>
<div style='font-size:0.75em; color:{T["text_muted"]}; margin-bottom: 6px; font-style: italic;'>{exp.get("period", "")}</div>
<div style='font-size:0.85em; color:{T["text_main"]}; opacity: 0.9; margin-bottom: 8px; line-height:1.5;'>{exp.get("description", "")}</div>
<div style='display: flex; flex-wrap: wrap; gap: 4px;'>{tech_pills}</div>
</div>
"""
            exp_html += "</div>"

        st.markdown(f"""
<div class='card-accent' style='min-height: fit-content;'>
<div style='font-family:Roboto,sans-serif; font-size:1.4em; font-weight:800; color:{T["text_main"]};'>
{p.get("full_name","N/A")}
</div>
<div style='color:{T["accent"]}; margin-top:4px;'>
{p.get("job_title","N/A")}
</div>
<div style='color:{T["text_muted"]}; font-size:0.85em; margin-top:6px;'>
{p.get("location","N/A")} &nbsp;·&nbsp; {p.get("education_level","N/A")} &nbsp;·&nbsp; {p.get("experience_years",0)} ans
</div>
<div style='color:{T["text_muted"]}; font-size:0.88em; margin:12px 0 8px; border-left:2px solid {T["accent"]}; padding-left:10px; font-style:italic;'>
{p.get("summary","")}
</div>
<div style='margin-top:10px;'>
<div style='color:{T["text_subtle"]}; font-size:0.75em; font-weight:700; letter-spacing:1px; text-transform:uppercase; margin-bottom:6px;'>Competences</div>
{skills_pills or f"<span style='color:{T['text_muted']};font-size:0.85em;'>Non precisees</span>"}
</div>
{exp_html}
<div style='margin-top:10px;'>
<div style='color:{T["text_subtle"]}; font-size:0.75em; font-weight:700; letter-spacing:1px; text-transform:uppercase; margin-bottom:6px;'>Langues</div>
{lang_pills or f"<span style='color:{T['text_muted']};font-size:0.85em;'>Non precisees</span>"}
</div>
</div>
""", unsafe_allow_html=True)
        st.markdown("")
        col_act1, col_act2 = st.columns([1, 1])
        with col_act1:
            if st.button("Lancer la recherche d emploi", type="primary", use_container_width=True):
                _run_search_pipeline(st.session_state.user_profile_text)
        with col_act2:
            if st.session_state.pipeline_result:
                if st.button("Voir les offres", use_container_width=True):
                    st.session_state.current_page = "Offres d'emploi"
                    st.session_state.previous_page = "Profil"
                    st.rerun()
    else:
        mode = st.radio(
            "Comment renseigner votre profil ?",
            options=["Uploader mon CV (PDF ou DOCX)", "Saisir ma description manuellement"],
            horizontal=True,
        )
        st.markdown("")
        if mode.startswith("Upload"):
            st.markdown("#### Importez votre CV")
            uploaded_file = st.file_uploader(
                "Glissez votre CV ici",
                type=["pdf", "docx", "doc"],
                help="PDF, DOCX, DOC — max 5 Mo"
            )
            if uploaded_file:
                if uploaded_file.size > 5 * 1024 * 1024:
                    st.error("Le fichier dépasse la limite autorisée de 5 Mo.")
                else:
                    col_i, col_b = st.columns([3, 1])
                    with col_i:
                        st.markdown(f"""
                        <div class='card' style='padding:12px; color:{T["accent"]}; font-size:0.9em;'>
                            {uploaded_file.name}
                            <span style='color:{T["text_muted"]};'>
                                ({round(uploaded_file.size/1024,1)} Ko)
                            </span>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_b:
                        if st.button("Analyser", type="primary", use_container_width=True):
                            with st.spinner("Analyse du CV en cours..."):
                                file_bytes = uploaded_file.read()
                                if st.session_state.use_mock:
                                    time.sleep(1)
                                    profile = CVParser.mock_parse(uploaded_file.name)
                                else:
                                    profile = CVParser().parse(file_bytes, uploaded_file.name)
                                st.session_state.candidate_profile = profile or {}
                                st.session_state.profile_source    = "cv"
                                st.session_state.cv_filename       = uploaded_file.name
                                st.session_state.user_profile_text = profile.get("profile_text", "")
                                st.session_state.cv_just_loaded    = True
                            # ── Sauvegarder dans Firestore ──
                            if st.session_state.get("logged_in") and st.session_state.get("user"):
                                uid = st.session_state.user.get("uid")
                                profile_to_save = {
                                    **profile,
                                    "profile_source": "cv",
                                    "cv_filename": uploaded_file.name,
                                }
                                AuthManager.save_profile(uid, profile_to_save)
                            st.rerun()
            else:
                st.markdown(f"""
                <div style='border:2px dashed {T["border"]}; border-radius:12px;
                            padding:48px; text-align:center; background:{T["bg_card"]};'>
                    <div style='color:{T["text_muted"]}; font-size:1em;'>
                        Deposez votre CV ici
                    </div>
                    <div style='color:{T["text_subtle"]}; font-size:0.82em; margin-top:6px;'>
                        PDF Â· DOCX Â· DOC
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("#### Decrivez votre profil")
            col_form, col_tips = st.columns([2, 1])
            with col_form:
                user_text = st.text_area(
                    "Votre profil",
                    height=220,
                    placeholder=(
                        "Exemple :\n"
                        "Je suis ingenieur Data Science avec 2 ans d experience.\n"
                        "Competences : Python, ML, SQL, Power BI.\n"
                        "Je cherche un poste a Yaounde ou Douala."
                    )
                )
                if st.button("Utiliser ce profil", type="primary",
                             disabled=not (user_text or "").strip()):
                    with st.spinner("Analyse du profil en cours..."):
                        if st.session_state.use_mock:
                            import time
                            time.sleep(1)
                            profile = CVParser.mock_parse("Saisie manuelle")
                        else:
                            try:
                                profile = CVParser().parse_text(user_text)
                            except Exception as e:
                                st.error(f"Erreur lors de l'analyse : {e}")
                                profile = None

                    if profile:
                        st.session_state.candidate_profile = profile
                        st.session_state.profile_source    = "text"
                        st.session_state.user_profile_text = profile.get("profile_text", user_text)
                        st.session_state.cv_just_loaded    = True  # Flag notification
                        
                        # Sauvegarder dans Firestore
                        if st.session_state.get("logged_in") and st.session_state.get("user"):
                            uid = st.session_state.user.get("uid")
                            profile_to_save = {
                                **profile,
                                "profile_source": "text",
                                "cv_filename":    None,
                            }
                            AuthManager.save_profile(uid, profile_to_save)
                            
                        st.rerun()

            with col_tips:
                st.markdown(f"""<div class='card'>
                    <div style='font-family:Roboto,sans-serif; font-weight:700;
                                color:{T["accent"]}; margin-bottom:12px;'>Conseils</div>
                    <div style='color:{T["text_main"]}; font-size:0.85em; line-height:1.9;'>
                        Mentionnez vos competences techniques<br>
                        Precisez vos annees d experience<br>
                        Indiquez votre secteur cible<br>
                        Specifiez votre localisation<br>
                        Ajoutez vos certifications
                    </div>
                </div>
                """, unsafe_allow_html=True)

elif page == "Offres d'emploi":
    st.markdown("<h1>Offres d'emploi collectées</h1>", unsafe_allow_html=True)

    if not st.session_state.pipeline_result:
        st.markdown(f"""
        <div style='background:{T["bg_card"]}; border:1px dashed {T["border"]};
                    border-radius:14px; padding:48px; text-align:center;'>
            <div style='color:{T["accent"]}; font-family:Roboto,sans-serif;
                        font-size:1.1em; margin-top:10px;'>Aucune recherche lancée</div>
            <div style='color:{T["text_muted"]}; font-size:0.9em; margin-top:8px;'>
                Renseignez votre profil dans l'onglet Mon Profil et lancez la recherche.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        jobs = st.session_state.pipeline_result.get("compatibility_scores", [])

        if jobs:
            # Filtres
            st.markdown("<br>", unsafe_allow_html=True)
            col_f1, col_f2 = st.columns(2)

            with col_f1:
                st.markdown(f"""
                    <div style='color:{T["text_main"]}; font-weight:700; font-size:1.05em; 
                                letter-spacing:0.5px; margin-bottom:2px;'>
                        Score minimum
                    </div>
                    <div style='color:{T["text_muted"]}; font-size:0.82em; margin-bottom:10px; font-style:italic;'>
                        Faites glisser pour filtrer les offres
                    </div>
                """, unsafe_allow_html=True)
                min_score = st.slider("Score minimum", 0, 100, 0, 5, label_visibility="collapsed")

            with col_f2:
                st.markdown(f"""
                    <div style='color:{T["text_main"]}; font-weight:700; font-size:1.05em; 
                                letter-spacing:0.5px; margin-bottom:2px;'>
                        Filtrer par Source
                    </div>
                    <div style='color:{T["text_muted"]}; font-size:0.82em; margin-bottom:10px; font-style:italic;'>
                        Toutes les sources restent visibles ici
                    </div>
                """, unsafe_allow_html=True)
                
                all_sources = sorted(list(set(j.get("source", "N/A") for j in jobs)))
                
                # Initialisation de l'état des sources dans la session
                if "sel_src_list" not in st.session_state:
                    st.session_state.sel_src_list = all_sources
                
                # --- Libellé dynamique du filtre ---
                selected = st.session_state.sel_src_list
                if not selected:
                    label_filter = "Filtrer par source..."
                else:
                    label_filter = ", ".join(selected)
                    # On limite la longueur du texte affiché sur le bouton pour l'esthétique
                    if len(label_filter) > 40:
                        label_filter = label_filter[:37] + "..."

                with st.popover(label_filter, use_container_width=True):
                    new_selection = []
                    for src in all_sources:
                        is_checked = src in st.session_state.sel_src_list
                        if st.checkbox(src, value=is_checked, key=f"chk_src_{src}"):
                            new_selection.append(src)
                    
                    # Mise à jour si la sélection change
                    if sorted(new_selection) != sorted(st.session_state.sel_src_list):
                        st.session_state.sel_src_list = new_selection
                        st.rerun()
                
                sel_src = st.session_state.sel_src_list

            # Logique de filtrage améliorée
            filtered = [j for j in jobs
                        if j.get("score", 0) >= min_score
                        and (not sel_src or j.get("source", "N/A") in sel_src)]

            st.markdown(f"<div style='color:{T['text_muted']}; font-size:0.85em; margin:8px 0;'>"
                        f"{len(filtered)} offre(s) affichée(s)</div>", unsafe_allow_html=True)

            for i, job in enumerate(filtered):
                score = job.get("score", 0)
                color = T["success"] if score >= 75 else T["warning"] if score >= 50 else T["error"]

                skills = job.get("skills", {})
                all_sk = skills.get("hard_skills", []) + skills.get("tools", [])
                pills = "".join(f"<span class='skill-pill'>{s}</span>" for s in all_sk[:6])

                with st.expander(f"{job['title']} — {job['company']}  |  {score}%",
                                 expanded=(i == 0)):
                    col_info, col_score = st.columns([3, 1])

                    with col_info:
                        st.markdown(f"""
                        <div style='color:{T["text_muted"]}; font-size:0.85em; margin-bottom:8px;'>
                            {job.get("location", "N/A")} &nbsp;·&nbsp; {job.get("source", "N/A")}
                        </div>
                        <div style='color:{T["text_main"]}; font-size:0.9em;
                                    line-height:1.7; margin-bottom:12px;'>
                            {job.get("description", "")[:350]}...
                        </div>
                        <div>{pills}</div>
                        <a href='{job.get("url", "#")}' target='_blank'
                           style='color:{T["accent"]}; font-size:0.85em;
                                  text-decoration:none; display:block; margin-top:10px;'>
                            Voir l'offre complète
                        </a>
                        """, unsafe_allow_html=True)

                    with col_score:
                        st.markdown(f"""
                        <div style='text-align:center; background:{T["bg_main"]};
                                    border-radius:10px; padding:18px;
                                    border:1px solid {T["border"]};'>
                            <div style='font-family:Roboto,sans-serif; font-size:1.8em;
                                        font-weight:800; color:{color};'>{score}%</div>
                            <div style='color:{T["text_muted"]}; font-size:0.78em;
                                        margin-top:4px;'>Compatibilité</div>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("Voir l'analyse détaillée", key=f"analysis_{i}", use_container_width=True):
                            st.session_state.selected_job = job
                            show_job_analysis(job)

                        if st.button("Se préparer", key=f"sel_{i}", use_container_width=True):
                            st.session_state.selected_job = job
                            st.session_state.previous_page = "Offres d'emploi"
                            st.session_state.current_page = "Préparation à l'entretien"
                            st.rerun()

# ============================================================
# TAB 3 — ANALYSE
# ============================================================
elif page == "Analyse":
    if st.session_state.previous_page:
        col_b, _ = st.columns([1, 15])
        with col_b:
            st.markdown("<div class='btn-back'>", unsafe_allow_html=True)
            if st.button("←", key="back_analyse_top"):
                st.session_state.current_page = st.session_state.previous_page
                st.session_state.previous_page = None
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<h1>Analyse de compatibilité</h1>", unsafe_allow_html=True)

    if not st.session_state.pipeline_result:
        st.info("Lancez d'abord la recherche depuis Mon Profil.")
    else:
        jobs = st.session_state.pipeline_result.get("compatibility_scores", [])
        best = st.session_state.pipeline_result.get("best_match")

        if best:
            st.markdown(f"""
            <div class='card-accent'>
                <div style='color:{T["text_muted"]}; font-size:0.75em; font-weight:700;
                            letter-spacing:2px; text-transform:uppercase;
                            margin-bottom:6px;'>Meilleure correspondance</div>
                <div style='font-family:Roboto,sans-serif; font-size:1.3em;
                            font-weight:800; color:{T["text_main"]};'>
                    {best["title"]} — {best["company"]}
                </div>
                <div style='color:{T["text_muted"]}; font-size:0.85em; margin-top:5px;'>
                    {best.get("location", "N/A")}
                </div>
                <div style='font-family:Roboto,sans-serif; font-size:2em;
                            font-weight:800; color:{T["accent"]}; margin-top:10px;'>
                    {best.get("score", 0)}%
                    <span style='font-size:0.4em; color:{T["text_muted"]};'>
                        de compatibilité
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### Classement des offres")

        for job in jobs:
            score = job.get("score", 0)
            color = T["success"] if score >= 75 else T["warning"] if score >= 50 else T["error"]

            col_t, col_b = st.columns([3, 1])

            with col_t:
                st.markdown(f"**{job['title']}** — {job['company']}")
                st.progress(score / 100)

            with col_b:
                st.markdown(
                    f"<div style='text-align:right; color:{color}; font-weight:700;"
                    f"font-family:Roboto,sans-serif; font-size:1.2em;'>{score}%</div>",
                    unsafe_allow_html=True
                )

            matching = job.get("matching_skills", [])
            missing = job.get("missing_skills", [])

            if matching or missing:
                with st.expander("Voir le détail"):
                    c1, c2 = st.columns(2)

                    with c1:
                        st.markdown("**Compétences correspondantes**")
                        for s in matching:
                            st.markdown(f"<span class='skill-pill'>{s}</span>",
                                        unsafe_allow_html=True)

                    with c2:
                        st.markdown("**Compétences manquantes**")
                        for s in missing:
                            st.markdown(
                                f"<span style='display:inline-block; background:{T['error']}15;"
                                f"color:{T['error']}; border:1px solid {T['error']}44;"
                                f"padding:3px 12px; border-radius:20px; font-size:0.8em;"
                                f"margin:3px;'>{s}</span>",
                                unsafe_allow_html=True
                            )

                    for r in job.get("recommendations", []):
                        st.markdown(f"  {r}")

            st.markdown("<hr>", unsafe_allow_html=True)



# ============================================================
# TAB 4 — COACH
# ============================================================
elif page == "Préparation à l'entretien":
    is_chat_active = st.session_state.prep_view == "coach" and st.session_state.get("current_chat")

    if not is_chat_active:
        col_b, _ = st.columns([1, 15])
        with col_b:
            st.markdown("<div class='btn-back'>", unsafe_allow_html=True)
            if st.button("←", key="back_prep_top"):
                if st.session_state.prep_view == "coach":
                    st.session_state.prep_view = "quiz"
                    st.rerun()
                elif st.session_state.previous_page:
                    st.session_state.edit_mode = False
                    st.session_state.current_page = st.session_state.previous_page
                    st.session_state.previous_page = None
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<h1>Préparer l'entretien d'embauche</h1>", unsafe_allow_html=True)

    if not st.session_state.selected_job:
        if not is_chat_active:
            st.markdown(f"""
            <div style='background:{T["bg_card"]}; border:1px dashed {T["border"]};
                        border-radius:14px; padding:48px; text-align:center;'>
                <div style='color:{T["accent"]}; font-family:Roboto,sans-serif; font-size:1.1em;'>
                    Aucune offre sélectionnée
                </div>
                <div style='color:{T["text_muted"]}; font-size:0.9em; margin-top:8px;'>
                    Sélectionnez une offre dans l'onglet Offres d'emploi.
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        job = st.session_state.selected_job

        if not is_chat_active:
            st.markdown(f"""
            <div class='card-accent'>
                <div style='color:{T["text_muted"]}; font-size:0.75em; font-weight:700;
                            letter-spacing:2px; text-transform:uppercase;'>Offre sélectionnée</div>
                <div style='font-family:Roboto,sans-serif; font-size:1.2em;
                            font-weight:800; color:{T["text_main"]}; margin-top:6px;'>
                    {job["title"]}
                    <span style='color:{T["text_muted"]}; font-weight:400; font-size:0.8em;'>
                        chez
                    </span>
                    {job["company"]}
                </div>
            </div>
            """, unsafe_allow_html=True)

        if st.session_state.prep_view == "quiz":
            if "quiz_current_index" not in st.session_state:
                st.session_state.quiz_current_index = 0

            if not st.session_state.quiz_questions:
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.session_state.quiz_current_index = 0

                col_btn1, col_btn2, _ = st.columns([1, 1, 1])

                with col_btn1:
                    if st.button("Générer le quiz QCM", type="primary", use_container_width=True):
                        with st.spinner("CoachAgent génère votre quiz..."):
                            if st.session_state.use_mock:
                                st.session_state.quiz_questions = \
                                    CoachAgent.mock_generate_quiz(job)
                            else:
                                coach = CoachAgent()
                                st.session_state.quiz_questions = \
                                    coach.generate_quiz(job, candidate_profile=st.session_state.candidate_profile)
                            st.session_state.quiz_current_index = 0
                            st.rerun()
                with col_btn2:
                    if st.button("Interagir avec le coach", use_container_width=True):
                        st.session_state.prep_view = "coach"
                        st.rerun()

            else:
                questions = st.session_state.quiz_questions
                submitted = st.session_state.quiz_submitted
                type_labels = {
                    "technique": "Technique",
                    "comportemental": "Comportemental",
                    "mise_en_situation": "Mise en situation",
                }

                if not submitted:
                    # ============================================================
                    # ÉCRAN DE NAVIGATION QUIZ (Non soumis)
                    # ============================================================
                    idx = st.session_state.quiz_current_index
                    nb_total = len(questions)
                    current_question_num = idx + 1
                    pct = int((current_question_num / nb_total) * 100) if nb_total > 0 else 0

                    # 1. Barre de progression moderne & stylée
                    st.markdown(f"""
                    <div style='margin-bottom: 22px; font-family: "Roboto", sans-serif;'>
                        <div style='display: flex; justify-content: space-between; font-size: 0.9em; font-weight: 700; color: {T["text_main"]}; margin-bottom: 8px;'>
                            <span>Question {current_question_num} / {nb_total}</span>
                            <span>{pct}%</span>
                        </div>
                        <div style='background: {T["border"]}44; border-radius: 10px; height: 8px; width: 100%; overflow: hidden;'>
                            <div style='background: {T["accent"]}; height: 100%; width: {pct}%; transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);'></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # 2. Question active
                    q = questions[idx]
                    qid = q.get("id", 0)
                    qtype = q.get("type", "technique")
                    label = type_labels.get(qtype, "Question")
                    options = q.get("options", {})

                    st.markdown(f"""
                    <div class='quiz-card'>
                        <span style='background:{T["accent"]}22; color:{T["accent"]};
                                     border:1px solid {T["accent"]}44; padding:2px 10px;
                                     border-radius:20px; font-size:0.75em;
                                     font-family:Roboto,sans-serif; font-weight:700;'>
                            {label}
                        </span>
                        <div style='font-family:Roboto,sans-serif; font-weight:700;
                                    color:{T["text_main"]}; font-size:1.05em;
                                    margin:12px 0 16px; line-height:1.4;'>
                            Q{qid}. {q.get("question", "")}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # 3. Propositions
                    user_ans = st.session_state.quiz_answers.get(str(qid))
                    options_keys = list(options.keys())
                    default_index = 0
                    if user_ans in options_keys:
                        default_index = options_keys.index(user_ans)

                    # Affichage des propositions sous forme de radio bouton interactif
                    choice = st.radio(
                        f"q_{qid}",
                        options=options_keys,
                        index=default_index,
                        format_func=lambda k, o=options: f"{k}.  {o[k]}",
                        key=f"radio_widget_{qid}",
                        label_visibility="collapsed"
                    )
                    # Sauvegarder immédiatement dans session_state
                    st.session_state.quiz_answers[str(qid)] = choice

                    st.markdown("<br>", unsafe_allow_html=True)

                    # 4. Boutons de navigation (Précédent / Suivant / Soumettre)
                    if idx < nb_total - 1:
                        # Questions normales
                        col_prev, col_next = st.columns([1, 1])
                        with col_prev:
                            if st.button("Précédent", use_container_width=True, disabled=(idx == 0)):
                                st.session_state.quiz_current_index -= 1
                                st.rerun()
                        with col_next:
                            if st.button("Suivant", use_container_width=True):
                                st.session_state.quiz_current_index += 1
                                st.rerun()
                    else:
                        # Dernière question : Précédent, Soumettre
                        col_prev, col_submit = st.columns([1, 1])
                        with col_prev:
                            if st.button("Précédent", use_container_width=True):
                                st.session_state.quiz_current_index -= 1
                                st.rerun()
                        with col_submit:
                            if st.button("Soumettre", type="primary", use_container_width=True):
                                st.session_state.quiz_submitted = True
                                st.rerun()

                else:
                    # ============================================================
                    # DÉDIÉ : VUE DES RÉSULTATS DU QUIZ (Soumis)
                    # ============================================================
                    correct_count = sum(
                        1 for q in questions
                        if st.session_state.quiz_answers.get(str(q["id"])) == q["correct_answer"]
                    )
                    total = len(questions)
                    pct = int(correct_count / total * 100) if total > 0 else 0
                    color = T["success"] if pct >= 80 else T["warning"] if pct >= 50 else T["error"]

                    msg = (
                        "Excellent ! Vous êtes parfaitement préparé pour cet entretien d'embauche."
                        if pct >= 80 else
                        "Bon travail ! Révisez les concepts restants pour maximiser vos chances de réussite."
                        if pct >= 50 else
                        "Continuez à vous entraîner — utilisez le coach pour progresser."
                    )

                    st.markdown("<h2>Résultats de votre Quiz QCM</h2>", unsafe_allow_html=True)

                    # Score box premium
                    st.markdown(f"""
                    <div class='score-box' style='border-top: 4px solid {color}; background: {T["bg_card"]}; padding: 30px; border-radius: 12px; text-align: center; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0,0,0,0.15);'>
                        <div style='font-size: 1.1em; font-weight: bold; color: {T["text_muted"]}; margin-bottom: 8px;'>Votre Score Final</div>
                        <div style='font-family: Roboto, sans-serif; font-size: 3.5em; font-weight: 900; color: {color}; line-height: 1;'>{correct_count} <span style='font-size: 0.5em; color: {T["text_muted"]}; font-weight: 500;'>/ {total}</span></div>
                        <div style='font-size: 1.5em; font-weight: 800; color: {color}; margin-top: 8px;'>{pct}% Réussite</div>
                        <div style='color: {T["text_main"]}; font-size: 0.95em; font-weight: 500; margin-top: 15px; border-top: 1px solid {T["border"]}55; padding-top: 15px;'>{msg}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Statistiques en colonnes
                    c_tot, c_ok, c_err = st.columns(3)
                    with c_tot:
                        st.markdown(f"""
                        <div class='stat-card'>
                            <div class='stat-number' style='color:{T["text_main"]};'>{total}</div>
                            <div class='stat-label'>Questions totales</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c_ok:
                        st.markdown(f"""
                        <div class='stat-card'>
                            <div class='stat-number' style='color:{T["success"]};'>{correct_count}</div>
                            <div class='stat-label'>Bonnes réponses</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with c_err:
                        st.markdown(f"""
                        <div class='stat-card'>
                            <div class='stat-number' style='color:{T["error"]};'>{total - correct_count}</div>
                            <div class='stat-label'>Mauvaises réponses</div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.markdown("<br>", unsafe_allow_html=True)

                    # Remettre EXACTEMENT le "Détail par question" d'avant
                    with st.expander("Détail par question"):
                        for q in questions:
                            qid = q.get("id", 0)
                            correct = q.get("correct_answer", "A")
                            answer = st.session_state.quiz_answers.get(str(qid), "-")
                            ok = answer == correct

                            st.markdown(
                                f"**Q{qid}.** {q.get('question', '')}  \n"
                                f"Votre réponse : **{answer}** "
                                f"{'(correct)' if ok else f' · Réponse attendue : **{correct}**'}"
                            )
                            if not ok:
                                explanation = q.get("explanation")
                                if not explanation:
                                    correct_text = q.get("options", {}).get(correct, "")
                                    explanation = f"La bonne réponse est {correct} : {correct_text}."
                                st.markdown(f"""
                                <div class='explanation-box' style='margin: 4px 0 12px 0; border-left: 3px solid {T["accent"]}; background: {T["accent"]}08;'>
                                    <strong>Explication de la bonne réponse :</strong> {explanation}
                                </div>
                                """, unsafe_allow_html=True)

                    # Boutons en bas du résultat
                    st.markdown("<br><hr>", unsafe_allow_html=True)
                    col_res1, col_res2 = st.columns(2)
                    with col_res1:
                        if st.button("Recommencer le quiz", key="restart_quiz_from_results", use_container_width=True):
                            st.session_state.quiz_questions = []
                            st.session_state.quiz_answers = {}
                            st.session_state.quiz_submitted = False
                            st.session_state.quiz_current_index = 0
                            st.rerun()
                    with col_res2:
                        if st.button("Interagir avec le coach 💬", key="chat_coach_from_results", type="primary", use_container_width=True):
                            st.session_state.prep_view = "coach"
                            st.rerun()

        else:
    
            import time
            if "chats" not in st.session_state:
                st.session_state["chats"] = []
            if "current_chat" not in st.session_state:
                st.session_state["current_chat"] = None
            if "show_chat_history" not in st.session_state:
                st.session_state["show_chat_history"] = False

            active_chat = st.session_state["current_chat"]

            if not active_chat:
                if not st.session_state.get("show_chat_history", False):
                    if st.button("Historique des chats", use_container_width=True):
                        st.session_state.show_chat_history = True
                        st.rerun()
                else:
                    if st.button("Masquer l'historique", use_container_width=True):
                        st.session_state.show_chat_history = False
                        st.rerun()

                if st.session_state.get("show_chat_history", False):
                    with st.expander("Vos précédentes conversations", expanded=True):
                        if not st.session_state["chats"]:
                            st.info("Aucun historique disponible")
                        else:
                            for idx, chat in enumerate(reversed(st.session_state["chats"])):
                                chat_id = chat.get("id", "Chat sans nom")
                                if st.button(f"Reprendre : {chat_id}", key=f"btn_hist_{chat_id}_{idx}", use_container_width=True):
                                    st.session_state["current_chat"] = chat
                                    st.session_state["show_chat_history"] = False
                                    st.rerun()

                st.markdown("<hr>", unsafe_allow_html=True)

                col_new, _ = st.columns([1, 1])
                with col_new:
                    if st.button("Commencer un nouvel entretien virtuel", use_container_width=True):
                        with st.spinner("Coach démarre l'entretien..."):
                            if st.session_state.use_mock:
                                welcome = f"Bonjour ! Bienvenue à votre entretien pour le poste de {job['title']}. Parlez-moi un peu de vous."
                            else:
                                welcome = CoachAgent().init_interview(job, candidate_profile=st.session_state.candidate_profile)
                                    
                            new_chat_id = f"Entretien {job['title']} - {time.strftime('%H:%M:%S')}"
                            new_chat = {
                                "id": new_chat_id,
                                "messages": [{"role": "assistant", "content": welcome}]
                            }
                            
                            st.session_state["chats"].append(new_chat)
                            st.session_state["current_chat"] = new_chat
                                
                            if st.session_state.get("logged_in") and st.session_state.get("user"):
                                uid = st.session_state.user.get("uid")
                                st.session_state.chat_history["chats_list"] = st.session_state["chats"]
                                AuthManager.save_chat_history(uid, st.session_state.chat_history)
                            st.rerun()

                st.markdown(f"<div style='background:{T['bg_card']}; border:1px dashed {T['border']}; border-radius:14px; padding:48px; text-align:center; margin-top:16px;'><div style='font-size:1.8em;'>&#128172;</div><div style='font-family:Roboto,sans-serif; font-weight:700; color:{T['text_main']}; margin-top:12px;'>Prêt pour votre entretien ?</div><div style='color:{T['text_muted']}; font-size:0.9em; margin-top:8px;'>Cliquez sur <b>Commencer un nouvel entretien virtuel</b> pour démarrer,<br>ou reprenez une conversation depuis l'historique.</div></div>", unsafe_allow_html=True)
            
            else:
                col_back, _ = st.columns([1, 6])
                with col_back:
                    if st.button("←", use_container_width=True):
                        st.session_state["current_chat"] = None
                        st.rerun()
                st.markdown("<hr style='margin-top:5px; margin-bottom:20px;'>", unsafe_allow_html=True)

                for idx, msg in enumerate(active_chat.get("messages", [])):
                    css = "chat-user" if msg["role"] == "user" else "chat-bot"
                    prefix = "Vous" if msg["role"] == "user" else "Coach"
                    st.markdown(
                        f"<div class='{css}'><strong>{prefix} :</strong> {msg['content']}</div>",
                        unsafe_allow_html=True
                    )

                if prompt := st.chat_input("Posez une question au Coach ou répondez à sa question..."):
                    active_chat["messages"].append({"role": "user", "content": prompt})

                    with st.spinner("Coach réfléchit..."):
                        if st.session_state.use_mock:
                            response = f"C'est une très bonne réponse pour {job['title']}. Avez-vous une autre question ?"
                        else:
                            response = CoachAgent().chat(
                                user_message=prompt,
                                job=job,
                                history=active_chat["messages"][:-1],
                                candidate_profile=st.session_state.candidate_profile
                            )

                        active_chat["messages"].append(
                            {"role": "assistant", "content": response}
                        )

                    st.session_state["current_chat"] = active_chat
                    for i, c in enumerate(st.session_state["chats"]):
                        if c["id"] == active_chat["id"]:
                            st.session_state["chats"][i] = active_chat
                            break

                    if st.session_state.get("logged_in") and st.session_state.get("user"):
                        uid = st.session_state.user.get("uid")
                        st.session_state.chat_history["chats_list"] = st.session_state["chats"]
                        AuthManager.save_chat_history(uid, st.session_state.chat_history)

                    st.rerun()


# ============================================================
# TAB 5 — PARAMÈTRES
# ============================================================
elif page == "Paramètres":
    col_b, _ = st.columns([1, 15])
    with col_b:
        st.markdown("<div class='btn-back'>", unsafe_allow_html=True)
        if st.button("←", key="back_param_top"):
            if st.session_state.previous_page:
                st.session_state.current_page = st.session_state.previous_page
                st.session_state.previous_page = None
            else:
                st.session_state.current_page = "Profil"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<h1>Paramètres</h1>", unsafe_allow_html=True)
    # Modifier le profil
    if st.session_state.candidate_profile:
        
        if "show_edit_profile" not in st.session_state:
            st.session_state.show_edit_profile = False

        if st.button("Modifier le profil", use_container_width=True):
            st.session_state.show_edit_profile = not st.session_state.show_edit_profile

        if st.session_state.show_edit_profile:
            st.markdown(f"""
            <div class='card-accent' style='padding-bottom: 55px; margin-bottom: -92px;'>
                <h3 style='margin-top:0; margin-bottom:0;'>Édition du profil</h3>
            </div>
            """, unsafe_allow_html=True)
            
            col_empty, col_btn = st.columns([2.5, 1])
            with col_empty:
                st.markdown("<div style='height:1px;'></div>", unsafe_allow_html=True)
            with col_btn:
                if "show_photo_upload" not in st.session_state:
                    st.session_state.show_photo_upload = False
                if st.button("Changer de photo", use_container_width=True):
                    st.session_state.show_photo_upload = not st.session_state.show_photo_upload
            
            st.markdown("<div style='margin-top: 30px;'></div>", unsafe_allow_html=True)
            
            
            if st.session_state.show_photo_upload:
                up_img = st.file_uploader("Nouvelle photo", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
                if up_img:
                    import base64
                    b64 = base64.b64encode(up_img.read()).decode()
                    mime = up_img.type
                    st.session_state.candidate_profile["profile_image_url"] = f"data:{mime};base64,{b64}"
                    
                    if st.session_state.get("logged_in") and st.session_state.get("user"):
                        uid = st.session_state.user.get("uid")
                        AuthManager.save_profile(uid, st.session_state.candidate_profile)
                    st.session_state.show_photo_upload = False
                    st.rerun()
    

            p = st.session_state.candidate_profile
            
            # 0. Nom complet
            new_name = st.text_input("Nom complet", value=p.get("full_name", ""))
            p["full_name"] = new_name
            
            # 1. Description / Summary
            new_summary = st.text_area("Ma description professionnelle", value=p.get("summary", ""), height=150)
            p["summary"] = new_summary
            
            st.markdown("<hr>", unsafe_allow_html=True)
            
            # 2. Compétences (Hard Skills)
            st.markdown("<h4>Mes Compétences</h4>", unsafe_allow_html=True)
            
            all_skills = p.get("hard_skills", [])
            if not all_skills:
                st.info("Aucune compétence renseignée.")
            else:
                cols = st.columns(3)
                for idx, skill in enumerate(all_skills):
                    with cols[idx % 3]:
                        col_p, col_b = st.columns([4, 1])
                        with col_p:
                            st.markdown(f"<span class='skill-pill'>{skill}</span>", unsafe_allow_html=True)
                        with col_b:
                            if st.button("✕", key=f"del_sk_{idx}", help=f"Supprimer {skill}"):
                                all_skills.remove(skill)
                                p["hard_skills"] = all_skills
                                st.session_state.candidate_profile = p
                                if st.session_state.get("logged_in") and st.session_state.get("user"):
                                    AuthManager.save_profile(st.session_state.user.get("uid"), p)
                                st.rerun()
    
            st.markdown("<br>", unsafe_allow_html=True)
            col_in1, col_in2 = st.columns([3, 1])
            with col_in1:
                new_skill = st.text_input("Nouvelle compétence", placeholder="ex: Docker, Marketing Digital...", key="in_new_skill", label_visibility="collapsed")
            with col_in2:
                if st.button("Ajouter", use_container_width=True):
                    if new_skill.strip():
                        if "hard_skills" not in p: p["hard_skills"] = []
                        if new_skill.strip() not in p["hard_skills"]:
                            p["hard_skills"].append(new_skill.strip())
                            st.session_state.candidate_profile = p
                            if st.session_state.get("logged_in") and st.session_state.get("user"):
                                AuthManager.save_profile(st.session_state.user.get("uid"), p)
                            st.success(f"'{new_skill}' ajouté !")
                            import time
                            time.sleep(0.5)
                            st.rerun()
                            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 3. Langues
            st.markdown("<h4>Mes Langues</h4>", unsafe_allow_html=True)
            all_langs = p.get("languages", [])
            if not all_langs:
                st.info("Aucune langue renseignée.")
            else:
                cols_l = st.columns(3)
                for idx, lang in enumerate(all_langs):
                    with cols_l[idx % 3]:
                        col_lp, col_lb = st.columns([4, 1])
                        with col_lp:
                            st.markdown(f"<span class='skill-pill'>{lang}</span>", unsafe_allow_html=True)
                        with col_lb:
                            if st.button("✕", key=f"del_lang_{idx}", help=f"Supprimer {lang}"):
                                all_langs.remove(lang)
                                p["languages"] = all_langs
                                st.session_state.candidate_profile = p
                                if st.session_state.get("logged_in") and st.session_state.get("user"):
                                    AuthManager.save_profile(st.session_state.user.get("uid"), p)
                                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            col_inl1, col_inl2 = st.columns([3, 1])
            with col_inl1:
                new_lang = st.text_input("Nouvelle langue", placeholder="ex: Anglais, Français...", key="in_new_lang", label_visibility="collapsed")
            with col_inl2:
                if st.button("Ajouter", key="btn_add_lang", use_container_width=True):
                    if new_lang.strip():
                        if "languages" not in p: p["languages"] = []
                        if new_lang.strip() not in p["languages"]:
                            p["languages"].append(new_lang.strip())
                            st.session_state.candidate_profile = p
                            if st.session_state.get("logged_in") and st.session_state.get("user"):
                                AuthManager.save_profile(st.session_state.user.get("uid"), p)
                            st.success(f"'{new_lang}' ajoutée !")
                            import time
                            time.sleep(0.5)
                            st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)

            # 4. Expériences
            st.markdown("<h4>Mes Expériences Professionnelles</h4>", unsafe_allow_html=True)
            all_exps = p.get("experiences", [])
            if not all_exps:
                st.info("Aucune expérience renseignée.")
            else:
                for idx, exp in enumerate(all_exps):
                    with st.expander(f"{exp.get('title', 'Poste')} chez {exp.get('company', 'Entreprise')}"):
                        exp_title = st.text_input("Poste", value=exp.get("title", ""), key=f"exp_title_{idx}")
                        exp_company = st.text_input("Entreprise", value=exp.get("company", ""), key=f"exp_company_{idx}")
                        exp_period = st.text_input("Période", value=exp.get("period", ""), key=f"exp_period_{idx}")
                        exp_desc = st.text_area("Description", value=exp.get("description", ""), key=f"exp_desc_{idx}")
                        
                        col_esave, col_edel = st.columns([1, 1])
                        with col_esave:
                            if st.button("Mettre à jour", key=f"upd_exp_{idx}"):
                                all_exps[idx] = {"title": exp_title, "company": exp_company, "period": exp_period, "description": exp_desc, "technologies": exp.get("technologies", [])}
                                p["experiences"] = all_exps
                                st.session_state.candidate_profile = p
                                if st.session_state.get("logged_in") and st.session_state.get("user"):
                                    AuthManager.save_profile(st.session_state.user.get("uid"), p)
                                st.success("Expérience mise à jour !")
                                import time
                                time.sleep(0.5)
                                st.rerun()
                        with col_edel:
                            if st.button("Supprimer", key=f"del_exp_{idx}"):
                                all_exps.pop(idx)
                                p["experiences"] = all_exps
                                st.session_state.candidate_profile = p
                                if st.session_state.get("logged_in") and st.session_state.get("user"):
                                    AuthManager.save_profile(st.session_state.user.get("uid"), p)
                                st.success("Expérience supprimée !")
                                import time
                                time.sleep(0.5)
                                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander("➕ Ajouter une expérience"):
                new_exp_title = st.text_input("Poste", key="new_exp_title")
                new_exp_company = st.text_input("Entreprise", key="new_exp_company")
                new_exp_period = st.text_input("Période (ex: 2020 - 2023)", key="new_exp_period")
                new_exp_desc = st.text_area("Description", key="new_exp_desc")
                if st.button("Ajouter cette expérience", use_container_width=True):
                    if new_exp_title and new_exp_company:
                        if "experiences" not in p: p["experiences"] = []
                        p["experiences"].append({
                            "title": new_exp_title,
                            "company": new_exp_company,
                            "period": new_exp_period,
                            "description": new_exp_desc,
                            "technologies": []
                        })
                        st.session_state.candidate_profile = p
                        if st.session_state.get("logged_in") and st.session_state.get("user"):
                            AuthManager.save_profile(st.session_state.user.get("uid"), p)
                        st.success("Nouvelle expérience ajoutée !")
                        import time
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("Le poste et l'entreprise sont obligatoires.")

            st.markdown("<br>", unsafe_allow_html=True)
            
            # Changer de profil below add button
            if st.button("Autres profils", use_container_width=True):
                st.session_state.confirm_change_profile = True
                
            if st.session_state.get("confirm_change_profile"):
                st.warning("Voulez-vous changer de profil utilisateur ? Cela effacera le profil actuel.")
                col_conf1, col_conf2 = st.columns(2)
                with col_conf1:
                    if st.button("Oui, changer de profil", use_container_width=True, type="primary"):
                        if st.session_state.get("logged_in") and st.session_state.get("user"):
                            uid = st.session_state.user.get("uid")
                            try:
                                from auth.firebase_config import db
                                from datetime import datetime
                                # Save current profile to saved_profiles collection
                                profile_id = p.get("job_title", "Profil").replace("/", "-") + "_" + datetime.now().strftime("%Y%m%d%H%M%S")
                                db.collection("users").document(uid).collection("saved_profiles").document(profile_id).set(p)
                                # Clear current candidate_profile
                                db.collection("users").document(uid).set({
                                    "candidate_profile":  None,
                                    "profile_updated_at": None
                                }, merge=True)
                            except Exception:
                                pass
                        st.session_state.candidate_profile = None
                        st.session_state.profile_source    = None
                        st.session_state.pipeline_result   = None
                        st.session_state.cv_filename       = None
                        st.session_state.user_profile_text = ""
                        st.session_state.confirm_change_profile = False
                        st.session_state.current_page = "Profil"
                        st.rerun()
                with col_conf2:
                    if st.button("Annuler", use_container_width=True):
                        st.session_state.confirm_change_profile = False
                        st.rerun()
    
            st.markdown("<br><hr>", unsafe_allow_html=True)
            
            if st.button("Enregistrer les modifications", type="primary", use_container_width=True):
                st.session_state.candidate_profile = p
                st.session_state.user_profile_text = p.get("summary", "")
                if st.session_state.get("logged_in") and st.session_state.get("user"):
                    AuthManager.save_profile(st.session_state.user.get("uid"), p)
                st.success("Profil mis à jour !")
                import time
                time.sleep(0.5)
                st.rerun()
    
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("### Apparence")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("Sombre", use_container_width=True, type="primary" if st.session_state.theme == "dark" else "secondary"):
            st.session_state.theme = "dark"
            st.query_params["theme"] = "dark"
            st.markdown("""
            <script>
            try {
                localStorage.setItem('jobagent_theme', 'dark');
            } catch(e) {}
            </script>
            """, unsafe_allow_html=True)
            if st.session_state.get("logged_in") and st.session_state.get("user"):
                uid = st.session_state.user.get("uid")
                try:
                    AuthManager.save_preferences(uid, {"theme": "dark"})
                except Exception:
                    pass
            st.rerun()
    with col_t2:
        if st.button("Clair", use_container_width=True, type="primary" if st.session_state.theme == "light" else "secondary"):
            st.session_state.theme = "light"
            st.query_params["theme"] = "light"
            st.markdown("""
            <script>
            try {
                localStorage.setItem('jobagent_theme', 'light');
            } catch(e) {}
            </script>
            """, unsafe_allow_html=True)
            if st.session_state.get("logged_in") and st.session_state.get("user"):
                uid = st.session_state.user.get("uid")
                try:
                    AuthManager.save_preferences(uid, {"theme": "light"})
                except Exception:
                    pass
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<div style='font-size: 11px; font-weight: bold; text-transform: uppercase; margin-bottom: 8px; opacity: 0.8;'>Configuration</div>", unsafe_allow_html=True)
    st.session_state.use_mock = st.toggle("Mode démo (sans API)", value=st.session_state.use_mock)
