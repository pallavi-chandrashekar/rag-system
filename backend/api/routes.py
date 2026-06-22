from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Dict, Optional
import datetime
import logging
import time
import uuid

from backend.config import settings
from backend.database import get_db
from backend.models import ChatSession # <--- Import New Model
from backend.services.chat import rewrite_query, generate_multi_queries, decompose_query
from backend.services.ingestion import process_document
from backend.services.router import route_query
from backend.services.llm import chat_with_llm, generate_grounded_answer
from backend.services.retrieval_service import retrieval_service

logger = logging.getLogger("rag.api")

router = APIRouter()

class SearchPayload(BaseModel):
    text: str
    tenant_id: str
    session_id: Optional[str] = None # <--- New Field
    chat_history: List[Dict[str, str]] = []

class RenameChatPayload(BaseModel):
    title: str

# --- 1. SEARCH (Grounded RAG + history persistence) ---
@router.post("/api/v1/search")
async def search_rag(payload: SearchPayload, db: Session = Depends(get_db)):
    """Grounded, tenant-scoped RAG.

    Modes (Step 7): ``LLM_ONLY``, ``SUMMARY``, ``SEARCH`` (hybrid retrieval).
    Returns a citation-rich response with confidence + observability metadata.
    """
    started = time.perf_counter()
    query_text = payload.text.strip()
    tenant_id = payload.tenant_id

    # --- ROUTING ---------------------------------------------------------
    q_lower = query_text.lower()
    summary_triggers = ["summarize", "summary", "tldr", "overview"]
    if q_lower in summary_triggers or any(q_lower.startswith(s) for s in summary_triggers):
        mode = "summary"
    elif any(x in q_lower for x in ["hi", "hello", "hey", "how are you"]):
        mode = "llm_only"
    else:
        mode = route_query(query_text)

    answer = ""
    sources: List[Dict] = []
    confidence = 0.0
    token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # --- EXECUTE ---------------------------------------------------------
    if mode == "llm_only":
        msgs = [{"role": ("assistant" if m["role"] == "ai" else "user"), "content": m["content"]} for m in payload.chat_history]
        msgs.append({"role": "user", "content": query_text})
        answer = chat_with_llm(msgs)

    elif mode == "summary":
        docs = db.execute(
            text("SELECT content FROM chunks WHERE tenant_id = :tid LIMIT 15"),
            {"tid": tenant_id},
        ).fetchall()
        if docs:
            combined = "\n\n".join([r.content for r in docs])
            answer = chat_with_llm([{"role": "user", "content": f"Summarize:\n{combined}"}])
        else:
            answer = settings.UNKNOWN_ANSWER_TEXT if settings.RAG_ENABLE_UNKNOWN_ANSWER else "No documents found to summarize."

    else:
        mode = "hybrid" if settings.RAG_ENABLE_HYBRID_RETRIEVAL else "vector"
        # Contextual rewrite for follow-up questions.
        standalone_query = query_text
        if payload.chat_history:
            standalone_query = rewrite_query(query_text, payload.chat_history)

        retrieved = retrieval_service.retrieve(db, standalone_query, tenant_id)
        confidence = retrieval_service.confidence(retrieved)

        # --- Unknown-answer handling (Step 6): no chunks OR low confidence ---
        grounded = (
            retrieved
            and not (
                settings.RAG_ENABLE_UNKNOWN_ANSWER
                and confidence < settings.RAG_MIN_CONFIDENCE_SCORE
            )
        )
        if grounded:
            filenames = retrieval_service.lookup_filenames(
                db, [r["document_id"] for r in retrieved]
            )
            sources = retrieval_service.format_sources(retrieved, tenant_id, filenames)
            answer, token_usage = generate_grounded_answer(
                standalone_query, sources, payload.chat_history
            )
            # Drop citations if the model abstained anyway.
            if answer.strip() == settings.UNKNOWN_ANSWER_TEXT:
                sources = []
                mode = "unknown"
        else:
            answer = (
                settings.UNKNOWN_ANSWER_TEXT
                if settings.RAG_ENABLE_UNKNOWN_ANSWER
                else "No relevant information was found in your documents."
            )
            mode = "unknown"

    latency_ms = int((time.perf_counter() - started) * 1000)

    # --- OBSERVABILITY (Step 10) -----------------------------------------
    logger.info(
        "rag_query tenant=%s mode=%s retrieval_count=%d selected_sources=%d "
        "confidence=%.3f model=%s latency_ms=%d tokens=%d",
        tenant_id, mode, len(sources), len(sources), confidence,
        settings.OPENAI_CHAT_MODEL, latency_ms, token_usage.get("total_tokens", 0),
    )

    # Legacy field consumed by older frontend builds.
    legacy_results = [
        {"id": s["chunk_id"], "content": s["text_snippet"], "score": s["combined_score"]}
        for s in sources
    ]

    # --- SAVE HISTORY ----------------------------------------------------
    if payload.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == payload.session_id).first()
        if not session:
            session = ChatSession(
                id=payload.session_id,
                tenant_id=tenant_id,
                title=query_text[:30] + "...",
                history=[],
            )
            db.add(session)
        new_history = list(session.history) if session.history else []
        new_history.append({"role": "user", "content": query_text})
        new_history.append(
            {
                "role": "ai",
                "content": answer or "Here are the search results.",
                "strategy": mode,
                "confidence": confidence,
                "sources": [
                    {"filename": s["filename"], "chunk_index": s["chunk_index"]}
                    for s in sources
                ],
            }
        )
        session.history = new_history
        session.updated_at = datetime.datetime.utcnow()
        db.commit()

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "mode": mode,
        "tenant_id": tenant_id,
        "latency_ms": latency_ms,
        "token_usage": token_usage,
        # --- Backwards-compatible fields ---
        "results": legacy_results,
        "strategy_used": mode,
    }

