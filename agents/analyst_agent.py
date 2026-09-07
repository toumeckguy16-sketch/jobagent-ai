"""
Agent Analyste (F4)
Calcule le score de compatibilité entre le profil utilisateur et les offres d'emploi
Utilise les embeddings vectoriels + LLM pour un scoring intelligent
"""
import os
from typing import List, Dict
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
import numpy as np

from utils.llm_response import make_chat_groq, invoke_json


class AnalystAgent:
    """
    Agent qui analyse la compatibilité entre le profil d'un candidat
    et les offres d'emploi collectées.
    Approche hybride :
    1. Score vectoriel (cosine similarity entre embeddings)
    2. Score LLM (analyse sémantique fine par le LLM)
    3. Score final = moyenne pondérée (40% vectoriel + 60% LLM)
    """

    SYSTEM_PROMPT = """Tu es un expert RH et coach en recrutement qui évalue avec rigueur la compatibilité entre un candidat et une offre d'emploi.
Analyse le profil du candidat par rapport aux exigences de l'offre et retourne un JSON avec :
- score: nombre entier de 0 à 100 (0=aucune compatibilité, 100=parfaite correspondance) reflétant fidèlement l'adéquation globale (compétences techniques, outils, niveau d'expérience)
- matching_skills: liste des compétences et outils du candidat qui correspondent aux exigences de l'offre
- missing_skills: liste des compétences techniques ou outils requis par l'offre que le candidat ne possède pas
- strengths: liste de 2-3 points forts concrets du candidat pour ce poste
- recommendations: liste de 3-4 conseils concrets et personnalisés du coach pour combler les écarts (mise en valeur de réalisations similaires, compétences à renforcer rapidement, conseils de candidature)
Retourne UNIQUEMENT le JSON, rien d'autre."""

    ANALYSIS_PROMPT = """Évalue la compatibilité :
PROFIL CANDIDAT :
{user_profile}

OFFRE D'EMPLOI :
Titre : {job_title}
Entreprise : {company}
Description : {description}
Compétences requises : {required_skills}

Donne ton évaluation en JSON structuré."""

    def __init__(self, model: str = "qwen/qwen3.6-27b"):
        # make_chat_groq active reasoning_effort=none pour Qwen → pas de thinking dans la réponse
        self.llm = make_chat_groq(
            temperature=0,
            model=model,
            max_tokens=1024,
        )
        # Embeddings optionnels (évite crash si OPENAI_API_KEY absent)
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            try:
                self.embeddings = OpenAIEmbeddings(api_key=openai_key)
            except Exception:
                self.embeddings = None
        else:
            self.embeddings = None

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human",  self.ANALYSIS_PROMPT),
        ])

    @staticmethod
    def _format_candidate_profile(user_profile: str, candidate_profile: dict = None) -> str:
        """Combine la description textuelle avec les compétences structurées du CV"""
        if not candidate_profile or not isinstance(candidate_profile, dict):
            return user_profile or "Profil candidat non spécifié"

        parts = []
        title = candidate_profile.get("job_title")
        if title and str(title).strip().lower() not in ("profil saisi", "candidat", "none", ""):
            parts.append(f"Titre visé / Métier : {title}")

        exp_years = candidate_profile.get("experience_years")
        if exp_years:
            parts.append(f"Années d'expérience : {exp_years} an(s)")

        edu = candidate_profile.get("education_level")
        if edu:
            parts.append(f"Niveau d'études : {edu}")

        hard = candidate_profile.get("hard_skills") or []
        tools = candidate_profile.get("tools") or []
        if isinstance(hard, str): hard = [hard]
        if isinstance(tools, str): tools = [tools]
        all_skills = [str(s).strip() for s in (hard + tools) if s and str(s).strip()]
        if all_skills:
            parts.append(f"Compétences & Outils maîtrisés : {', '.join(all_skills[:15])}")

        if user_profile and user_profile.strip():
            parts.append(f"Description du profil : {user_profile.strip()[:400]}")

        return "\n".join(parts) if parts else (user_profile or "Profil candidat non spécifié")

    # ─────────────────────────────────────────
    #  MÉTHODE PRINCIPALE
    # ─────────────────────────────────────────
    def analyze(self, user_profile: str, jobs: List[dict], candidate_profile: dict = None) -> List[dict]:
        """
        Calcule les scores de compatibilité pour toutes les offres.
        Args:
            user_profile: Description textuelle du profil candidat
            jobs:         Offres enrichies avec compétences (venant de ExtractorAgent)
            candidate_profile: Profil structuré du candidat (CV complet)
        Returns:
            Liste de dicts avec job + score + analyse détaillée, triée par score desc
        """
        print(f"   Analyse de {len(jobs)} offres...")
        full_candidate_desc = self._format_candidate_profile(user_profile, candidate_profile)

        # Pré-calcul : embedding du profil utilisateur (1 seul appel API si dispo)
        profile_embedding = None
        if self.embeddings:
            try:
                profile_embedding = self.embeddings.embed_query(full_candidate_desc)
            except Exception:
                profile_embedding = None

        results = []
        for job in jobs:
            try:
                analysis = self._analyze_single_job(
                    full_candidate_desc, job, profile_embedding
                )
                results.append({**job, **analysis})
            except Exception as e:
                print(f"    ⚠ Erreur analyse '{job.get('title', 'Offre')}': {e}")
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
        hard_skills = skills.get("hard_skills", [])
        tools = skills.get("tools", [])
        req_list = [s for s in (hard_skills + tools) if s]
        required_skills_str = ", ".join(req_list) if req_list else "Non spécifiées explicitement"

        # Score LLM (analyse sémantique) via invoke_json — gère le thinking Qwen
        try:
            llm_result = invoke_json(self.llm, self.prompt.format_messages(
                user_profile=user_profile,
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                description=(job.get("description") or "")[:800],
                required_skills=required_skills_str,
            ))
        except Exception as e:
            print(f"    ⚠ Parsing JSON analyst échoué : {e}. Fallback score=50.")
            llm_result = {}

        # Extraction et validation du score (plage 0-100)
        raw_score = llm_result.get("score", 50)
        try:
            llm_score = max(0, min(100, int(raw_score)))
        except (TypeError, ValueError):
            llm_score = 50

        # Score vectoriel (cosine similarity) si embedding disponible
        vector_score = None
        if self.embeddings and profile_embedding is not None:
            try:
                job_text = f"{job.get('title', '')} {job.get('description', '')[:500]}"
                job_embedding = self.embeddings.embed_query(job_text)
                vector_score = self._cosine_similarity(profile_embedding, job_embedding) * 100
                vector_score = max(0, min(100, vector_score))
            except Exception:
                vector_score = None

        # Score final : 60% LLM + 40% vectoriel si dispo, sinon 100% LLM
        if vector_score is not None:
            final_score = int(0.6 * llm_score + 0.4 * vector_score)
            vec_display = round(vector_score, 1)
        else:
            final_score = llm_score
            vec_display = llm_score

        return {
            "score":            final_score,
            "llm_score":        llm_score,
            "vector_score":     vec_display,
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