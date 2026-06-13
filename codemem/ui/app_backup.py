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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from orchestrator import run_pipeline
from agents.scraper_agent import ScraperAgent
from agents.extractor_agent import ExtractorAgent
from agents.analyst_agent import AnalystAgent
from agents.coach_agent import CoachAgent
from utils.cv_parser        import CVParser
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
        "quiz_questions": [],
        "quiz_answers": {},
        "quiz_submitted": False,
        "use_mock": True,
        "candidate_profile": None,
        "profile_source": None,
        "cv_filename": None,
        "user_profile_text": "",
        "theme": "dark",
        "current_page": "Profil",
        "previous_page": None,
        "profile_image_url": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # ── Charger le profil depuis Firestore ──────────
    # Si l'utilisateur est connecté et qu'aucun profil
    # n'est encore en mémoire, on charge depuis Firebase
    if (st.session_state.get("logged_in") and
        st.session_state.get("candidate_profile") is None and
        st.session_state.get("user")):
        uid     = st.session_state.user.get("uid")
        profile = AuthManager.load_profile(uid)
        if profile:
            st.session_state.candidate_profile = profile
            st.session_state.user_profile_text = profile.get("profile_text", "")
            st.session_state.profile_source    = profile.get("profile_source", "text")
            st.session_state.cv_filename       = profile.get("cv_filename", None)
            
        if st.session_state.get("pipeline_result") is None:
            pipeline_result = AuthManager.load_job_search_results(uid)
            if pipeline_result:
                st.session_state.pipeline_result = pipeline_result
                
        # Forçons le type dict
        history = AuthManager.load_chat_history(uid)
        if isinstance(history, dict) and history:
            st.session_state.chat_history = history
        elif not isinstance(st.session_state.chat_history, dict):
            st.session_state.chat_history = {}

init_session()

# ============================================================
# THÈMES (DARK / LIGHT)
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
        "toggle_label": "Thème clair",
    },
    "light": {
        "bg_main":      "#FFFFFF",
        "bg_card":      "#F5F5F5",
        "bg_sidebar":   "#F0F0F0",
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
        "toggle_label": "Thème sombre",
    }
}

T = THEMES[st.session_state.theme]

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
    font-size: 1.8em !important;
}}

