"""LLM access layer.

Provides plain chat completion plus a *grounded* generation path that forces
the model to answer only from retrieved context and to abstain ("I don't
know...") when the context is insufficient. Token usage is surfaced for
observability.
"""

import os
from typing import Dict, List, Tuple

from backend.config import settings

_client = None


def _get_client():
    """Lazily construct the OpenAI client so importing this module stays
    dependency-free (used by unit tests / tooling without `openai` installed)."""
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client

# Grounding contract enforced on every retrieval-augmented answer.
GROUNDED_SYSTEM_PROMPT = """You are an enterprise knowledge assistant.

RULES:
1. Answer ONLY using the information in the provided context.
2. If the context does not contain the answer, reply with EXACTLY:
   "{unknown}"
3. Always cite the sources you used by their [Source N] label.
4. Do not use outside knowledge or speculate. Be concise and factual.
"""


def chat_with_llm(messages: list, model: str = None) -> str:
    """General chat completion (used for routing, summaries, small talk)."""
    try:
        response = _get_client().chat.completions.create(
            model=model or settings.OPENAI_CHAT_MODEL,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:  # noqa: BLE001 - surfaced to caller as friendly text
        print(f"LLM Error: {e}")
        return "I'm having trouble connecting to my brain right now."


def _format_context(sources: List[Dict]) -> str:
    """Render retrieved sources into a numbered, citable context block."""
    blocks = []
    for i, s in enumerate(sources, start=1):
        label = s.get("filename", "document")
        blocks.append(f"[Source {i}] ({label})\n{s.get('text_snippet', s.get('content', ''))}")
    return "\n\n".join(blocks)


def generate_grounded_answer(
    query: str, sources: List[Dict], history: List[Dict] = None
) -> Tuple[str, Dict]:
    """Generate an answer grounded strictly in ``sources``.

    Returns ``(answer_text, token_usage_dict)``. When no sources are provided
    the configured unknown-answer text is returned without an LLM call.
    """
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    if not sources:
        return settings.UNKNOWN_ANSWER_TEXT, usage

    system = GROUNDED_SYSTEM_PROMPT.format(unknown=settings.UNKNOWN_ANSWER_TEXT)
    messages = [{"role": "system", "content": system}]
    for m in (history or [])[-4:]:
        role = "assistant" if m.get("role") in ("ai", "assistant") else "user"
        messages.append({"role": role, "content": m.get("content", "")})

    context = _format_context(sources)
    messages.append(
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:",
        }
    )

    try:
        response = _get_client().chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=messages,
            temperature=0.1,
        )
        answer = response.choices[0].message.content.strip()
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return answer, usage
    except Exception as e:  # noqa: BLE001
        print(f"Grounded LLM Error: {e}")
        return settings.UNKNOWN_ANSWER_TEXT, usage
