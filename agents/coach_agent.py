"""
Agent Coach (F5) — Version QCM
Prépare l'utilisateur à l'entretien d'embauche via RAG + LLM
Génère un quiz QCM (3 propositions) avec correction automatique
"""
import os
import re
from typing import List
from langchain_openai import OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from utils.llm_response import make_chat_groq, extract_final_content, invoke_json

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

    # ── Prompt Quiz ────────────────────────────────────────────────
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

    # Prompt pour la 2e passe (complétion)
    QUIZ_COMPLETION_PROMPT = """Contexte de l'offre :
{context}
Offre d'emploi :
Titre       : {job_title}
Entreprise  : {company}
Compétences : {required_skills}

Des questions ont déjà été générées (ids {existing_ids}).
Génère UNIQUEMENT {remaining} questions NOUVELLES (différentes des précédentes), à partir de l'id {start_id}.
Questions déjà générées (ne PAS les reproduire) :
{existing_questions_summary}
Retourne UNIQUEMENT le JSON avec la liste des {remaining} nouvelles questions."""

    # ── Prompt Chat ───────────────────────────────────────────────
    CHAT_SYSTEM_PROMPT = """Tu es un coach bienveillant et expert en entretiens d'embauche.
Tu aides un candidat à préparer son entretien pour le poste de {job_title} chez {company}.
Contexte de l'offre : {job_context}
Réponds de façon constructive, encourage le candidat et donne des exemples concrets.
"""

    def __init__(self, model: str = "qwen/qwen3.6-27b"):
        # Utilisation de make_chat_groq() pour activer reasoning_effort=none
        # → supprime le raisonnement interne de la réponse Qwen
        self.llm = make_chat_groq(
            temperature=0.3,
            model=model,
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
        self._model = model

    # ─────────────────────────────────────────
    #  GÉNÉRATION DU QUIZ QCM
    # ─────────────────────────────────────────
    def generate_quiz(self, job: dict, candidate_profile: dict = None) -> List[dict]:
        """
        Génère un quiz QCM de 15 questions pour une offre donnée,
        en tenant compte du profil du candidat pour personnaliser les questions.
        Utilise une logique de 2 passes si la première ne produit pas 15 questions.
        """
        self._index_job(job)

        query   = f"compétences requises entretien {job.get('title', '')}"
        context = self._retrieve_context(query, k=3)
        skills  = job.get("skills", {})
        required_skills = ", ".join(
            skills.get("hard_skills", []) + skills.get("tools", [])
        )

        # Ajout des expériences du candidat dans le prompt
        candidate_exp_text = ""
        if candidate_profile and candidate_profile.get("experiences"):
            candidate_exp_text = "\nExpériences du candidat :\n"
            for exp in candidate_profile["experiences"]:
                candidate_exp_text += f"- {exp.get('title')} chez {exp.get('company')} ({exp.get('period')}): {exp.get('description')}\n"

        # LLM dédié au quiz avec max_tokens élevé pour recevoir 15 questions complètes
        quiz_llm = make_chat_groq(
            temperature=0.7,
            max_tokens=8192,
            model=self._model,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.QUIZ_SYSTEM_PROMPT),
            ("human",  self.QUIZ_PROMPT + candidate_exp_text),
        ])

        try:
            result = invoke_json(quiz_llm, prompt.format_messages(
                context=context,
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                required_skills=required_skills,
            ))
            questions = result.get("questions", [])

            # Validation des questions (structure minimale)
            questions = [q for q in questions if self._is_valid_question(q)]

            print(f"[CoachAgent] 1ère passe : {len(questions)} question(s) générée(s).")

            # 2e passe si moins de 15 questions
            if len(questions) < 15:
                questions = self._complete_quiz(
                    questions=questions,
                    quiz_llm=quiz_llm,
                    context=context,
                    job=job,
                    required_skills=required_skills,
                    candidate_exp_text=candidate_exp_text,
                )

            # Complétion finale avec le mock si toujours insuffisant
            if len(questions) < 15:
                print(f"[CoachAgent] Complétion mock : {15 - len(questions)} question(s).")
                mock_qs = self.mock_generate_quiz(job)
                existing_texts = {q.get("question", "").lower() for q in questions}
                for mq in mock_qs:
                    if mq.get("question", "").lower() not in existing_texts:
                        mq["id"] = len(questions) + 1
                        questions.append(mq)
                        if len(questions) >= 15:
                            break

            # On tronque à exactement 15 si plus
            questions = questions[:15]

            # Réindexation des ids
            for i, q in enumerate(questions):
                q["id"] = i + 1

            return questions

        except Exception as e:
            print(f"Erreur lors de la génération du quiz : {e}")
            return self.mock_generate_quiz(job)

    def _complete_quiz(
        self,
        questions: List[dict],
        quiz_llm,
        context: str,
        job: dict,
        required_skills: str,
        candidate_exp_text: str,
    ) -> List[dict]:
        """
        2e passe : complète le quiz pour atteindre 15 questions.
        """
        remaining = 15 - len(questions)
        start_id  = len(questions) + 1
        existing_ids = [q.get("id", i + 1) for i, q in enumerate(questions)]
        existing_summary = "\n".join(
            f"- (id {q.get('id', '')}) {q.get('question', '')}" for q in questions
        )

        completion_prompt = ChatPromptTemplate.from_messages([
            ("system", self.QUIZ_SYSTEM_PROMPT),
            ("human",  self.QUIZ_COMPLETION_PROMPT + candidate_exp_text),
        ])

        try:
            result = invoke_json(quiz_llm, completion_prompt.format_messages(
                context=context,
                job_title=job.get("title", ""),
                company=job.get("company", ""),
                required_skills=required_skills,
                existing_ids=existing_ids,
                remaining=remaining,
                start_id=start_id,
                existing_questions_summary=existing_summary,
            ))
            new_questions = result.get("questions", [])
            # Si la réponse est une liste directe
            if not new_questions and isinstance(result, list):
                new_questions = result

            new_questions = [q for q in new_questions if self._is_valid_question(q)]

            # Dédupliquer par texte
            existing_texts = {q.get("question", "").lower() for q in questions}
            for nq in new_questions:
                if nq.get("question", "").lower() not in existing_texts:
                    questions.append(nq)
                    existing_texts.add(nq.get("question", "").lower())
                    if len(questions) >= 15:
                        break

            print(f"[CoachAgent] 2e passe : total {len(questions)} question(s).")
        except Exception as e:
            print(f"[CoachAgent] Erreur 2e passe quiz : {e}")

        return questions

    @staticmethod
    def _is_valid_question(q: dict) -> bool:
        """Vérifie qu'une question a la structure minimale requise."""
        if not isinstance(q, dict):
            return False
        if not q.get("question"):
            return False
        options = q.get("options", {})
        if not isinstance(options, dict) or not all(k in options for k in ("A", "B", "C")):
            return False
        if q.get("correct_answer") not in ("A", "B", "C"):
            return False
        return True

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
        # Extraction de la réponse finale uniquement (supprime le raisonnement Qwen)
        return extract_final_content(response)

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

        # Groq/Qwen exige au moins un message "human" — on ajoute un déclencheur neutre
        chain = ChatPromptTemplate.from_messages([
            ("system", prompt_system),
            ("human", "Commence l'entretien."),
        ]) | self.llm
        try:
            response = chain.invoke({})
            # Extraction de la réponse finale uniquement (supprime le raisonnement Qwen)
            return extract_final_content(response)
        except Exception as e:
            print(f"Erreur init_interview : {e}")
            return f"Bonjour ! Je suis ravi de vous accueillir pour cet entretien concernant le poste de **{job.get('title', 'ce poste')}** chez **{job.get('company', 'notre structure')}**. Pouvez-vous commencer par me parler de votre parcours et de ce qui vous a motivé à postuler ?"

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
                "difficulty": "Facile",
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
                "difficulty": "Moyen",
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
                "difficulty": "Facile",
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
                "difficulty": "Moyen",
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
                "difficulty": "Difficile",
                "question": f"Vous rejoignez {company} et on vous demande d'analyser la qualité des données d'un nouveau dataset. Par où commencez-vous ?",
                "options": {
                    "A": "Je lance directement un modèle ML pour voir les résultats",
                    "B": "J'effectue une analyse exploratoire (EDA) : valeurs manquantes, distributions, outliers, types de données",
                    "C": "Je supprime toutes les lignes avec des valeurs manquantes avant de commencer"
                },
                "correct_answer": "B",
                "explanation": "L'analyse exploratoire (EDA) est l'étape incontournable avant tout traitement. Elle permet de comprendre la structure des données, détecter les anomalies et prendre des décisions éclairées sur le nettoyage. Lancer un modèle sans EDA ou supprimer aveuglément des données sont des erreurs méthodologiques graves."
            },
            {
                "id": 6,
                "type": "technique",
                "difficulty": "Moyen",
                "question": "Quelle est la différence entre un processus et un thread en programmation ?",
                "options": {
                    "A": "Un processus est plus léger qu'un thread et partage la même mémoire",
                    "B": "Un processus a son propre espace mémoire ; un thread partage l'espace mémoire du processus parent",
                    "C": "Il n'y a aucune différence fonctionnelle entre un processus et un thread"
                },
                "correct_answer": "B",
                "explanation": "Un processus dispose de son propre espace mémoire isolé, tandis qu'un thread est une unité d'exécution légère au sein d'un processus, partageant la mémoire avec les autres threads du même processus. Les threads sont plus légers mais nécessitent une gestion de la concurrence (locks, semaphores)."
            },
            {
                "id": 7,
                "type": "technique",
                "difficulty": "Difficile",
                "question": "Qu'est-ce que le principe SOLID en développement logiciel ?",
                "options": {
                    "A": "Un ensemble de 5 principes de conception orientée objet pour produire un code maintenable et évolutif",
                    "B": "Un framework de tests unitaires très populaire en Java",
                    "C": "Un protocole de communication entre microservices"
                },
                "correct_answer": "A",
                "explanation": "SOLID est un acronyme pour 5 principes : Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. Ces principes guident la conception de logiciels robustes, maintenables et facilement extensibles, indépendamment du langage utilisé."
            },
            {
                "id": 8,
                "type": "comportemental",
                "difficulty": "Difficile",
                "question": "Comment réagissez-vous face à un feedback négatif de votre manager sur un travail que vous jugez de qualité ?",
                "options": {
                    "A": "Je défends fermement mon travail et explique pourquoi le feedback est injuste",
                    "B": "J'accepte le feedback sans chercher à comprendre les raisons",
                    "C": "J'écoute activement, je pose des questions pour comprendre les attentes, puis j'ajuste mon travail"
                },
                "correct_answer": "C",
                "explanation": "La capacité à recevoir et intégrer le feedback est une compétence clé. L'écoute active permet de comprendre la perspective du manager, les questions clarificatrices permettent d'aligner les attentes, et l'ajustement démontre agilité et professionnalisme. Défendre son travail sans écoute crée des tensions inutiles."
            },
            {
                "id": 9,
                "type": "mise_en_situation",
                "difficulty": "Moyen",
                "question": "Un client signale un bug critique en production le vendredi à 17h. Que faites-vous ?",
                "options": {
                    "A": "Je laisse le problème pour lundi car c'est la fin de la semaine",
                    "B": "J'évalue la criticité, informe les parties prenantes, applique un correctif ou un contournement, puis documente l'incident",
                    "C": "Je demande au client de patienter jusqu'à la prochaine release prévue"
                },
                "correct_answer": "B",
                "explanation": "Face à un incident critique, la priorité est de minimiser l'impact. Il faut évaluer rapidement la gravité, communiquer avec les parties prenantes, appliquer un correctif immédiat ou un workaround, puis documenter l'incident pour éviter qu'il ne se reproduise. Ignorer le problème ou demander d'attendre nuit gravement à la relation client."
            },
            {
                "id": 10,
                "type": "technique",
                "difficulty": "Facile",
                "question": "Qu'est-ce qu'une API REST ?",
                "options": {
                    "A": "Un langage de programmation orienté web",
                    "B": "Une interface permettant la communication entre applications via des requêtes HTTP standardisées",
                    "C": "Un système de gestion de base de données relationnelle"
                },
                "correct_answer": "B",
                "explanation": "Une API REST (Representational State Transfer) est une interface permettant à différentes applications de communiquer via HTTP en utilisant des méthodes standardisées (GET, POST, PUT, DELETE). Elle est stateless, ce qui signifie que chaque requête contient toutes les informations nécessaires à son traitement."
            },
            {
                "id": 11,
                "type": "comportemental",
                "difficulty": "Facile",
                "question": "Comment décrieriez-vous votre méthode de travail en équipe ?",
                "options": {
                    "A": "Je préfère travailler seul car je suis plus productif",
                    "B": "Je communique régulièrement, partage mes avancées et n'hésite pas à demander de l'aide si nécessaire",
                    "C": "Je délègue un maximum de tâches pour me concentrer sur les décisions importantes"
                },
                "correct_answer": "B",
                "explanation": "Un bon travail d'équipe repose sur la communication transparente, le partage des informations et la capacité à demander ou offrir de l'aide. Cette approche favorise la cohésion, évite les blocages et maximise la productivité collective. Travailler en silo ou déléguer à l'excès nuit à la dynamique d'équipe."
            },
            {
                "id": 12,
                "type": "mise_en_situation",
                "difficulty": "Difficile",
                "question": f"Vous devez intégrer une nouvelle technologie dans le système existant de {company}. Comment procédez-vous ?",
                "options": {
                    "A": "Je l'intègre directement en production pour gagner du temps",
                    "B": "J'évalue la compatibilité, je crée un prototype, je teste en environnement de staging, puis je déploie progressivement",
                    "C": "Je remplace entièrement l'ancien système par le nouveau en une seule fois"
                },
                "correct_answer": "B",
                "explanation": "L'intégration progressive d'une nouvelle technologie minimise les risques. L'évaluation de compatibilité prévient les conflits, le prototype valide la faisabilité, les tests en staging détectent les problèmes avant la production, et le déploiement progressif permet un rollback rapide si nécessaire. Les approches tout-ou-rien sont risquées."
            },
            {
                "id": 13,
                "type": "technique",
                "difficulty": "Moyen",
                "question": "Quelle est la complexité temporelle d'une recherche dans un tableau trié avec la recherche binaire ?",
                "options": {
                    "A": "O(n) — linéaire",
                    "B": "O(n²) — quadratique",
                    "C": "O(log n) — logarithmique"
                },
                "correct_answer": "C",
                "explanation": "La recherche binaire divise l'espace de recherche par 2 à chaque itération, ce qui donne une complexité en O(log n). C'est bien plus efficace qu'une recherche linéaire O(n) sur de grands tableaux. Elle nécessite cependant que le tableau soit préalablement trié."
            },
            {
                "id": 14,
                "type": "comportemental",
                "difficulty": "Moyen",
                "question": "Vous avez un délai très serré et réalisez que vous ne pourrez pas terminer toutes les tâches demandées. Que faites-vous ?",
                "options": {
                    "A": "Je livre un travail incomplet sans prévenir et j'espère que personne ne remarquera",
                    "B": "Je travaille toute la nuit sans en informer personne pour tout terminer",
                    "C": "J'informe mon manager dès que possible, je priorise les éléments critiques et je propose un plan de livraison réaliste"
                },
                "correct_answer": "C",
                "explanation": "La transparence face aux contraintes de délai est primordiale. Informer son manager tôt permet d'ajuster les priorités collectivement, de réaffecter des ressources si nécessaire et de maintenir la confiance. Livrer en cachette un travail incomplet ou s'épuiser inutilement sont deux erreurs qui nuisent à la qualité et à la relation professionnelle."
            },
            {
                "id": 15,
                "type": "mise_en_situation",
                "difficulty": "Difficile",
                "question": "Un membre de votre équipe produit régulièrement un travail de mauvaise qualité. Comment gérez-vous la situation ?",
                "options": {
                    "A": "Je fais son travail à sa place pour ne pas retarder le projet",
                    "B": "Je l'ignore et espère que le manager s'en rende compte",
                    "C": "Je lui fais un retour privé et constructif, je propose de l'aider, et j'escalade au manager si la situation ne s'améliore pas"
                },
                "correct_answer": "C",
                "explanation": "La gestion des problèmes de qualité dans une équipe nécessite diplomatie et constructivité. Un feedback privé et bienveillant permet au collègue de comprendre les attentes et de progresser. Proposer de l'aide montre la solidarité. Si la situation persiste malgré tout, l'escalade au manager devient nécessaire pour protéger le projet et l'équipe."
            },
        ]