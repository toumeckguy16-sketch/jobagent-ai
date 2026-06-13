"""
Orchestrateur Principal - LangGraph StateGraph
Coordonne les 4 agents du système multi-agent de recherche d'emploi
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from typing import TypedDict, List, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
import operator
from agents.scraper_agent import ScraperAgent
from agents.extractor_agent import ExtractorAgent
from agents.analyst_agent import AnalystAgent
from agents.coach_agent import CoachAgent
# ─────────────────────────────────────────────
#  ÉTAT PARTAGÉ entre tous les agents
# ─────────────────────────────────────────────
class JobSearchState(TypedDict):
    # Profil utilisateur (entrée F1)
    user_profile: str                        # Description texte du candidat
    user_skills: List[str]                   # Compétences extraites du profil
    # Offres collectées (F2)
    raw_jobs: List[dict]                     # Offres brutes scrappées
    # Compétences des offres (F3)
    jobs_with_skills: List[dict]             # Offres enrichies + compétences extraites
    selected_job: Optional[dict]             # Offre sélectionnée par l'utilisateur
    # Analyse de compatibilité (F4)
    compatibility_scores: List[dict]         # Scores profil vs offres
    best_match: Optional[dict]               # Meilleure offre
    # Préparation entretien (F5)
    quiz_questions: List[dict]               # Questions générées par RAG
    chat_history: Annotated[list, add_messages]  # Historique du chat
    # Statut interne
    current_step: str
    errors: List[str]
    flyer_url: Optional[str]  # URL du flyer de présentation du projet
# ─────────────────────────────────────────────
#  NŒUDS DU GRAPHE (un par agent)
# ─────────────────────────────────────────────
def scraper_node(state: JobSearchState) -> JobSearchState:
    """Nœud Agent Scraper : collecte les offres (F2)"""
    print("🔍[Agent Scraper] Collecte des offres en cours...")
    agent = ScraperAgent()
    jobs = agent.scrape(query=state["user_profile"])
    return {
        **state,
        "raw_jobs": jobs,
        "current_step": "scraping_done"
    }
def extractor_node(state: JobSearchState) -> JobSearchState:
    """Nœud Agent Extracteur : extrait les compétences (F3)"""
    print("📋[Agent Extracteur] Extraction des compétences...")
    agent = ExtractorAgent()
    enriched_jobs = agent.extract_skills(jobs=state["raw_jobs"])
    return {
        **state,
        "jobs_with_skills": enriched_jobs,
        "current_step": "extraction_done"
    }
def analyst_node(state: JobSearchState) -> JobSearchState:
    """Nœud Agent Analyste : calcule la compatibilité (F4)"""
    print("📊[Agent Analyste] Calcul des scores de compatibilité...")
    agent = AnalystAgent()
    scores = agent.analyze(
        user_profile=state["user_profile"],
        jobs=state["jobs_with_skills"]
    )
    best = max(scores, key=lambda x: x["score"]) if scores else None
    return {
        **state,
        "compatibility_scores": scores,
        "best_match": best,
        "current_step": "analysis_done"
    }
def coach_node(state: JobSearchState) -> JobSearchState:
    """Nœud Agent Coach : génère le quiz RAG (F5)"""
    print("🎯[Agent Coach] Génération du quiz d'entretien...")
    if not state.get("selected_job"):
        return {**state, "current_step": "coach_skipped"}
    agent = CoachAgent()
    quiz = agent.generate_quiz(job=state["selected_job"])
    return {
        **state,
        "quiz_questions": quiz,
        "current_step": "coach_done"
    }
# ─────────────────────────────────────────────
#  CONDITIONS DE ROUTAGE
# ─────────────────────────────────────────────
def should_run_coach(state: JobSearchState) -> str:
    """Décide si le coach doit s'activer (offre sélectionnée ?)"""
    if state.get("selected_job"):
        return "run_coach"
    return "skip_coach"
# ─────────────────────────────────────────────
#  CONSTRUCTION DU GRAPHE LANGGRAPH
# ─────────────────────────────────────────────
def build_graph() -> StateGraph:
    graph = StateGraph(JobSearchState)
    # Ajout des nœuds
    graph.add_node("scraper",   scraper_node)
    graph.add_node("extractor", extractor_node)
    graph.add_node("analyst",   analyst_node)
    graph.add_node("coach",     coach_node)
    # Flux principal : Scraper → Extracteur → Analyste
    graph.set_entry_point("scraper")
    graph.add_edge("scraper",   "extractor")
    graph.add_edge("extractor", "analyst")
    # Routage conditionnel : Analyste → Coach (si offre sélectionnée) ou FIN
    graph.add_conditional_edges(
        "analyst",
        should_run_coach,
        {
            "run_coach":  "coach",
            "skip_coach": END,
        }
    )
    graph.add_edge("coach", END)
    return graph.compile()
# ─────────────────────────────────────────────
#  POINT D'ENTRÉE
# ─────────────────────────────────────────────
def run_pipeline(user_profile: str, selected_job: dict = None) -> JobSearchState:
    """Lance le pipeline complet"""
    app = build_graph()
    initial_state = JobSearchState(
        user_profile=user_profile,
        user_skills=[],
        raw_jobs=[],
        jobs_with_skills=[],
        selected_job=selected_job,
        compatibility_scores=[],
        best_match=None,
        quiz_questions=[],
        chat_history=[],
        current_step="start",
        errors=[]
    )
    result = app.invoke(initial_state)
    return result