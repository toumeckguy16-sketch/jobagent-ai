"""
Agent Coach (F5) — Version QCM
Prépare l'utilisateur à l'entretien d'embauche via RAG + LLM
Génère un quiz QCM (3 propositions) avec correction automatique
"""
import os
from typing import List
from langchain_openai import OpenAIEmbeddings
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

CHROMA_AVAILABLE = False
try:
    from langchain_community.vectorstores import Chroma
    import chromadb
    CHROMA_AVAILABLE = True
except Exception as e:
    print(f"ChromaDB non disponible (erreur d'importation, p.ex. incompatibilite Protobuf) : {e}")
class CoachAgent:
    """
    Agent Coach utilisant RAG (Retrieval-Augmented Generation).
    Pipeline RAG :
    1. Indexation : stocke les détails de l'offre dans ChromaDB
    2. Retrieval  : récupère les passages les plus pertinents
    3. Generation : génère un QCM contextualisé (3 propositions, 1 bonne réponse)
    """
    QUIZ_SYSTEM_PROMPT = """Tu es un coach expert en préparation d'entretiens d'embauche.
En te basant sur le contexte fourni, génère un quiz QCM de préparation à l'entretien.
Chaque question a exactement 3 propositions (A, B, C) et UNE SEULE bonne réponse.
Retourne UNIQUEMENT un JSON valide avec cette structure exacte :
{{
  "questions": [
    {{
      "id": 1,
      "type": "technique",
      "difficulty": "Facile",
      "question": "La question posée ?",
      "options": {{
        "A": "Première proposition",
        "B": "Deuxième proposition",
        "C": "Troisième proposition"
      }},
      "correct_answer": "B",
      "explanation": "Explication détaillée pourquoi B est la bonne réponse, et pourquoi A et C sont incorrectes."
    }}
  ],
  "total": 15
}}
Génère exactement 15 questions variées (mélange technique, comportemental et mises en situation).
Répartis de manière équilibrée les niveaux de difficulté : Facile, Moyen, Difficile.
IMPORTANT :
- Tu dois MÉLANGER aléatoirement la position des bonnes réponses pour t'assurer que "correct_answer" est parfois A, parfois B et parfois C.
- Les mauvaises réponses doivent être plausibles mais clairement incorrectes.
- L'explication doit être pédagogique et détaillée (2-3 phrases).
- correct_answer doit être de manière stricte "A", "B" ou "C".
"""
    QUIZ_PROMPT = """Contexte de l'offre (extrait via RAG) :
{context}
Offre d'emploi :
Titre       : {job_title}
Entreprise  : {company}
Compétences : {required_skills}
Génère le quiz QCM de 15 questions."""
    # ── Prompt Chat ───────────────────────────────────────────────
    CHAT_SYSTEM_PROMPT = """Tu es un coach bienveillant et expert en entretiens d'embauche.
Tu aides un candidat à préparer son entretien pour le poste de {job_title} chez {company}.
Contexte de l'offre : {job_context}
Réponds de façon constructive, encourage le candidat et donne des exemples concrets.
"""
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.llm = ChatGroq(
            model=model,
            temperature=0.3,
            api_key=os.getenv("GROQ_API_KEY")
        )
        self.embeddings = OpenAIEmbeddings(
            api_key=os.getenv("OPENAI_API_KEY")
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500, chunk_overlap=50
        )
        self.chroma_dir  = "./data/chroma_db"
        self.vectorstore = None
        self.raw_job_text = ""
    # ─────────────────────────────────────────
    #  GÉNÉRATION DU QUIZ QCM
    # ─────────────────────────────────────────
    def generate_quiz(self, job: dict, candidate_profile: dict = None) -> List[dict]:
        """
        Génère un quiz QCM de 15 questions pour une offre donnée,
        en tenant compte du profil du candidat pour personnaliser les questions.
        """
        self._index_job(job)

        query   = f"compétences requises entretien {job.get('title', '')}"
        context = self._retrieve_context(query, k=3)
        skills         = job.get("skills", {})
        required_skills = ", ".join(
            skills.get("hard_skills", []) + skills.get("tools", [])
        )

        # Ajout des expériences du candidat dans le prompt
        candidate_exp_text = ""
        if candidate_profile and candidate_profile.get("experiences"):
            candidate_exp_text = "\nExpériences du candidat :\n"
            for exp in candidate_profile["experiences"]:
                candidate_exp_text += f"- {exp.get('title')} chez {exp.get('company')} ({exp.get('period')}): {exp.get('description')}\n"

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.QUIZ_SYSTEM_PROMPT),
            ("human",  self.QUIZ_PROMPT + candidate_exp_text),
        ])
        chain  = prompt | self.llm | JsonOutputParser()
        result = chain.invoke({
            "context":         context,
            "job_title":       job.get("title", ""),
            "company":         job.get("company", ""),
            "required_skills": required_skills,
        })
        return result.get("questions", [])

    # ─────────────────────────────────────────
    #  CHAT INTERACTIF
    # ─────────────────────────────────────────
    def chat(self, user_message: str, job: dict, history: List[dict] = None, candidate_profile: dict = None) -> str:
        context    = self._retrieve_context(user_message, k=2)
        skills     = job.get("skills", {})
        job_context = (
            f"Compétences requises : {', '.join(skills.get('hard_skills', []))}\n"
            f"Description : {job.get('description', '')[:300]}"
        )
        
        # Enrichissement avec les expériences du candidat
        candidate_context = ""
        if candidate_profile and candidate_profile.get("experiences"):
            candidate_context = "\nExpériences professionnelles du candidat :\n"
            for exp in candidate_profile["experiences"]:
                candidate_context += f"- {exp.get('title')} chez {exp.get('company')} ({exp.get('period')}): {exp.get('description')}\n"

        messages = [
            ("system", self.CHAT_SYSTEM_PROMPT.format(
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                job_context=job_context + candidate_context
            ))
        ]
        if history:
            for msg in history[-6:]:
                messages.append((msg["role"], msg["content"]))
        messages.append(("human", f"Contexte RAG : {context}\n\nQuestion / Réponse : {user_message}"))
        prompt   = ChatPromptTemplate.from_messages(messages)
        chain    = prompt | self.llm
        response = chain.invoke({})
        return response.content

    def init_interview(self, job: dict, candidate_profile: dict = None) -> str:
        """Génère le message de bienvenue pour l'entretien virtuel"""
        skills = job.get("skills", {})
        hard_skills = ", ".join(skills.get("hard_skills", []))
        
        # Enrichissement avec les expériences du candidat
        candidate_context = ""
        if candidate_profile and candidate_profile.get("experiences"):
            candidate_context = "\nVoici les expériences du candidat pour t'aider à personnaliser ta première question :\n"
            for exp in candidate_profile["experiences"]:
                candidate_context += f"- {exp.get('title')} chez {exp.get('company')} ({exp.get('period')}): {exp.get('description')}\n"

        prompt_system = f"""Tu es un recruteur bienveillant et expert. Tu accueilles chaleureusement le candidat pour son entretien pour le poste de {job.get('title', 'ce poste')} chez {job.get('company', 'notre structure')}.
Fais une courte introduction (1-2 phrases) et pose ta première question ouverte. 
IMPORTANT : Utilise les expériences passées du candidat (si fournies) pour rendre ta question plus pertinente et personnalisée par rapport aux compétences requises ({hard_skills}). 
{candidate_context}
Attends ensuite sa réponse. Ne pose pas plusieurs questions à la fois."""
        
        chain = ChatPromptTemplate.from_messages([("system", prompt_system)]) | self.llm
        return chain.invoke({}).content
    # ─────────────────────────────────────────
    #  RAG : INDEXATION & RETRIEVAL
    # ─────────────────────────────────────────
    def _index_job(self, job: dict):
        skills   = job.get("skills", {})
        job_text = f"""
Poste : {job.get('title', '')}
Entreprise : {job.get('company', '')}
Localisation : {job.get('location', '')}
Description : {job.get('description', '')}
Compétences techniques : {', '.join(skills.get('hard_skills', []))}
Compétences comportementales : {', '.join(skills.get('soft_skills', []))}
Outils : {', '.join(skills.get('tools', []))}
Expérience requise : {skills.get('experience_years', 0)} ans
Niveau d'éducation : {skills.get('education_level', '')}
Langues : {', '.join(skills.get('languages', []))}
"""
        self.raw_job_text = job_text
        if not CHROMA_AVAILABLE:
            self.vectorstore = None
            return

        try:
            docs = self.text_splitter.create_documents(
                [job_text],
                metadatas=[{"source": "job_offer", "title": job.get("title", "")}]
            )
            self.vectorstore = Chroma.from_documents(
                documents=docs,
                embedding=self.embeddings,
                persist_directory=self.chroma_dir,
                collection_name="job_offers"
            )
        except Exception as e:
            print(f"Indexation ignoree (Erreur quota ?) : {e}")
            self.vectorstore = None

    def _retrieve_context(self, query: str, k: int = 3) -> str:
        if not self.vectorstore:
            return self.raw_job_text
        try:
            docs = self.vectorstore.similarity_search(query, k=k)
            return "\n---\n".join([doc.page_content for doc in docs])
        except Exception:
            return self.raw_job_text
    # ─────────────────────────────────────────
    #  MODE MOCK — QCM fictif
    # ─────────────────────────────────────────
    @staticmethod
    def mock_generate_quiz(job: dict) -> List[dict]:
        """Quiz QCM fictif pour tester sans LLM"""
        company = job.get("company", "l'entreprise")
        return [
            {
                "id": 1,
                "type": "technique",
                "question": "Quelle bibliothèque Python est la plus adaptée pour manipuler des données tabulaires ?",
                "options": {
                    "A": "pandas",
                    "B": "matplotlib",
                    "C": "requests"
                },
                "correct_answer": "A",
                "explanation": "pandas est la bibliothèque de référence pour la manipulation de données tabulaires en Python (DataFrames). matplotlib sert à la visualisation, et requests à faire des requêtes HTTP."
            },
            {
                "id": 2,
                "type": "technique",
                "question": "Qu'est-ce que le surapprentissage (overfitting) en Machine Learning ?",
                "options": {
                    "A": "Le modèle apprend trop lentement sur les données d'entraînement",
                    "B": "Le modèle performe bien sur les données d'entraînement mais mal sur de nouvelles données",
                    "C": "Le modèle utilise trop de mémoire RAM pendant l'entraînement"
                },
                "correct_answer": "B",
                "explanation": "L'overfitting signifie que le modèle a mémorisé les données d'entraînement au lieu d'apprendre des patterns généralisables. Il performe donc très bien en entraînement mais échoue sur des données inédites. On le combat avec la régularisation, le dropout ou plus de données."
            },
            {
                "id": 3,
                "type": "comportemental",
                "question": "Face à un désaccord technique avec un collègue senior, quelle est la meilleure approche ?",
                "options": {
                    "A": "Céder immédiatement pour éviter le conflit",
                    "B": "Imposer votre point de vue car vous êtes certain d'avoir raison",
                    "C": "Présenter vos arguments avec des données, écouter son point de vue et chercher un consensus"
                },
                "correct_answer": "C",
                "explanation": "La meilleure approche est de s'appuyer sur des faits et données pour argumenter, tout en restant ouvert à la perspective du collègue. Cette attitude démontre maturité professionnelle et esprit d'équipe, des qualités très appréciées en entreprise."
            },
            {
                "id": 4,
                "type": "comportemental",
                "question": "Comment gérez-vous plusieurs tâches urgentes simultanément ?",
                "options": {
                    "A": "Je traite toutes les tâches en même temps pour aller plus vite",
                    "B": "Je priorise selon l'impact et l'urgence, je communique sur les délais et je livre par étapes",
                    "C": "Je travaille uniquement sur la tâche la plus difficile en premier"
                },
                "correct_answer": "B",
                "explanation": "La priorisation par impact/urgence (matrice d'Eisenhower) combinée à une communication transparente sur les délais est la méthode la plus efficace. Elle démontre organisation, sens des responsabilités et professionnalisme."
            },
            {
                "id": 5,
                "type": "mise_en_situation",
                "question": f"Vous rejoignez {company} et on vous demande d'analyser la qualité des données d'un nouveau dataset. Par où commencez-vous ?",
                "options": {
                    "A": "Je lance directement un modèle ML pour voir les résultats",
                    "B": "J'effectue une analyse exploratoire (EDA) : valeurs manquantes, distributions, outliers, types de données",
                    "C": "Je supprime toutes les lignes avec des valeurs manquantes avant de commencer"
                },
                "correct_answer": "B",
                "explanation": "L'analyse exploratoire (EDA) est l'étape incontournable avant tout traitement. Elle permet de comprendre la structure des données, détecter les anomalies et prendre des décisions éclairées sur le nettoyage. Lancer un modèle sans EDA ou supprimer aveuglément des données sont des erreurs méthodologiques graves."
            }
        ]