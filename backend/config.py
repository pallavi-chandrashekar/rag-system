"""Centralised application configuration.

All tunable behaviour for the RAG pipeline is exposed here as environment
variables so the reference architecture can be reconfigured without code
changes. Defaults are production-sensible and let the stack boot with zero
configuration for local evaluation.
"""

import os


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Settings:
    """Runtime settings resolved from the environment."""

    # --- Models -----------------------------------------------------------
    # Chat/generation model used for grounded answers, routing and summaries.
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_CHAT_MODEL: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini")

    # Embedding configuration. The reference stack ships with a *local*
    # sentence-transformers model (no API key required, 384 dimensions) so it
    # is fully runnable offline. Set EMBEDDING_PROVIDER=openai to switch to the
    # hosted model below (requires re-ingestion + a matching Vector() column).
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "local")
    OPENAI_EMBEDDING_MODEL: str = os.getenv(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )
    LOCAL_EMBEDDING_MODEL: str = os.getenv(
        "LOCAL_EMBEDDING_MODEL", "all-MiniLM-L6-v2"
    )
    EMBEDDING_DIM: int = _get_int("EMBEDDING_DIM", 384)

    # --- Retrieval --------------------------------------------------------
    RAG_TOP_K: int = _get_int("RAG_TOP_K", 5)
    RAG_MIN_CONFIDENCE_SCORE: float = _get_float("RAG_MIN_CONFIDENCE_SCORE", 0.55)
    RAG_ENABLE_HYBRID_RETRIEVAL: bool = _get_bool("RAG_ENABLE_HYBRID_RETRIEVAL", True)
    RAG_ENABLE_UNKNOWN_ANSWER: bool = _get_bool("RAG_ENABLE_UNKNOWN_ANSWER", True)
    RAG_ENABLE_CITATIONS: bool = _get_bool("RAG_ENABLE_CITATIONS", True)

    # Hybrid scoring weights: combined = VECTOR_WEIGHT*vec + KEYWORD_WEIGHT*kw
    RAG_VECTOR_WEIGHT: float = _get_float("RAG_VECTOR_WEIGHT", 0.7)
    RAG_KEYWORD_WEIGHT: float = _get_float("RAG_KEYWORD_WEIGHT", 0.3)

    # Minimum cosine similarity for a vector candidate to be considered.
    RAG_VECTOR_FLOOR: float = _get_float("RAG_VECTOR_FLOOR", 0.35)

    # Standard response message when the system cannot ground an answer.
    UNKNOWN_ANSWER_TEXT: str = os.getenv(
        "UNKNOWN_ANSWER_TEXT",
        "I don't know based on the available documents.",
    )


settings = Settings()
