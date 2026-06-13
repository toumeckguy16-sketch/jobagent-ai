"""
Agent Scraper (F2)
Collecte automatiquement les offres d'emploi via l'API Tavily Search.

Pourquoi Tavily ?
- API de recherche web conçue pour les agents IA
- Aucun blocage anti-scraping à gérer
- Retourne des résultats structurés directement
- Nativement intégré à LangChain
- Plan gratuit : 1000 requêtes/mois (https://tavily.com)
"""

import os
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date

from langchain_community.tools.tavily_search import TavilySearchResults

# Mapping des mois en français pour le parsing
FRENCH_MONTHS = {
    "janvier": 1, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "jan": 1, "fév": 2, "mar": 3, "avr": 4, "mai": 5, "jun": 6,
    "jul": 7, "aoû": 8, "sep": 9, "oct": 10, "nov": 11, "déc": 12,
    "janv": 1, "sept": 9, "octo": 10, "nove": 11, "dece": 12
}


class ScraperAgent:
    """
    Agent responsable de la collecte des offres d'emploi.
    Utilise l'API Tavily pour rechercher les offres sur le web
    sans avoir à gérer les blocages anti-scraping.

    Flux :
        profile_text
            │
            ▼
        _build_queries()  
            │
            ▼ →  construit des requêtes ciblées
        TavilySearchResults  
            │
            ▼
        _parse_results() →  normalise en format interne
            │            →  filtre intelligent (Publication >= 2026 OU Expiration future)
            ▼
        _deduplicate()  
            │
            ▼ →  supprime les doublons
        List[dict] (JobSearchState)
    """

    # Sites ciblés dans les requêtes Tavily (5 sources différentes)
    TARGET_SITES = [
        "cameroundesk.com",
        "minajob.com",
        "emploi.cm",
        "recrutement-cameroun.com",
        "joobaz.com",
    ]
    
    # Seuil de publication (MFE 2026 : seulement à partir de Janvier 2026)
    PUBLICATION_THRESHOLD = date(2026, 1, 1)

    # ============================================================
    # INITIALISATION
    # ============================================================
    def __init__(self, max_results: int = 10):
        """
        Args:
            max_results: Nombre de résultats max par requête Tavily
        """
        self.max_results = max_results
        self.tavily = TavilySearchResults(
            max_results=max_results,
            api_key=os.getenv("TAVILY_API_KEY"),
            include_raw_content=True,
        )
        # Pool d'offres brutes (avant filtrage de date) — utilisé par le fallback
        self._all_raw_jobs: List[Dict[str, Any]] = []

    # ============================================================
    # MÉTHODE PRINCIPALE
    # ============================================================
    def scrape(self, query: str, max_jobs: int = 10) -> List[Dict[str, Any]]:
        """
        Recherche des offres d'emploi correspondant au profil.
        Active automatiquement un mode fallback si aucune offre ne passe
        les filtres de date/qualité ou si le pool brut est vide.
        """
        print("  → [ScraperAgent] Recherche via Tavily...")
        print(f"  → [ScraperAgent] Profil reçu ({len(query)} chars) : {query[:200]}...")
        
        # Réinitialiser le pool brut à chaque appel
        self._all_raw_jobs = []
        
        # Garde-fou : si le profil est vide ou trop court, lever une alerte
        if not query or len(query.strip()) < 10:
            print("  ⚠ [ScraperAgent] Profil vide ou trop court — recherche générique activée")
            query = "offre emploi Cameroun"
        
        keywords = self._extract_keywords(query)
        queries = self._build_queries(keywords)
        all_jobs = []

        for q in queries:
            try:
                print(f"     Requête : {q}")
                results = self.tavily.invoke(q)
                jobs = self._parse_results(results)
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"  ⚠ Erreur Tavily pour '{q}': {e}")
                self._record_rejection("web", "Scraping échoué")

        unique_jobs = self._deduplicate(all_jobs)
        
        # -- Assurer la diversité des sources --
        from collections import defaultdict
        source_map = defaultdict(list)
        for job in unique_jobs:
            source_map[job["source"]].append(job)
            
        diverse_jobs = []
        while source_map and len(diverse_jobs) < max_jobs:
            for src in list(source_map.keys()):
                if len(diverse_jobs) >= max_jobs:
                    break
                diverse_jobs.append(source_map[src].pop(0))
                if not source_map[src]:
                    del source_map[src]

        # ──────────────────────────────────────
        # MODE FALLBACK : aucune offre valide après filtrage de date
        # ──────────────────────────────────────
        if not diverse_jobs:
            # Si le pool brut est vide (toutes les requêtes ont échoué),
            # on lance des requêtes de fallback élargies pour alimenter le pool
            if not self._all_raw_jobs:
                print("  ⚠ [ScraperAgent] Pool brut vide — lancement de requêtes de fallback élargies...")
                fallback_queries = self._build_fallback_queries(keywords)
                for fq in fallback_queries:
                    try:
                        print(f"     [Fallback Query] : {fq}")
                        results = self.tavily.invoke(fq)
                        # On stocke TOUT dans le pool brut sans filtrer par date
                        for r in results:
                            url = r.get("url", "")
                            title = r.get("title", "Offre d'emploi")
                            content = r.get("content", "") or r.get("raw_content", "")
                            if "annonce expirée" in title.lower() or "annonce expirée" in content.lower():
                                continue
                            source = self._identify_source(url)
                            pub_date_obj = self._extract_publication_date(content)
                            exp_date_obj = self._extract_expiration_date(content)
                            pub_str = pub_date_obj.strftime("%d/%m/%Y") if pub_date_obj else "Non précisée"
                            expiration_str = exp_date_obj.strftime("%d/%m/%Y") if exp_date_obj else "Non précisée"
                            job_entry = {
                                "title": self._clean_title(title),
                                "company": self._extract_company(content, title),
                                "location": self._extract_location(content),
                                "publication_date": pub_str,
                                "expiration_date": expiration_str,
                                "description": self._clean_text(content[:600].strip() if content else title),
                                "url": self._validate_url(url),
                                "source": source,
                                "_pub_date_obj": pub_date_obj,
                            }
                            self._all_raw_jobs.append(job_entry)
                    except Exception as e:
                        print(f"  ⚠ Erreur Tavily [Fallback Query] pour '{fq}': {e}")

            if self._all_raw_jobs:
                print("  ⚠ [ScraperAgent] Fallback mode activated: all jobs were rejected. "
                      "Injecting up to 5 recent jobs from 5 distinct sources.")
                diverse_jobs = self._fallback_strategy(self._all_raw_jobs)
                if diverse_jobs:
                    print(f"  ✓ [Fallback] {len(diverse_jobs)} offre(s) injectée(s) depuis le pool brut.")
                else:
                    print("  ✗ [Fallback] Pool brut vide — aucune offre à injecter.")

        print(f"  ✅ {len(diverse_jobs)} offres collectées avec diversité")
        
        # Nettoyage : retirer la clé privée utilisée uniquement pour le fallback
        for job in diverse_jobs:
            job.pop("_pub_date_obj", None)
        
        return diverse_jobs

    # ============================================================
    # STRATÉGIE FALLBACK
    # ============================================================
    def _fallback_strategy(self, raw_pool: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Stratégie de secours : sélectionne les 5 offres les plus récentes
        provenant de 5 sites différents, depuis le pool brut (offres non filtrées).

        Règles :
        - 5 offres maximum
        - Priorité aux offres les plus récentes (date de publication)
        - Au maximum 1 offre par source (5 sources différentes visées)
        - Si moins de 5 sources distinctes disponibles, complète avec les offres
          les plus récentes des sources déjà représentées (sans doublon)
        - Aucun doublon
        """
        from datetime import date as date_cls
        TARGET = 5

        # 1. Dédupliquer le pool brut
        seen_urls = set()
        seen_titles = set()
        unique_pool = []
        for job in raw_pool:
            url_key = job.get("url", "").lower()
            title_key = job.get("title", "").lower()[:50]
            if url_key not in seen_urls and title_key not in seen_titles:
                seen_urls.add(url_key)
                seen_titles.add(title_key)
                unique_pool.append(job)

        if not unique_pool:
            return []

        # 2. Trier par date de publication (la plus récente en premier)
        #    Les offres sans date sont placées en dernier (date minimale)
        def sort_key(j):
            d = j.get("_pub_date_obj")
            if isinstance(d, date_cls):
                return d
            return date_cls.min

        sorted_pool = sorted(unique_pool, key=sort_key, reverse=True)

        # 3. Pass 1 : une offre par source différente (max TARGET sources)
        selected = []
        used_sources = set()

        for job in sorted_pool:
            if len(selected) >= TARGET:
                break
            src = job.get("source", "web")
            if src not in used_sources:
                selected.append(job)
                used_sources.add(src)

        # 4. Pass 2 : si moins de TARGET offres, compléter avec les plus récentes
        #    sans doublon (même si la source est déjà représentée)
        if len(selected) < TARGET:
            for job in sorted_pool:
                if len(selected) >= TARGET:
                    break
                if job not in selected:
                    selected.append(job)

        # 5. Marquer les offres injectées par le fallback
        for job in selected:
            job["fallback"] = True
            print(f"     [Fallback] Injection : '{job['title']}' depuis '{job.get('source')}'")

        return selected

    # ============================================================
    # CONSTRUCTION DES REQUÊTES
    # ============================================================
    def _build_queries(self, keywords: List[str]) -> List[str]:
        """
        Construit plusieurs requêtes de recherche ciblées avec la période courante.
        """
        base = " ".join(keywords[:6])
        queries = []
        
        # Période dynamique basée sur la date actuelle
        today = date.today()
        FRENCH_MONTHS_REV = {
            1: "janvier", 2: "février", 3: "mars", 4: "avril",
            5: "mai", 6: "juin", 7: "juillet", 8: "août",
            9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre"
        }
        target_period = f"{FRENCH_MONTHS_REV[today.month]} {today.year}"

        for site in self.TARGET_SITES:
            queries.append(f"offre emploi {target_period} {base} site:{site}")

        queries.append(f"offre emploi {target_period} {base} Cameroun")
        
        return queries

    def _build_fallback_queries(self, keywords: List[str]) -> List[str]:
        """
        Construit des requêtes élargies sans restriction de date pour le fallback.
        Cible 5 sites différents avec les mots-clés du profil.
        Utilisé lorsque toutes les offres ont été rejetées ou que le pool brut est vide.
        """
        base = " ".join(keywords[:6])
        
        queries = []
        for site in self.TARGET_SITES:
            queries.append(f"offre emploi récente {base} Cameroun site:{site}")
        
        # Requête générale sans site ciblé
        queries.append(f"offre emploi 2026 {base} Cameroun recrutement")
        
        return queries

    # ============================================================
    # PARSING DES RÉSULTATS TAVILY
    # ============================================================
    def _parse_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalise les résultats bruts de Tavily au format interne.
        Applique les filtres de date de publication et de date limite.
        Stocke TOUTES les offres (même rejetées) dans _all_raw_jobs pour le fallback.
        """
        jobs = []
        today = date.today()

        for r in results:
            url = r.get("url", "")
            title = r.get("title", "Offre d'emploi")
            content = r.get("content", "") or r.get("raw_content", "")
            
            # --- Exigence 1 : Ignorer les annonces explicitement expirées ---
            if "annonce expirée" in title.lower() or "annonce expirée" in content.lower():
                print(f"     [Debug] Offre ignorée (Expirée via mention) : {title}")
                self._record_rejection(url, "Offre expirée")
                continue
            
            source = self._identify_source(url)
            company = self._extract_company(content, title)
            location = self._extract_location(title + " " + content)
            
            # --- Extraction des dates ---
            pub_date_obj = self._extract_publication_date(content)
            exp_date_obj = self._extract_expiration_date(content)
            
            # Formatage des dates pour l'affichage
            pub_str = pub_date_obj.strftime("%d/%m/%Y") if pub_date_obj else "Non précisée"
            expiration_str = exp_date_obj.strftime("%d/%m/%Y") if exp_date_obj else "Non précisée"

            description = content[:600].strip() if content else title

            # --- Nettoyage et Validation Final ---
            title_clean = self._clean_title(title)
            company_clean = self._clean_text(company)
            location_clean = self._clean_text(location)
            description_clean = self._clean_text(description)
            url_clean = self._validate_url(url)
            
            if url_clean == "Lien indisponible":
                self._record_rejection(url, "Lien invalide")
                continue

            if location_clean in ["N/A", ""]:
                print(f"     [Debug] Offre rejetée (Localisation non spécifique) : {title}")
                self._record_rejection(url, "Localisation non spécifique")
                continue

            job_entry = {
                "title": title_clean,
                "company": company_clean,
                "location": location_clean,
                "publication_date": pub_str,
                "expiration_date": expiration_str,
                "description": description_clean,
                "url": url_clean,
                "source": source,
                # Garder les objets date pour le tri du fallback
                "_pub_date_obj": pub_date_obj,
            }

            # --- Stocker dans le pool brut pour le fallback (avant filtre de date) ---
            self._all_raw_jobs.append(job_entry)

            # --- Appliquer le filtre de date (seules les offres valides passent) ---
            is_valid, raison_rejet = self._is_job_valid(pub_date_obj, exp_date_obj, title)
            if not is_valid:
                self._record_rejection(url, raison_rejet)
                continue

            jobs.append(job_entry)

        return jobs

    # ============================================================
    # LOGIQUE MÉTIER PRIORITAIRE
    # ============================================================
    def _is_job_valid(self, pub_date_obj: Optional[date], exp_date_obj: Optional[date], title: str) -> Tuple[bool, str]:
        """
        Logique métier de filtrage prioritaire des offres d'emploi.
        Règles :
        1. Publication <= 15 jours ET non expirée.
        2. Fallback sur Date Limite de candidature dans le futur.
        3. Exclusion immédiate si aucune date.
        """
        today = date.today()
        
        if pub_date_obj:
            delta = today - pub_date_obj
            is_expired = (exp_date_obj is not None and exp_date_obj <= today)
            
            if delta.days <= 15 and not is_expired:
                return True, "Valide"
            else:
                raison = "Expirée" if is_expired else f"Trop ancienne ({delta.days} jours)"
                print(f"     [Debug] Offre rejetée ({raison}) : {title}")
                return False, raison
                
        elif exp_date_obj:
            if exp_date_obj > today:
                print(f"     [Debug] Publication inconnue, mais expire le {exp_date_obj} -> Conservée : {title}")
                return True, "Valide par Date Expiration"
            else:
                print(f"     [Debug] Offre rejetée (Expirée le {exp_date_obj}) : {title}")
                return False, "Expirée"
                
        else:
            print(f"     [Debug] Offre rejetée (Aucune date disponible) : {title}")
            return False, "Aucune date"

    # ============================================================
    # UTILITAIRES D'EXTRACTION
    # ============================================================
    def _extract_keywords(self, profile: str) -> List[str]:
        """Extrait les mots-clés pertinents du profil"""
        stopwords = {
            "je", "suis", "un", "une", "le", "la", "les", "et", "de",
            "du", "des", "en", "au", "avec", "pour", "dans", "sur",
            "mon", "ma", "mes", "par", "que", "qui", "plus", "ans"
        }
        
        words = profile.lower().split()
        # Conserver les mots de 2+ caractères (pour capturer "RH", "BI", etc.)
        keywords = [w.strip(".,;:!?") for w in words if len(w) >= 2 and w not in stopwords]
        
        # Déduplication
        seen, unique = set(), []
        for k in keywords:
            if k not in seen:
                seen.add(k)
                unique.append(k)
                
        return unique[:8]

    def _identify_source(self, url: str) -> str:
        """Identifie le site source depuis l'URL"""
        url_lower = url.lower()
        
        if "cameroundesk" in url_lower:
            return "cameroundesk"
        if "minajob" in url_lower:
            return "minajob"
        if "emploi.cm" in url_lower:
            return "emploi.cm"
            
        try:
            return url.split("//")[1].split("/")[0].replace("www.", "")
        except Exception:
            return "web"

    def _extract_company(self, content: str, title: str) -> str:
        """Tente d'extraire le nom de l'entreprise depuis le contenu"""
        patterns = [
            r"(?:entreprise|société|company|employeur)\s*[:\-]\s*([A-Z][^\n,]{2,40})",
            r"(?:recrutement|recrute)\s+(?:pour|chez)\s+([A-Z][^\n,]{2,40})",
            r"([A-Z][A-Z\s]{2,30})\s+(?:recrute|recherche)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()
                
        return "N/A"

    def _extract_location(self, text: str) -> str:
        """Extrait la localisation depuis le texte (titre + contenu)"""
        text_lower = text.lower()
        
        remote_keywords = ["remote", "télétravail", "teletravail", "en ligne", "à distance", "telecommute"]
        if any(w in text_lower for w in remote_keywords):
            return "Remote"

        cities = [
            "Yaoundé", "Douala", "Bafoussam", "Garoua", "Maroua",
            "Bamenda", "Ngaoundéré", "Bertoua", "Kumba", "Limbe"
        ]
        
        for city in cities:
            if city.lower() in text_lower:
                return city
                
        if "cameroun" in text_lower:
            return "Cameroun"
            
        return "N/A"

    def _extract_publication_date(self, content: str) -> Optional[date]:
        """Tente d'extraire la date de publication."""
        patterns = [
            r"(?:publié|mis en ligne|parution|posté|date)\s+(?:le|du)?\s*([0-9]{1,2}(?:\s*[a-zA-Zéû]{3,10}\s*|[\/\.\-])[0-9]{1,2}(?:[\/\.\-][0-9]{2,4})?)",
            r"([0-9]{1,2}\s*[a-zA-Zéû]{3,10}\s*[0-9]{4})"
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                candidate = match.group(1).strip()
                parsed_date = self._normalize_date(candidate)
                if parsed_date:
                    return parsed_date
        return None

    def _extract_expiration_date(self, content: str) -> Optional[date]:
        """Tente d'extraire la date d'expiration."""
        patterns = [
            r"(?:date limite|expire le|clôture|jusqu'au|deadline|avant le)\s*[:\-]?\s*([0-9]{1,2}(?:\s*[a-zA-Zéû]{3,10}\s*|[\/\.\-])[0-9]{1,2}(?:[\/\.\-][0-9]{2,4})?)",
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                candidate = match.group(1).strip()
                parsed_date = self._normalize_date(candidate)
                if parsed_date:
                    return parsed_date
        return None

    def _normalize_date(self, date_str: str) -> Optional[date]:
        """Normalise une chaîne de date en objet date."""
        date_str = date_str.lower().strip()
        date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
        date_str = date_str.replace(',', ' ').replace('.', '/')
        
        # Format YYYY-MM-DD
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            try: return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError: pass

        # DD/MM/YYYY
        num_match = re.match(r'^(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?$', date_str)
        if num_match:
            d, m, y = num_match.groups()
            if not y: y = str(date.today().year)
            if len(y) == 2: y = "20" + y
            try: return date(int(y), int(m), int(d))
            except ValueError: pass

        # Texte (12 Avril 2026)
        txt_match = re.search(r'(\d{1,2})\s+([a-zéû]+)\s+(\d{4})', date_str)
        if not txt_match:
            txt_match = re.search(r'([a-zéû]+)\s+(\d{1,2})\s+(\d{4})', date_str)
            if txt_match: m_txt, d, y = txt_match.groups()
            else: return None
        else:
            d, m_txt, y = txt_match.groups()

        month_idx = FRENCH_MONTHS.get(m_txt)
        if not month_idx:
            eng_months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
            month_idx = eng_months.get(m_txt[:3])
            
        if month_idx:
            try: return date(int(y), month_idx, int(d))
            except ValueError: pass
        return None

    def _clean_title(self, title: str) -> str:
        """Nettoie le titre de la page web."""
        title = re.sub(r"\s*[\|\-–]\s*(cameroundesk|minajob|emploi\.cm).*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*[\|\-–]\s*offres?\s+d.emploi.*$", "", title, flags=re.IGNORECASE)
        return self._clean_text(title)

    def _clean_text(self, text: str) -> str:
        """
        Nettoie le texte pour supprimer les caractères corrompus,
        les symboles sans signification et les caractères non-latins (chinois, etc.).
        """
        if not text or text == "N/A":
            return text

        # 1. Supprimer les caractères de remplacement Unicode () et symboles corrompus
        # On cible aussi les blocs de symboles graphiques (▓▒)
        text = text.replace("\ufffd", "")
        text = re.sub(r'[▓▒░█]+', '', text)
        
        # 2. Supprimer les caractères non-ASCII / non-Latins (chinois, japonais, etc.)
        # On conserve : Latin, Accents, Chiffres, Ponctuation standard et Espaces.
        # \u00C0-\u00FF couvre les caractères accentués français.
        text = re.sub(r'[^\x00-\x7F\u00C0-\u00FF\s\.,;!?:()\'\"\-@&€$%*+=/]', '', text)

        # 3. Supprimer les répétitions excessives de symboles incohérents (ex: /////%%%%)
        # On garde les répétitions de lettres ou chiffres, mais on limite les symboles
        text = re.sub(r'([^\w\s])\1{2,}', r'\1', text)

        # 4. Normaliser les espaces et retours à la ligne
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _validate_url(self, url: str) -> str:
        """
        Vérifie si le lien est valide, propre et ne contient pas de code HTML.
        """
        if not url:
            return "Lien indisponible"
            
        url = url.strip()
        
        # Détection de code source HTML ou caractères suspects dans une URL
        if any(c in url for c in ['<', '>', '{', '}', '[', ']', '"', "'"]):
            return "Lien indisponible"
            
        # Validation du protocole
        if not (url.startswith("http://") or url.startswith("https://")):
            return "Lien indisponible"
            
        # Vérification sommaire de la structure (point obligatoire)
        if "." not in url:
            return "Lien indisponible"
            
        return url

    def _deduplicate(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Supprime les doublons."""
        seen_urls = set()
        seen_titles = set()
        unique = []
        for job in jobs:
            url_key = job.get("url", "").lower()
            title_key = job.get("title", "").lower()[:50]
            if url_key not in seen_urls and title_key not in seen_titles:
                seen_urls.add(url_key)
                seen_titles.add(title_key)
                unique.append(job)
        return unique

    @staticmethod
    def mock_scrape(query: str) -> List[Dict[str, Any]]:
        """Données fictives."""
        # Simulation de quelques rejets pour le Dashboard (Mode Démo)
        try:
            import streamlit as st
            if "rejected_sites" not in st.session_state or not st.session_state.rejected_sites:
                from datetime import datetime
                st.session_state.rejected_sites = {
                    "linkedin.com": {
                        "site": "linkedin.com",
                        "rejected_count": 12,
                        "reasons": {"Offre expirée": 8, "Lien invalide": 4},
                        "last_rejected": datetime.now().strftime("%d/%m/%Y %H:%M")
                    },
                    "indeed.com": {
                        "site": "indeed.com",
                        "rejected_count": 5,
                        "reasons": {"Trop ancienne": 5},
                        "last_rejected": datetime.now().strftime("%d/%m/%Y %H:%M")
                    }
                }
        except: pass

        return [
            {
                "title": "Data Scientist",
                "company": "Orange Cameroun",
                "location": "Douala",
                "description": "Python, ML, SQL.",
                "url": "https://www.cameroundesk.com/data-scientist",
                "source": "cameroundesk",
                "publication_date": "12/01/2026",
                "expiration_date": "15/05/2026"
            },
            {
                "title": "Ingénieur BI",
                "company": "MTN",
                "location": "Yaoundé",
                "description": "BI, Azure.",
                "url": "https://www.minajob.com/ingenieur-bi",
                "source": "minajob",
                "publication_date": "Non précisée",
                "expiration_date": "20/06/2026"
            },
        ]

    def _record_rejection(self, url: str, reason: str):
        """Enregistre un rejet dans le session state de Streamlit pour le Dashboard."""
        try:
            import streamlit as st
            if "rejected_sites" not in st.session_state:
                st.session_state.rejected_sites = {}
            
            site = self._identify_source(url)
            
            if site not in st.session_state.rejected_sites:
                st.session_state.rejected_sites[site] = {
                    "site": site,
                    "rejected_count": 0,
                    "reasons": {},
                    "last_rejected": ""
                }
            
            entry = st.session_state.rejected_sites[site]
            entry["rejected_count"] += 1
            entry["reasons"][reason] = entry["reasons"].get(reason, 0) + 1
            entry["last_rejected"] = datetime.now().strftime("%d/%m/%Y %H:%M")
        except Exception:
            pass
