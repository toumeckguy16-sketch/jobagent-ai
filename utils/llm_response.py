"""
Traitement des réponses Groq / Qwen 3.6.

Qwen 3.6 (preview) est un modèle hybride « thinking / non-thinking ».
La réponse brute n'est pas toujours un simple texte :

- message.content            : réponse destinée à l'utilisateur (parfois polluée)
- additional_kwargs['reasoning'] / reasoning_content : raisonnement interne
- balises <think>…</think>   : thinking parfois injecté dans content
- content en liste de blocs  : text vs reasoning

Ce module extrait uniquement le texte visible / le JSON métier.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, List, Optional

from langchain_groq import ChatGroq

DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")
FALLBACK_GROQ_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b"]

# Raisonnement interne éventuellement collé dans content
_THINK_BLOCK_RE = re.compile(
    r"<think>.*?</think>"
    r"|<thinking>.*?</thinking>"
    r"|<\|think\|>.*?<\|/think\|>"
    r"|<\|begin_of_thought\|>.*?<\|end_of_thought\|>",
    re.DOTALL | re.IGNORECASE,
)
_REASONING_KEYS = {
    "reasoning",
    "reasoning_content",
    "reasoning_details",
    "thinking",
    "thought",
}


def make_chat_groq(
    *,
    temperature: float,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
) -> ChatGroq:
    """
    Instancie ChatGroq pour Qwen 3.6 ou modèle de secours en mode non-thinking.

    reasoning_effort=none  → pas de chaîne de réflexion (JSON / dialogue).
    reasoning_format=parsed → si thinking réapparaît, il est séparé de content.
    max_tokens = 1024 par défaut si non spécifié pour éviter le rejet OTPM de Groq.
    """
    target_model = model or DEFAULT_GROQ_MODEL
    safe_max_tokens = max_tokens if max_tokens is not None else 1024

    kwargs: dict[str, Any] = {
        "model": target_model,
        "temperature": temperature,
        "api_key": os.getenv("GROQ_API_KEY"),
        "max_tokens": safe_max_tokens,
    }

    # reasoning_effort="none" n'est supporté que par la famille Qwen
    if "qwen" in target_model.lower():
        extras = [
            {
                "reasoning_effort": "none",
                "reasoning_format": "parsed",
            },
            {
                "extra_body": {
                    "reasoning_effort": "none",
                    "reasoning_format": "parsed",
                }
            },
            {
                "model_kwargs": {
                    "reasoning_effort": "none",
                    "reasoning_format": "parsed",
                }
            },
        ]
        last_error = None
        for extra in extras:
            try:
                return ChatGroq(**kwargs, **extra)
            except (TypeError, ValueError) as exc:
                last_error = exc
                continue
        if last_error:
            print(f"[llm_response] Paramètres reasoning Groq ignorés : {last_error}")

    return ChatGroq(**kwargs)


def invoke_with_retry(
    llm_or_chain: Any,
    prompt_value: Any,
    max_retries: int = 2,
    initial_delay: float = 2.0,
    backoff_factor: float = 2.0,
    fallback_models: Optional[List[str]] = None,
    temperature: float = 0.3,
    max_tokens: Optional[int] = 1024,
) -> Any:
    """
    Exécute un appel LLM ou une chaîne LangChain de manière résiliente :
    1. Réessaye avec temporisation exponentielle (backoff) en cas de RateLimitError (429)
       ou d'erreur réseau transitoire.
    2. Si les retries échouent sur le modèle principal, bascule automatiquement
       sur les modèles de secours (fallback_models) dont les quotas Groq sont distincts.
    """
    if fallback_models is None:
        fallback_models = list(FALLBACK_GROQ_MODELS)

    last_exception = None

    # 1. Tentatives sur le modèle principal avec backoff
    for attempt in range(max_retries + 1):
        try:
            return llm_or_chain.invoke(prompt_value)
        except Exception as exc:
            last_exception = exc
            err_msg = str(exc).lower()
            is_rate_limit = (
                "rate_limit" in err_msg
                or "rate limit" in err_msg
                or "429" in err_msg
                or "tokens per minute" in err_msg
                or "too large" in err_msg
                or "resource has been exhausted" in err_msg
            )
            is_transient = (
                is_rate_limit
                or "connection" in err_msg
                or "timeout" in err_msg
                or "503" in err_msg
                or "502" in err_msg
                or "500" in err_msg
            )

            if not is_transient or attempt >= max_retries:
                break

            wait_time = initial_delay * (backoff_factor ** attempt)
            match = re.search(r"try again in (\d+(?:\.\d+)?)s", str(exc), re.IGNORECASE)
            if match:
                try:
                    suggested = float(match.group(1)) + 0.5
                    wait_time = max(wait_time, suggested)
                except ValueError:
                    pass

            print(
                f"[llm_response] Rate limit ou erreur transitoire ({type(exc).__name__}). "
                f"Attente {wait_time:.1f}s avant réessai ({attempt + 1}/{max_retries})..."
            )
            time.sleep(wait_time)

    # 2. Si le modèle principal a échoué malgré les retries, essayer les modèles de secours
    for fb_model in fallback_models:
        print(f"[llm_response] Bascule automatique vers le modèle de secours Groq : {fb_model}")
        try:
            fb_llm = make_chat_groq(
                temperature=temperature,
                max_tokens=max_tokens,
                model=fb_model,
            )
            if hasattr(llm_or_chain, "first") and hasattr(llm_or_chain, "last"):
                # Cas d'une RunnableSequence (prompt | llm)
                fb_chain = llm_or_chain.first | fb_llm
                return fb_chain.invoke(prompt_value)
            else:
                return fb_llm.invoke(prompt_value)
        except Exception as fb_exc:
            print(f"[llm_response] Modèle de secours {fb_model} a également échoué : {fb_exc}")
            last_exception = fb_exc
            continue

    # Si tous les modèles ont échoué, propager la dernière exception
    raise last_exception


def extract_final_content(message: Any) -> str:
    """
    Retourne uniquement le texte destiné à l'utilisateur.

    Priorité :
    1. Blocs 'text' / 'output_text' d'un content multimodale (hors reasoning)
    2. Attribut .content s'il est une chaîne
    3. Nettoyage des balises de thinking encore présentes
    """
    if message is None:
        return ""

    content = getattr(message, "content", message)

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
                continue
            if not isinstance(block, dict):
                text_attr = getattr(block, "text", None)
                btype = getattr(block, "type", None)
                if btype in _REASONING_KEYS or btype in ("reasoning", "thinking"):
                    continue
                if text_attr:
                    parts.append(str(text_attr))
                continue
            btype = str(block.get("type", "")).lower()
            if btype in _REASONING_KEYS or btype in ("reasoning", "thinking"):
                continue
            if "text" in block:
                parts.append(str(block["text"]))
            elif "output_text" in block:
                parts.append(str(block["output_text"]))
        content = "\n".join(parts)

    if content is None:
        content = ""
    text = str(content)

    # Ne jamais concaténer additional_kwargs.reasoning dans le texte affiché
    text = _THINK_BLOCK_RE.sub("", text)

    # Séparateurs fréquents : thinking puis réponse
    for marker in (
        "</think>",
        "<|end_of_thought|>",
        "<|start_of_solution|>",
        "Final answer:",
        "Réponse finale :",
        "Réponse finale:",
    ):
        if marker.lower() in text.lower():
            idx = text.lower().rfind(marker.lower())
            after = text[idx + len(marker) :].strip()
            if after:
                text = after

    return text.strip()


def parse_json_from_text(text: str) -> dict:
    """Extrait le premier objet JSON valide d'une réponse LLM."""
    if not text or not str(text).strip():
        raise ValueError("Réponse LLM vide, JSON impossible à extraire.")

    cleaned = extract_final_content(text)
    cleaned = cleaned.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"questions": parsed}
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        snippet = cleaned[start : end + 1]
        parsed = json.loads(snippet)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Impossible d'extraire un objet JSON de la réponse LLM.")


def invoke_json(
    llm: Any,
    prompt_value: Any,
    max_retries: int = 2,
    fallback_models: Optional[List[str]] = None,
    max_tokens: Optional[int] = 4096,
) -> dict:
    """Appelle le LLM de façon résiliente et parse un JSON métier."""
    message = invoke_with_retry(
        llm,
        prompt_value,
        max_retries=max_retries,
        fallback_models=fallback_models,
        temperature=0.0,
        max_tokens=max_tokens,
    )
    visible = extract_final_content(message)
    return parse_json_from_text(visible)
