"""
Agent Analyste (F4)
Calcule le score de compatibilité entre le profil utilisateur et les offres d'emploi
Utilise les embeddings vectoriels + LLM pour un scoring intelligent
"""
import os
from typing import List, Dict
from langchain_openai import OpenAIEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import numpy as np
class AnalystAgent:
    """
    Agent qui analyse la compatibilité entre le profil d'un candidat
    et les offres d'emploi collectées.
    Approche hybride :
    1. Score vectoriel (cosine similarity entre embeddings)
    2. Score LLM (analyse sémantique fine par le LLM)
    3. Score final = moyenne pondérée (40% vectoriel + 60% LLM)
    """
    SYSTEM_PROMPT = """Tu es un expert RH qui évalue la compatibilité entre un candidat et une 
offre d'emploi.
Analyse le profil du candidat par rapport aux exigences de l'offre et retourne un JSON avec :- score: nombre entier de 0 à 100 (0=aucune compatibilité, 100=parfaite correspondance)- matching_skills: liste des compétences du candidat qui correspondent à l'offre- missing_skills: liste des compétences requises que le candidat ne mentionne pas- strengths: liste de 2-3 points forts du candidat pour ce poste- recommendations: liste de 2-3 conseils pour améliorer sa candidature
Retourne UNIQUEMENT le JSON, rien d'autre."""
    ANALYSIS_PROMPT = """Évalue la compatibilité :
PROFIL CANDIDAT :
{user_profile}
OFFRE D'EMPLOI :
Titre : {job_title}
Entreprise : {company}
Description : {description}
Compétences requises : {required_skills}
Donne ton évaluation en JSON."""
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.llm = ChatGroq(
            model=model,
            temperature=0,
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human",  self.ANALYSIS_PROMPT),
        ])
        self.chain = self.prompt | self.llm | JsonOutputParser()
    # ─────────────────────────────────────────
    #  MÉTHODE PRINCIPALE
    # ─────────────────────────────────────────
    def analyze(self, user_profile: str, jobs: List[dict]) -> List[dict]:
        """
        Calcule les scores de compatibilité pour toutes les offres.
        Args:
            user_profile: Description textuelle du profil candidat
            jobs:         Offres enrichies avec compétences (venant de ExtractorAgent)
        Returns:
            Liste de dicts avec job + score + analyse détaillée, triée par score desc
        """
        print(f"   Analyse de {len(jobs)} offres...")
        # Pré-calcul : embedding du profil utilisateur (1 seul appel API)
        try:
            profile_embedding = self.embeddings.embed_query(user_profile)
        except Exception:
            profile_embedding = None
        results = []
        for job in jobs:
            try:
                analysis = self._analyze_single_job(
                    user_profile, job, profile_embedding
                )
                results.append({**job, **analysis})
            except Exception as e:
                print(f"    ⚠ Erreur analyse '{job['title']}': {e}")
                results.append({**job, "score": 0, "error": str(e)})
        # Tri par score décroissant
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        return results
    def _analyze_single_job(
        self,
        user_profile: str,
        job: dict,
        profile_embedding=None
    ) -> dict:
        """Analyse une seule offre"""
        skills = job.get("skills", {})
        required_skills_str = ", ".join(
            skills.get("hard_skills", []) + skills.get("tools", [])
        )
        # Score LLM (analyse sémantique)
        llm_result = self.chain.invoke({
            "user_profile":    user_profile,
            "job_title":       job.get("title", ""),
            "company":         job.get("company", ""),
            "description":     job.get("description", ""),
            "required_skills": required_skills_str,
        })
        # Score vectoriel (cosine similarity) si embedding disponible
        llm_score = llm_result.get("score", 50)
        vector_score = llm_score  # Fallback: on utilise le score LLM si OpenAI quota failed
        
        if profile_embedding is not None:
            try:
                job_text = f"{job.get('title', '')} {job.get('description', '')}"
                job_embedding = self.embeddings.embed_query(job_text)
                vector_score = self._cosine_similarity(profile_embedding, job_embedding) * 100
            except Exception:
                pass
                
        # Score final = 60% LLM + 40% vectoriel
        final_score = int(0.6 * llm_score + 0.4 * vector_score)
        return {
            "score":            final_score,
            "llm_score":        llm_score,
            "vector_score":     round(vector_score, 1),
            "matching_skills":  llm_result.get("matching_skills", []),
            "missing_skills":   llm_result.get("missing_skills", []),
            "strengths":        llm_result.get("strengths", []),
            "recommendations":  llm_result.get("recommendations", []),
        }
    # ─────────────────────────────────────────
    #  UTILITAIRES
    # ─────────────────────────────────────────
    @staticmethod
    def _cosine_similarity(a: list, b: list) -> float:
        """Calcule la similarité cosinus entre deux vecteurs"""
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))
    # ─────────────────────────────────────────
    #  MODE MOCK
    # ─────────────────────────────────────────
    @staticmethod
    def mock_analyze(user_profile: str, jobs: List[dict]) -> List[dict]:
        """Données fictives pour tester sans LLM"""
        scores = [85, 72, 60]
        results = []
        for i, job in enumerate(jobs):
            score = scores[i % len(scores)]
            results.append({
                **job,
                "score":           score,
                "vector_score":    score - 3,
                "llm_score":       score + 2,
                "matching_skills": ["Python", "SQL"],
                "missing_skills":  ["TensorFlow"],
                "strengths":       ["Bonne base en data science", "Profil polyvalent"],
                "recommendations": ["Renforcer les compétences en deep learning"],
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results