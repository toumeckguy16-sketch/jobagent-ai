"""
run_streamlit.py
Routeur Streamlit : login → app
"""

import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import streamlit as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Restauration de session et thème depuis localStorage via URL query params ──
import time
import json
import urllib.parse
from auth.auth_manager import AuthManager

# Traitement de la restauration de session
if "session_restore" in st.query_params:
    try:
        session_data = json.loads(urllib.parse.unquote(st.query_params["session_restore"]))
        if isinstance(session_data, dict) and "refresh_token" in session_data:
            expires_at = session_data.get("expires_at", 0)
            if time.time() < expires_at - 60:
                # Encore valide localement
                st.session_state.logged_in = True
                st.session_state.user = session_data
            else:
                # Expiré, tentative de rafraîchissement silencieux
                refresh_tok = session_data["refresh_token"]
                result = AuthManager.refresh_id_token(refresh_tok)
                if result.get("success"):
                    session_data["id_token"] = result["id_token"]
                    session_data["refresh_token"] = result["refresh_token"]
                    session_data["expires_at"] = time.time() + 3600
                    st.session_state.logged_in = True
                    st.session_state.user = session_data
                elif result.get("error") == "network_error":
                    # Tolérance panne réseau à l'initialisation : restaurer la session en mode hors-ligne
                    st.session_state.logged_in = True
                    st.session_state.user = session_data
                    st.session_state.network_error_count = 1
    except Exception:
        pass
    st.query_params.pop("session_restore", None)

# Récupérer le thème depuis l'URL
qp_theme = st.query_params.get("theme", None)
if qp_theme in ("dark", "light"):
    st.session_state.theme = qp_theme
elif "theme" not in st.session_state:
    st.session_state.theme = "dark"

# ── Session State ─────────────────────────────
defaults = {
    "logged_in": False,
    "user":      None,
    "theme":     st.session_state.get("theme", "dark"),
    "use_mock":  os.getenv("USE_MOCK_MODE", "False") == "True",
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── Injection JS via HTML Component (exécuté dans le parent Streamlit) ──
st.components.v1.html("""
<script>
(function() {
    const parentWindow = window.parent;
    try {
        const savedTheme = parentWindow.localStorage.getItem('jobagent_theme');
        const savedSession = parentWindow.localStorage.getItem('jobagent_session');
        const params = new URLSearchParams(parentWindow.location.search);
        let needsRedirect = false;
        
        if (savedTheme && !params.has('theme')) {
            params.set('theme', savedTheme);
            needsRedirect = true;
        }
        
        // Restaurer la session si pas de paramètre no_restore et pas déjà restaurée
        if (savedSession && !params.has('session_restore') && !params.has('no_restore') && !parentWindow.__session_checked) {
            params.set('session_restore', encodeURIComponent(savedSession));
            parentWindow.__session_checked = true;
            needsRedirect = true;
        }
        
        if (needsRedirect) {
            parentWindow.history.replaceState(null, '', '?' + params.toString());
            parentWindow.location.reload();
        }
    } catch(e) {}

    // Listener pour la landing page (postMessage depuis l'iframe)
    if (!parentWindow.__navigate_listener_registered) {
        parentWindow.__navigate_listener_registered = true;
        parentWindow.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'navigate_login') {
                try {
                    const params = new URLSearchParams(parentWindow.location.search);
                    params.set('action', 'login');
                    parentWindow.history.replaceState(null, '', '?' + params.toString());
                    parentWindow.location.reload();
                } catch(e) {}
            }
        });
    }
})();
</script>
""", height=0)

# ── Routage ───────────────────────────────────
if not st.session_state.logged_in:
    # Si l'utilisateur clique sur "Commencer" ou a déjà vu la landing page
    if st.query_params.get("action") == "login" or st.session_state.get("seen_landing", False):
        st.session_state.seen_landing = True
        if "action" in st.query_params:
            # On retire l'action pour que le lien ne reste pas dans l'URL
            st.query_params.pop("action")
            st.rerun()

        from ui.login_page import render_login_page
        render_login_page()
    else:
        # Affichage de la Landing Page en plein écran
        st.markdown(
            """
            <style>
                #MainMenu {visibility: hidden;}
                header {visibility: hidden;}
                footer {visibility: hidden;}
                .stApp { padding-top: 0 !important; }
                .block-container {
                    padding: 0rem !important;
                    max-width: 100% !important;
                }
                iframe.landing-frame {
                    height: 100vh !important;
                    width: 100vw !important;
                    border: none;
                    margin: 0;
                    padding: 0;
                    display: block;
                }
            </style>
            """,
            unsafe_allow_html=True
        )
        landing_path = ROOT / "landing" / "index.html"
        if landing_path.exists():
            html_content = landing_path.read_text(encoding="utf-8")
            import base64
            b64_html = base64.b64encode(html_content.encode('utf-8')).decode('utf-8')
            st.markdown(f'<iframe class="landing-frame" src="data:text/html;base64,{b64_html}"></iframe>', unsafe_allow_html=True)
        else:
            st.error("Landing page non trouvée.")
else:
    # Charger app.py comme script principal
    with open(ROOT / "ui" / "app.py", encoding="utf-8") as f:
        code = compile(f.read(), str(ROOT / "ui" / "app.py"), "exec")
    exec(code, {"__file__": str(ROOT / "ui" / "app.py"), "__name__": "__main__"})