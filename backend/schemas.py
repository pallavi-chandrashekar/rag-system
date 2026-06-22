"""Pydantic response models for the RAG API.

These describe the *grounded* chat contract: every answer is accompanied by
the sources it was derived from, a confidence score, and observability
metadata so consumers can audit how an answer was produced.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Source(BaseModel):
    """A single retrieved chunk that contributed to an answer (a citation)."""

    document_id: str
    filename: str
    chunk_id: str
    chunk_index: int = 0
    tenant_id: str
    text_snippet: str
    retrieval_score: float = Field(..., description="Final fused ranking score")
    keyword_score: float = 0.0
    vector_score: float = 0.0
    combined_score: float = 0.0


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """Top-level grounded chat response."""

    answer: str
    sources: List[Source] = []
    confidence: float = 0.0
    mode: str = "hybrid"
    tenant_id: str
    latency_ms: int = 0
    token_usage: TokenUsage = TokenUsage()

    # --- Backwards-compatible fields consumed by the existing frontend ----
    results: List[dict] = []
    strategy_used: Optional[str] = None
