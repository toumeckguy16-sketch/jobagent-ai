"""
ui/login_page.py
Page de connexion — Email/Password + Google OAuth
Thème dynamique (sombre/clair) identique à app.py
"""
import streamlit as st
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from auth.auth_manager import AuthManager
import webbrowser
import requests
# ─────────────────────────────────────────────
#  THÈMES (identiques à app.py)
# ─────────────────────────────────────────────
THEMES = {
    "dark": {
        "bg_main":    "#0F0F0F",
        "bg_card":    "#1A1A1A",
        "text_main":  "#E5E5E5",
        "text_muted": "#888888",
        "text_subtle":"#555555",
        "accent":     "#FF6B00",
        "accent_h":   "#FF8C33",
        "border":     "#2A2A2A",
        "success":    "#22C55E",
        "error":      "#EF4444",
    },
    "light": {
        "bg_main":    "#FFFFFF",
        "bg_card":    "#F5F5F5",
        "text_main":  "#111111",
        "text_muted": "#555555",
        "text_subtle":"#999999",
        "accent":     "#DC2626",
        "accent_h":   "#16A34A",
        "border":     "#E0E0E0",
        "success":    "#16A34A",
        "error":      "#DC2626",
    }
}
def render_login_page():
    """Affiche la page de connexion et gère l'authentification."""
    # ── Restauration du thème depuis les query_params ou session state ──
    qp_theme = st.query_params.get("theme", None)
    if qp_theme in ("dark", "light"):
        st.session_state.theme = qp_theme
    elif "theme" not in st.session_state:
        st.session_state.theme = "dark"
        
    T = THEMES[st.session_state.theme]
    
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
    
    import time
    
    # ── Gestion du retour Google OAuth ────────────────
    if "code" in st.query_params:
        code = st.query_params["code"]
        st.query_params.clear()
        
        with st.spinner("Connexion Google en cours..."):
            from dotenv import load_dotenv
            load_dotenv()
            client_id = os.getenv("GOOGLE_CLIENT_ID")
            client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
            redirect_uri = "https://jobagent-ai-taxhx9jqu3drmxss6muhkg.streamlit.app"
            
            token_url = "https://oauth2.googleapis.com/token"
            data = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
            resp = requests.post(token_url, data=data)
            token_data = resp.json()
            
            if "id_token" in token_data:
                id_token = token_data["id_token"]
                firebase_api_key = os.getenv("FIREBASE_API_KEY", "AIzaSyDPzWlUWTTJglkNcwNe-SdfqDfZXFrChCs")
                fb_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key={firebase_api_key}"
                payload = {
                    "requestUri": "https://jobagent-ai-taxhx9jqu3drmxss6muhkg.streamlit.app",
                    "postBody": f"id_token={id_token}&providerId=google.com",
                    "returnSecureToken": True,
                    "returnIdpCredential": True
                }
                fb_resp = requests.post(fb_url, json=payload)
                fb_data = fb_resp.json()
                
                if "localId" in fb_data:
                    st.session_state.user = {
                        "uid": fb_data["localId"],
                        "email": fb_data.get("email", ""),
                        "full_name": fb_data.get("displayName", "Utilisateur Google"),
                        "provider": "google",
                        "id_token": fb_data.get("idToken"),
                        "refresh_token": fb_data.get("refreshToken", ""),
                        "expires_at": time.time() + int(fb_data.get("expiresIn", 3600))
                    }
                    st.session_state.is_new_user = False
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Erreur d'authentification avec Google via Firebase.")
            else:
                st.error("Erreur lors de la récupération des informations Google.")
                
    # ── CSS ──────────────────────────────────
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&family=Roboto:wght@400;500;700;800;900&display=swap');
    
    /* Cacher l'entête Streamlit et forcer le fond sombre sur tous les conteneurs */
    header[data-testid="stHeader"] {{
        display: none !important;
        height: 0px !important;
    }}
    [data-testid="stSidebar"] {{ display: none !important; }}
    
    html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stAppViewBlockContainer"] {{
        background-color: {T['bg_main']} !important;
        background: {T['bg_main']} !important;
        font-family: 'DM Sans', sans-serif !important;
        color: {T['text_main']} !important;
    }}
    
    /* Supprimer l'espace vide au-dessus de la page */
    .block-container {{
        padding-top: 0rem !important;
        margin-top: 0rem !important;
    }}
    [data-testid="stAppViewBlockContainer"] {{
        padding-top: 0rem !important;
        padding-bottom: 1rem !important;
        margin-top: 0rem !important;
    }}
    /* Cacher les containers de script/style vides pour éviter le décalage vertical */
    .element-container:has(script), .element-container:has(style) {{
        display: none !important;
        height: 0px !important;
        margin: 0px !important;
        padding: 0px !important;
    }}
    
    /* Forcer la couleur du texte et des labels Streamlit */
    .stApp p, .stApp span, .stApp label {{
        color: {T['text_main']} !important;
    }}
    
    h1, h2, h3 {{
        font-family: 'Syne', sans-serif !important;
        color: {T['text_main']} !important;
    }}
    
    .stButton > button {{
        background: transparent !important;
        color: {T['text_main']} !important;
        border: 1px solid {T['accent']} !important;
        border-radius: 8px !important;
        font-family: 'Syne', sans-serif !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        height: 48px !important;
    }}
    .stButton > button:hover {{
        background: {T['accent']} !important;
        color: #FFFFFF !important;
        transform: translateY(-1px) !important;
    }}
    .stButton > button p {{
        color: {T['text_main']} !important;
        font-size: 0.9em !important;
        margin: 0 !important;
    }}
    .stButton > button:hover p {{
        color: #FFFFFF !important;
    }}
    
    .stTextInput input {{
        background: {T['bg_card']} !important;
        border: 1px solid {T['border']} !important;
        border-radius: 8px !important;
        color: {T['text_main']} !important;
        font-family: 'DM Sans', sans-serif !important;
        caret-color: {T['text_main']} !important;
    }}
    .stTextInput input:focus {{
        border-color: {T['accent']} !important;
        box-shadow: 0 0 0 2px {T['accent']}33 !important;
    }}
    
    [data-testid="stTabs"] button {{
        font-family: 'Syne', sans-serif !important;
        font-weight: 600 !important;
        background: transparent !important;
    }}
    [data-testid="stTabs"] button p {{
        color: {T['text_muted']} !important;
    }}
    [data-testid="stTabs"] button[aria-selected="true"] {{
        border-bottom: 2px solid {T['accent']} !important;
    }}
    [data-testid="stTabs"] button[aria-selected="true"] p {{
        color: {T['accent']} !important;
    }}
    
    hr {{ border-color: {T['border']} !important; }}
    </style>
    """, unsafe_allow_html=True)
    # ── Le sélecteur de thème a été retiré pour forcer le thème sombre comme dans l'image ──
    # ── Centrage du formulaire ───────────────
    _, col_center, _ = st.columns([1, 2, 1])
    with col_center:
        # Logo / Titre
        st.markdown(f"""
        <div style='text-align:center; padding:0; margin-bottom:5px;'>
            <div style='font-family:Roboto,sans-serif; font-size:2.4em;
                        font-weight:800; color:{T["text_main"]} !important;
                        letter-spacing:-1px;'>JobAgent AI</div>
        </div>
        """, unsafe_allow_html=True)
        # Carte formulaire (sans fond ni bordure pour correspondre à l'image)
        st.markdown(f"""
        <div style='padding:0px 0px; margin-bottom:0px;'>
        """, unsafe_allow_html=True)
        # Onglets Connexion / Inscription
        tab_login, tab_register = st.tabs(["Connexion", "Creer un compte"])
        # ══════════════════════════════════════
        #  ONGLET CONNEXION
        # ══════════════════════════════════════
        with tab_login:
            login_email = st.text_input(
                "Adresse email",
                placeholder="vous@example.com",
                key="login_email"
            )
            login_password = st.text_input(
                "Mot de passe",
                type="password",
                placeholder="Votre mot de passe",
                key="login_password"
            )
            col_btn, col_forgot = st.columns([2, 1])
            with col_btn:
                login_btn = st.button("Se connecter", type="primary",
                                      use_container_width=True, key="btn_login")
            with col_forgot:
                forgot_btn = st.button("Mot de passe oublie ?",
                                       use_container_width=True, key="btn_forgot")
            # Connexion Email
            if login_btn:
                if not login_email or not login_password:
                    st.error("Veuillez remplir tous les champs.")
                else:
                    with st.spinner("Connexion en cours..."):
                        result = AuthManager.login(login_email, login_password)
                    if result["success"]:
                        st.session_state.user      = result["user"]
                        st.session_state.is_new_user = False
                        st.session_state.logged_in = True
                        st.rerun()
                    else:
                        st.error(result["error"])
            # Mot de passe oublié
            if forgot_btn:
                if not login_email:
                    st.warning("Entrez votre email ci-dessus puis cliquez a nouveau.")
                else:
                    with st.spinner("Envoi du lien de reinitialisation..."):
                        result = AuthManager.reset_password(login_email)
                    if result["success"]:
                        st.success("Email de reinitialisation envoye ! Verifiez votre boite mail.")
                    else:
                        st.error(result["error"])
            # Séparateur Google
            st.markdown(f"""
            <div style='display:flex; align-items:center; margin-top:-15px; margin-bottom:5px;'>
                <hr style='flex:1; border-color:{T["border"]};'>
                <span style='color:{T["text_muted"]} !important; font-size:0.82em;
                             padding:0 12px;'>ou</span>
                <hr style='flex:1; border-color:{T["border"]};'>
            </div>
            """, unsafe_allow_html=True)
            # Bouton Google
            _render_google_button()

        # ══════════════════════════════════════
        #  ONGLET INSCRIPTION
        # ══════════════════════════════════════
        with tab_register:
            reg_name = st.text_input(
                "Nom complet",
                placeholder="Jean Dupont",
                key="reg_name"
            )
            reg_email = st.text_input(
                "Adresse email",
                placeholder="vous@example.com",
                key="reg_email"
            )
            reg_password = st.text_input(
                "Mot de passe",
                type="password",
                placeholder="Minimum 6 caracteres",
                key="reg_password"
            )
            reg_confirm = st.text_input(
                "Confirmer le mot de passe",
                type="password",
                placeholder="Repetez le mot de passe",
                key="reg_confirm"
            )
            register_btn = st.button("Creer mon compte", type="primary",
                                     use_container_width=True, key="btn_register")
            if register_btn:
                # Validations
                if not all([reg_name, reg_email, reg_password, reg_confirm]):
                    st.error("Veuillez remplir tous les champs.")
                elif reg_password != reg_confirm:
                    st.error("Les mots de passe ne correspondent pas.")
                elif len(reg_password) < 6:
                    st.error("Le mot de passe doit contenir au moins 6 caracteres.")
                else:
                    with st.spinner("Creation du compte..."):
                        result = AuthManager.register(reg_email, reg_password, reg_name)
                    if result["success"]:
                     st.session_state.user      = result["user"]
                     st.session_state.is_new_user = True
                     st.session_state.logged_in = True
                     st.rerun()
                    else:
                        st.error(result["error"])
            # Séparateur Google
            st.markdown(f"""
            <div style='display:flex; align-items:center; margin-top:-15px; margin-bottom:5px;'>
                <hr style='flex:1; border-color:{T["border"]};'>
                <span style='color:{T["text_muted"]} !important; font-size:0.82em;
                             padding:0 12px;'>ou</span>
                <hr style='flex:1; border-color:{T["border"]};'>
            </div>
            """, unsafe_allow_html=True)
            _render_google_button()
        st.markdown("</div>", unsafe_allow_html=True)
        # Footer
        st.markdown(f"""
        <div style='text-align:center; color:{T["text_subtle"]} !important;
                    font-size:0.78em; margin-top:20px;'>
           By Mainto Studio &copy; 2026
        </div>
        """, unsafe_allow_html=True)
# ─────────────────────────────────────────────
#  GOOGLE AUTH
# ─────────────────────────────────────────────
def _render_google_button():
    """
    Génère l'URL d'authentification Google et affiche le bouton SVG stylisé.
    """
    from dotenv import load_dotenv
    load_dotenv()
    
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        st.error("La clé GOOGLE_CLIENT_ID est manquante dans le fichier .env.")
        return

    redirect_uri_encoded = "https%3A%2F%2Fjobagent-ai-taxhx9jqu3drmxss6muhkg.streamlit.app"
    
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri_encoded}&"
        f"response_type=code&"
        f"scope=openid%20email%20profile&"
        f"access_type=offline&"
        f"prompt=select_account"
    )
    
    st.markdown(f"""
    <a href="{auth_url}" target="_self" style="
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: #F2F2F2;
        color: #111111 !important;
        text-decoration: none;
        border-radius: 999px;
        height: 48px;
        font-family: 'DM Sans', sans-serif;
        font-weight: 600;
        font-size: 16px;
        transition: background 0.2s;
        border: 1px solid #E0E0E0;
        width: 100%;
        box-sizing: border-box;
    ">
        <svg version="1.1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" style="width:20px; height:20px; margin-right:12px;">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.7 17.74 9.5 24 9.5z"></path>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"></path>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"></path>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"></path>
            <path fill="none" d="M0 0h48v48H0z"></path>
        </svg>
        Se connecter avec Google
    </a>
    """, unsafe_allow_html=True)