/* Boutons transparents avec bordure */
.stButton > button {{
    background: transparent !important;
    color: {T['text_main']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 8px !important;
    font-family: 'Roboto', sans-serif !important;
    font-weight: 500 !important;
    transition: all 0.2s ease !important;
}}

.stButton > button:hover {{
    border-color: {T['accent']} !important;
    transform: translateY(-1px) !important;
}}

.stButton > button:active, .stButton > button:focus {{
    border-color: {T['accent']} !important;
    background: {T['accent']}15 !important;
    transform: scale(0.98) !important;
}}

.stButton > button:disabled {{
    background: {T['border']} !important;
    color: {T['text_muted']} !important;
    transform: none !important;
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
    background: {T['bg_card']} !important;
    border: 1px solid {T['border']} !important;
    border-radius: 10px !important;
}}

[data-testid="stExpander"] summary {{
    color: {T['text_main']} !important;
    font-family: 'Roboto', sans-serif !important;
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

/* ── Composants custom ── */
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
    padding: 20px;
    margin: 12px 0;
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
</style>
""", unsafe_allow_html=True)

# ============================================================
# FONCTION PIPELINE DE RECHERCHE
# ============================================================
def _run_search_pipeline(user_profile: str):
    """Exécute le pipeline de recherche d'emploi."""
    with st.spinner("Chargement des offres d'emploi..."):
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

        # ── Sauvegarder dans Firestore ──────────────
        if st.session_state.get("logged_in") and st.session_state.get("user"):
            uid = st.session_state.user.get("uid")
            AuthManager.save_job_search_results(uid, st.session_state.pipeline_result)

        n = len(st.session_state.pipeline_result.get("compatibility_scores", []))
        st.success(f"{n} offres trouvées et analysées !")
        st.balloons()

# ============================================================
# SIDEBAR ET NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown(f"""
    <div style='text-align:center; padding:10px 0 20px;'>
        <div style='font-family:Roboto,sans-serif; font-size:1.5em; font-weight:800;
                    color:{T["text_main"]};'>JobAgent AI</div>
        <div style='font-size:0.75em; color:{T["text_muted"]}; margin-top:4px;'>
            Menu Principal
        </div>
    </div>
    """, unsafe_allow_html=True)

    def nav_button(label, page_name):
        is_active = st.session_state.current_page == page_name
        if st.button(label, type="primary" if is_active else "secondary", use_container_width=True):
            st.session_state.current_page = page_name
            st.rerun()

    nav_button("Mon Profil", "Profil")
    nav_button("Offres d'emploi", "Offres d'emploi")
    nav_button("Analyse", "Analyse")
    nav_button("Préparation à l'entretien", "Préparation à l'entretien")
    nav_button("Dashboard", "Dashboard")

    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Paramètres
    st.markdown(f"<div class='section-label'>Paramètres</div>", unsafe_allow_html=True)
    
    st.markdown("<div style='font-size:0.85em; margin-bottom:5px; margin-top:10px;'>Apparence</div>", unsafe_allow_html=True)
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        if st.button("Sombre", use_container_width=True, type="primary" if st.session_state.theme == "dark" else "secondary"):
            st.session_state.theme = "dark"
            st.rerun()
    with col_t2:
        if st.button("Clair", use_container_width=True, type="primary" if st.session_state.theme == "light" else "secondary"):
            st.session_state.theme = "light"
            st.rerun()

    st.markdown("<div style='font-size:0.85em; margin-top:10px;'>Configuration</div>", unsafe_allow_html=True)
    st.session_state.use_mock = st.toggle("Mode démo (sans API)", value=st.session_state.use_mock)

    # Profil actif
    if st.session_state.candidate_profile:
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(f"<div class='section-label'>Profil actif</div>", unsafe_allow_html=True)

        p = st.session_state.candidate_profile
        
        img_url = p.get("profile_image_url")
        
        # L'upload ne doit apparaître QUE si aucune photo n'est encore définie
        if not img_url:
            up_img = st.file_uploader("Ajouter une photo de profil", type=["png", "jpg", "jpeg"])
            if up_img:
                import base64
                b64 = base64.b64encode(up_img.read()).decode()
                mime = up_img.type
                st.session_state.candidate_profile["profile_image_url"] = f"data:{mime};base64,{b64}"
                
                if st.session_state.get("logged_in") and st.session_state.get("user"):
                    uid = st.session_state.user.get("uid")
                    AuthManager.save_profile(uid, st.session_state.candidate_profile)
                st.rerun()


        img_html = f"<img src='{img_url}' style='width:50px; height:50px; border-radius:50%; object-fit:cover; float:right; margin-top:-5px;'/>\n" if img_url else ""

        st.markdown(f"""
<div class='card' style='padding:14px; overflow:hidden;'>
{img_html}<div style='font-family:Roboto,sans-serif; font-weight:700; color:{T["text_main"]};'>{p.get("full_name", "Candidat")}</div>
<div style='color:{T["accent"]}; font-size:0.82em; margin-top:3px;'>{p.get("education_level", "N/A")}</div>
<div style='color:{T["text_muted"]}; font-size:0.78em;'>{p.get("experience_years", 0)} ans d'expérience</div>
</div>
""", unsafe_allow_html=True)

        if st.button("Autres profils", use_container_width=True):
            if st.session_state.get("logged_in") and st.session_state.get("user"):
                uid = st.session_state.user.get("uid")
                try:
                    from auth.firebase_config import db
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
            st.rerun()

    if st.button("déconnexion", use_container_width=True):
        st.session_state.logged_in        = False
        st.session_state.user             = None
        st.session_state.candidate_profile = None
        st.session_state.pipeline_result  = None
        st.session_state.chat_history     = {}
        st.session_state.quiz_questions   = []
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style='text-align:center; color:{T["text_subtle"]}; font-size:0.75em;'>
       Mainto Studio &copy; 2026
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# AFFICHAGE DE LA PAGE COURANTE
# ============================================================
page = st.session_state.current_page
st.markdown(f"<h1>{page}</h1>", unsafe_allow_html=True)

if page == "Dashboard":
    st.markdown(f"""
    <div class='hero'>
        <p class='hero-title'>JobAgent AI</p>
        <p class='hero-sub'>
            Système multi-agents de recherche d'emploi personnalisé &nbsp;·&nbsp; Cameroun
        </p>
        <div style='margin-top:14px; display:flex; gap:8px; flex-wrap:wrap;'>
            <span class='skill-pill'>Tavily Search</span>
            <span class='skill-pill'>Llama / Groq</span>
            <span class='skill-pill'>Ollama Local</span>
            <span class='skill-pill'>GPT-4o-mini</span>
            <span class='skill-pill'>RAG ChromaDB</span>
        </div>
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

elif page == "Profil":
    st.markdown("## Mon profil ")
    if st.session_state.candidate_profile:
        p = st.session_state.candidate_profile
        src = f"CV : {st.session_state.cv_filename}" if st.session_state.profile_source == "cv" \
              else "Profil saisi manuellement"
        st.success(f"Profil charge — {src}")
        skills_pills = "".join(
            f"<span class='skill-pill'>{s}</span>"
            for s in (p.get("hard_skills", []) + p.get("tools", []))[:10]
        )
        lang_pills = "".join(
            f"<span class='skill-pill'>{l}</span>"
            for l in p.get("languages", [])
        )
        st.markdown(f"""
        <div class='card-accent'>
            <div style='font-family:Roboto,sans-serif; font-size:1.4em;
                        font-weight:800; color:{T["text_main"]};'>
                {p.get("full_name","N/A")}
            </div>
            <div style='color:{T["accent"]}; margin-top:4px;'>
                {p.get("job_title","N/A")}
            </div>
            <div style='color:{T["text_muted"]}; font-size:0.85em; margin-top:6px;'>
                {p.get("location","N/A")} &nbsp;·&nbsp;
                {p.get("education_level","N/A")} &nbsp;·&nbsp;
                {p.get("experience_years",0)} ans
            </div>
            <div style='color:{T["text_muted"]}; font-size:0.88em; margin:12px 0 8px;
                        border-left:2px solid {T["accent"]}; padding-left:10px;
                        font-style:italic;'>
                {p.get("summary","")[:250]}
            </div>
            <div style='margin-top:10px;'>
                <div style='color:{T["text_subtle"]}; font-size:0.75em; font-weight:700;
                            letter-spacing:1px; text-transform:uppercase;
                            margin-bottom:6px;'>Competences</div>
                {skills_pills or f"<span style='color:{T['text_muted']};font-size:0.85em;'>Non precisees</span>"}
            </div>
            <div style='margin-top:10px;'>
                <div style='color:{T["text_subtle"]}; font-size:0.75em; font-weight:700;
                            letter-spacing:1px; text-transform:uppercase;
                            margin-bottom:6px;'>Langues</div>
                {lang_pills or f"<span style='color:{T['text_muted']};font-size:0.85em;'>Non precisees</span>"}
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")
        if st.button("Lancer la recherche d emploi", type="primary"):
            _run_search_pipeline(st.session_state.user_profile_text)
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
                help="PDF, DOCX, DOC — max 10 Mo"
            )
            if uploaded_file:
                col_i, col_b = st.columns([3, 1])
                with col_i:
                    st.markdown(f"""
                    <div class='card' style='padding:12px; color:{T["accent"]}; fontsize:0.9em;'>
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
                            
                            
                            # ── Sauvegarder dans Firestore ──────────────
                        if st.session_state.get("logged_in") and st.session_state.get("user"):
                            uid = st.session_state.user.get("uid")
                            profile_to_save = {
                            **profile,
                           "profile_source": "cv",
                          "cv_filename":    uploaded_file.name,
                            }
                            AuthManager.save_profile(uid, profile_to_save)
                           
                            st.success("CV analyse avec succes !")
                            st.rerun()
                           
            else:
                st.markdown(f"""
                <div style='border:2px dashed {T["border"]}; border-radius:12px;
                            padding:48px; text-align:center; background:{T["bg_card"]};'>
                    <div style='color:{T["text_muted"]}; font-size:1em;'>
                        Deposez votre CV ici
                    </div>
                    <div style='color:{T["text_subtle"]}; font-size:0.82em; margin-top:6px;'>
                        PDF · DOCX · DOC
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
                    profile = {
                        "full_name": "Candidat", "email": "", "phone": "",
                        "location": "", "job_title": "",
                        "summary": user_text[:300],
                        "hard_skills": [], "soft_skills": [], "tools": [],
                        "languages": [], "education_level": "",
                        "experience_years": 0, "sectors": [],
                        "profile_text": user_text, "raw_cv_text": user_text,
                    }
                    
                    st.session_state.candidate_profile = profile
                    st.session_state.profile_source    = "text"
                    st.session_state.user_profile_text = user_text
                    
                    # ── Sauvegarder dans Firestore ──────────────
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
    st.markdown("## Offres d'emploi collectées")

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
            col_f1, col_f2 = st.columns(2)

            with col_f1:
                min_score = st.slider("Score minimum", 0, 100, 0, 5)

            with col_f2:
                sources = list(set(j.get("source", "N/A") for j in jobs))
                sel_src = st.multiselect("Sources", sources, default=sources)

            filtered = [j for j in jobs
                        if j.get("score", 0) >= min_score
                        and j.get("source", "N/A") in sel_src]

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
                            st.session_state.previous_page = "Offres d'emploi"
                            st.session_state.current_page = "Analyse"
                            st.rerun()

                        if st.button("Se préparer", key=f"sel_{i}", use_container_width=True):
                            st.session_state.selected_job = job
                            st.session_state.previous_page = "Offres d'emploi"
                            st.session_state.current_page = "Préparation à l'entretien"
                            st.rerun()

# ============================================================
# TAB 3 — ANALYSE
# ============================================================
elif page == "Analyse":
    st.markdown("## Analyse de compatibilité")

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

    if st.session_state.previous_page:
        st.markdown("<br>", unsafe_allow_html=True)
        col_b, _ = st.columns([1, 15])
        with col_b:
            if st.button("←", key="back_analyse_end", help="Retour à la page précédente"):
                st.session_state.current_page = st.session_state.previous_page
                st.session_state.previous_page = None
                st.rerun()

# ============================================================
# TAB 4 — COACH
# ============================================================
elif page == "Préparation à l'entretien":
    st.markdown("## Préparer l'entretien d'embauche")

    if not st.session_state.selected_job:
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

        st.markdown(f"""
        <div class='card'>
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

        subtab1, subtab2 = st.tabs(["Générer un quiz", "Interagir avec le coach"])

        # ====================================================
        # SUBTAB 1 — QUIZ QCM
        # ====================================================
        with subtab1:
            if not st.session_state.quiz_questions:
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False

                col_btn, _ = st.columns([1, 2])

                with col_btn:
                    if st.button("Générer le quiz QCM", type="primary", use_container_width=True):
                        with st.spinner("CoachAgent génère votre quiz..."):
                            if st.session_state.use_mock:
                                st.session_state.quiz_questions = \
                                    CoachAgent.mock_generate_quiz(job)
                            else:
                                coach = CoachAgent()
                                st.session_state.quiz_questions = \
                                    coach.generate_quiz(job)
                            st.rerun()
            else:
                questions = st.session_state.quiz_questions
                submitted = st.session_state.quiz_submitted

                type_labels = {
                    "technique": "Technique",
                    "comportemental": "Comportemental",
                    "mise_en_situation": "Mise en situation",
                }

                # Affichage des questions
                for q in questions:
                    qid = q.get("id", 0)
                    qtype = q.get("type", "technique")
                    label = type_labels.get(qtype, "Question")
                    options = q.get("options", {})
                    correct = q.get("correct_answer", "A")
                    user_ans = st.session_state.quiz_answers.get(str(qid))

                    # Couleur de la card selon résultat
                    if submitted and user_ans:
                        extra_cls = "quiz-ok" if user_ans == correct else "quiz-fail"
                    else:
                        extra_cls = ""

                    st.markdown(f"""
                    <div class='quiz-card {extra_cls}'>
                        <span style='background:{T["accent"]}22; color:{T["accent"]};
                                     border:1px solid {T["accent"]}44; padding:2px 10px;
                                     border-radius:20px; font-size:0.75em;
                                     font-family:Roboto,sans-serif; font-weight:700;'>
                            {label}
                        </span>
                        <div style='font-family:Roboto,sans-serif; font-weight:700;
                                    color:{T["text_main"]}; font-size:0.97em;
                                    margin:10px 0 14px;'>
                            Q{qid}. {q.get("question", "")}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Propositions
                    if not submitted:
                        choice = st.radio(
                            f"q{qid}",
                            options=list(options.keys()),
                            format_func=lambda k, o=options: f"{k}.  {o[k]}",
                            key=f"radio_{qid}",
                            label_visibility="collapsed"
                        )
                        st.session_state.quiz_answers[str(qid)] = choice
                    else:
                        for key, text in options.items():
                            if key == correct:
                                css = "option-correct"
                                icon = "✓"
                            elif key == user_ans and user_ans != correct:
                                css = "option-wrong"
                                icon = "✗"
                            else:
                                css = "option-neutral"
                                icon = "○"

                            st.markdown(
                                f"<div class='{css}'>{icon} &nbsp; <strong>{key}.</strong>"
                                f" &nbsp; {text}</div>",
                                unsafe_allow_html=True
                            )

                        st.markdown(
                            f"<div class='explanation-box'>"
                            f"<strong>Explication :</strong> {q.get('explanation', '')}"
                            f"</div>",
                            unsafe_allow_html=True
                        )

                st.markdown("<hr>", unsafe_allow_html=True)

                # Bouton de soumission
                if not submitted:
                    nb_ans = len(st.session_state.quiz_answers)
                    nb_total = len(questions)
                    all_done = nb_ans >= nb_total

                    if not all_done:
                        st.markdown(
                            f"<div style='color:{T['text_muted']}; font-size:0.85em;"
                            f"margin-bottom:10px;'>"
                            f"{nb_ans}/{nb_total} question(s) répondue(s)</div>",
                            unsafe_allow_html=True
                        )

                    col_s, _ = st.columns([1, 2])

                    with col_s:
                        if st.button("Soumettre mes réponses", type="primary",
                                     use_container_width=True, disabled=not all_done):
                            st.session_state.quiz_submitted = True
                            st.rerun()

                # Score final
                else:
                    correct_count = sum(
                        1 for q in questions
                        if st.session_state.quiz_answers.get(str(q["id"])) == q["correct_answer"]
                    )
                    total = len(questions)
                    pct = int(correct_count / total * 100)

                    color = T["success"] if pct >= 80 else T["warning"] if pct >= 50 else T["error"]

                    msg = (
                        "Excellent ! Vous êtes bien préparé pour cet entretien."
                        if pct >= 80 else
                        "Bon travail ! Révisez les points manquants."
                        if pct >= 50 else
                        "Continuez à vous entraîner — utilisez le chat pour approfondir."
                    )

                    st.markdown(f"""
                    <div class='score-box' style='border-color:{color};'>
                        <div style='font-family:Roboto,sans-serif; font-size:2.5em;
                                    font-weight:800; color:{color};'>
                            {correct_count} / {total}
                        </div>
                        <div style='font-size:1.2em; font-weight:700;
                                    color:{color};'>{pct}%</div>
                        <div style='color:{T["text_muted"]}; font-size:0.9em;
                                    margin-top:8px;'>{msg}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    with st.expander("Détail par question"):
                        for q in questions:
                            qid = q.get("id", 0)
                            correct = q.get("correct_answer", "A")
                            answer = st.session_state.quiz_answers.get(str(qid), "-")
                            ok = answer == correct

                            st.markdown(
                                f"{'✓' if ok else '✗'} **Q{qid}.** "
                                f"{q.get('question', '')[:55]}... "
                                f"Réponse : **{answer}** "
                                f"{'(correct)' if ok else f'(attendu : {correct})'}"
                            )

                    col_r, _ = st.columns([1, 2])

                    with col_r:
                        if st.button("Recommencer le quiz", use_container_width=True):
                            st.session_state.quiz_questions = []
                            st.session_state.quiz_answers = {}
                            st.session_state.quiz_submitted = False
                            st.rerun()

        # ====================================================
        # SUBTAB 2 — CHAT ET ENTRETIEN
        # ====================================================
        with subtab2:
            job_key = job.get("url", job.get("title", "default"))
            if not isinstance(st.session_state.chat_history, dict):
                st.session_state.chat_history = {}
                
            if job_key not in st.session_state.chat_history:
                st.session_state.chat_history[job_key] = []
                
            active_chat = st.session_state.chat_history[job_key]

            # Historique des chats
            past_sessions = [k for k, v in st.session_state.chat_history.items() if len(v) > 0]
            if past_sessions:
                options = [job_key] + [s for s in past_sessions if s != job_key]
                selected_hist = st.selectbox("Historique des chats (Continuer une conversation)", options)
                if selected_hist != job_key:
                    job_key = selected_hist
                    active_chat = st.session_state.chat_history[job_key]

            if st.button("Commencer un entretien virtuel", use_container_width=True):
                with st.spinner("Coach démarre l'entretien..."):
                    if st.session_state.use_mock:
                        welcome = f"Bonjour ! Bienvenue à votre entretien pour le poste de {job['title']}. Parlez-moi un peu de vous."
                    else:
                        welcome = CoachAgent().init_interview(job)
                            
                    st.session_state.chat_history[job_key] = [{"role": "assistant", "content": welcome}]
                        
                    if st.session_state.get("logged_in") and st.session_state.get("user"):
                        uid = st.session_state.user.get("uid")
                        AuthManager.save_chat_history(uid, st.session_state.chat_history)
                    st.rerun()

            st.markdown("<hr>", unsafe_allow_html=True)
            
            if not active_chat:
                st.info("Cliquez sur 'Commencer un entretien virtuel' ou posez votre première question ci-dessous pour démarrer.")

            for msg in active_chat:
                css = "chat-user" if msg["role"] == "user" else "chat-bot"
                prefix = "Vous" if msg["role"] == "user" else "Coach"

                st.markdown(
                    f"<div class='{css}'><strong>{prefix} :</strong> {msg['content']}</div>",
                    unsafe_allow_html=True
                )

            if prompt := st.chat_input("Posez une question au Coach ou répondez à sa question..."):
                active_chat.append({"role": "user", "content": prompt})

                with st.spinner("Coach réfléchit..."):
                    if st.session_state.use_mock:
                        response = f"C'est une très bonne réponse pour {job['title']}. Avez-vous une autre question ?"
                    else:
                        response = CoachAgent().chat(
                            user_message=prompt,
                            job=job,
                            history=active_chat[:-1]
                        )

                    active_chat.append(
                        {"role": "assistant", "content": response}
                    )

                st.session_state.chat_history[job_key] = active_chat

                if st.session_state.get("logged_in") and st.session_state.get("user"):
                    uid = st.session_state.user.get("uid")
                    AuthManager.save_chat_history(uid, st.session_state.chat_history)

                st.rerun()

    if st.session_state.previous_page:
        st.markdown("<br>", unsafe_allow_html=True)
        col_b, _ = st.columns([1, 15])
        with col_b:
            if st.button("←", key="back_prep_end", help="Retour à la page précédente"):
                st.session_state.current_page = st.session_state.previous_page
                st.session_state.previous_page = None
                st.rerun()