"""
Agent Extracteur (F3)
Extrait automatiquement les compétences requises dans chaque offre d'emploi.
Utilise Ollama pour faire tourner un modèle LLM en LOCAL (zéro coût, zéro API).
"""
import os
import re
import json
from typing import List
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

# ─────────────────────────────────────────────
#  SCHÉMA DE SORTIE STRUCTURÉ (Pydantic)
# ─────────────────────────────────────────────
class JobSkills(BaseModel):
    """Schéma Pydantic pour la sortie structurée de l'extracteur"""
    hard_skills:      List[str] = Field(description="Compétences techniques (Python...)")
    soft_skills:      List[str] = Field(description="Compétences comportementales")
    experience_years: int       = Field(description="Années d'expérience")
    education_level:  str       = Field(description="Niveau d'étude")
    languages:        List[str] = Field(description="Langues requises")
    tools:            List[str] = Field(description="Outils spécifiques")

# ─────────────────────────────────────────────
#  AGENT EXTRACTEUR — Ollama (local)
# ─────────────────────────────────────────────
class ExtractorAgent:
    """
    Agent qui analyse chaque offre d'emploi et en extrait
    les compétences de façon structurée via un modèle local Ollama.
    """
    DEFAULT_MODEL = "minimax-m2.5"
    
    # NOTE : Les accolades littérales doivent être doublées {{ }} pour éviter 
    # que LangChain ne les interprète comme des variables de prompt.
    SYSTEM_PROMPT = """Tu es un expert RH spécialisé dans l'analyse d'offres d'emploi.
Ton rôle est d'extraire de façon précise et structurée toutes les compétences
mentionnées dans une description de poste.
Retourne UNIQUEMENT un objet JSON valide, sans aucun texte avant ou après.
Ne mets pas de ```json. Commence directement par {{ et termine par }}.
Structure JSON attendue :
{{
  "hard_skills": ["compétence1", "compétence2"],
  "soft_skills": ["compétence1", "compétence2"],
  "experience_years": 0,
  "education_level": "Master",
  "languages": ["Français", "Anglais"],
  "tools": ["outil1", "outil2"]
}}"""

    EXTRACTION_PROMPT = """Analyse cette offre d'emploi et extrais toutes les compétences :
Titre du poste : {title}
Entreprise     : {company}
Description    : {description}
Retourne le JSON structuré."""

    def __init__(self, model: str = None, base_url: str = None):
        self.model_name = model or os.getenv("OLLAMA_MODEL", self.DEFAULT_MODEL)
        self.base_url   = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm = ChatOllama(
            model       = self.model_name,
            base_url    = self.base_url,
            temperature = 0,
            format      = "json",
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human",  self.EXTRACTION_PROMPT),
        ])
        self.chain = self.prompt | self.llm | JsonOutputParser()

    def extract_skills(self, jobs: List[dict]) -> List[dict]:
        enriched_jobs = []
        for job in jobs:
            try:
                print(f"    [Ollama/{self.model_name}] Extraction : {job['title']} @ {job['company']}")
                skills       = self._extract_from_job(job)
                enriched_job = {**job, "skills": skills}
                enriched_jobs.append(enriched_job)
            except Exception as e:
                print(f"    ⚠Erreur extraction pour '{job['title']}': {e}")
                enriched_jobs.append({**job, "skills": self._empty_skills()})
        return enriched_jobs

    def _extract_from_job(self, job: dict) -> dict:
        raw_result = self.chain.invoke({
            "title":       job.get("title", ""),
            "company":     job.get("company", ""),
            "description": job.get("description", ""),
        })
        return self._validate_and_normalize(raw_result)

    def _validate_and_normalize(self, raw: dict) -> dict:
        normalized = {
            "hard_skills":      self._to_list(raw.get("hard_skills", [])),
            "soft_skills":      self._to_list(raw.get("soft_skills", [])),
            "experience_years": self._to_int(raw.get("experience_years", 0)),
            "education_level":  str(raw.get("education_level", "")),
            "languages":        self._to_list(raw.get("languages", [])),
            "tools":            self._to_list(raw.get("tools", [])),
        }
        return normalized

    @staticmethod
    def _to_list(value) -> List[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if v]
        if isinstance(value, str) and value.strip():
            return [v.strip() for v in value.split(",") if v.strip()]
        return []

    @staticmethod
    def _to_int(value) -> int:
        try: return int(value)
        except (ValueError, TypeError):
            match = re.search(r'\d+', str(value))
            return int(match.group()) if match else 0

    @staticmethod
    def _empty_skills() -> dict:
        return {
            "hard_skills": [], "soft_skills": [],
            "experience_years": 0, "education_level": "",
            "languages": [], "tools": []
        }

    @staticmethod
    def mock_extract(jobs: List[dict]) -> List[dict]:
        mock_skills = {
            "hard_skills":      ["Python", "Machine Learning", "SQL"],
            "soft_skills":      ["Communication"],
            "experience_years": 2,
            "education_level":  "Master",
            "languages":        ["Français"],
            "tools":            ["Git"]
        }
        return [{**job, "skills": mock_skills} for job in jobs]