# ---  LIST CHATS ---
@router.get("/api/v1/chats")
async def list_chats(x_tenant_id: str = Header(..., alias="X-Tenant-ID"), db: Session = Depends(get_db)):
    chats = db.query(ChatSession).filter(ChatSession.tenant_id == x_tenant_id).order_by(ChatSession.updated_at.desc()).all()
    return [{"id": str(c.id), "title": c.title, "updated_at": str(c.updated_at)} for c in chats]

# ---  GET CHAT ---
@router.get("/api/v1/chats/{session_id}")
async def get_chat(session_id: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID"), db: Session = Depends(get_db)):
    chat = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.tenant_id == x_tenant_id).first()
    if not chat: raise HTTPException(404, "Chat not found")
    return {"history": chat.history}

# ---  DELETE CHAT ---
@router.delete("/api/v1/chats/{session_id}")
async def delete_chat(session_id: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID"), db: Session = Depends(get_db)):
    db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.tenant_id == x_tenant_id).delete()
    db.commit()
    return {"status": "success"}

# --- INGEST & DELETE DOCS ---
@router.post("/api/v1/ingest")
async def ingest_file(file: UploadFile = File(...), x_tenant_id: str = Header(..., alias="X-Tenant-ID"), db: Session = Depends(get_db)):
    doc_id = await process_document(file, x_tenant_id, db)
    return {"status": "success", "doc_id": doc_id}

@router.get("/api/v1/documents")
async def list_documents(x_tenant_id: str = Header(..., alias="X-Tenant-ID"), db: Session = Depends(get_db)):
    results = db.execute(text("SELECT id, filename, created_at FROM documents WHERE tenant_id = :tid ORDER BY created_at DESC"), {"tid": x_tenant_id}).fetchall()
    return {"documents": [{"id": str(r.id), "filename": r.filename, "created_at": str(r.created_at).split(" ")[0]} for r in results]}

@router.delete("/api/v1/documents/{doc_id}")
async def delete_document(doc_id: str, x_tenant_id: str = Header(..., alias="X-Tenant-ID"), db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM documents WHERE id = :id AND tenant_id = :tid"), {"id": doc_id, "tid": x_tenant_id})
    db.commit()
    return {"status": "success"}

# --- RENAME CHAT ---
@router.put("/api/v1/chats/{session_id}")
async def rename_chat(
    session_id: str, 
    payload: RenameChatPayload, 
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"), 
    db: Session = Depends(get_db)
):
    chat = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.tenant_id == x_tenant_id).first()
    if not chat: 
        raise HTTPException(status_code=404, detail="Chat not found")
    
    chat.title = payload.title
    db.commit()
    return {"status": "success", "title": chat.title}