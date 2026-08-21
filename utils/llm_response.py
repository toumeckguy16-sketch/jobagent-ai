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
from typing import Any, Optional

from langchain_groq import ChatGroq

DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.6-27b")

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
    Instancie ChatGroq pour Qwen 3.6 en mode non-thinking.

    reasoning_effort=none  → pas de chaîne de réflexion (JSON / dialogue).
    reasoning_format=parsed → si thinking réapparaît, il est séparé de content.
    """
    kwargs: dict[str, Any] = {
        "model": model or DEFAULT_GROQ_MODEL,
        "temperature": temperature,
        "api_key": os.getenv("GROQ_API_KEY"),
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

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


def invoke_json(llm: ChatGroq, prompt_value) -> dict:
    """Appelle le LLM et parse un JSON métier (sans JsonOutputParser)."""
    message = llm.invoke(prompt_value)
    visible = extract_final_content(message)
    return parse_json_from_text(visible)
