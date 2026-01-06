from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Header, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Dict, Optional
import datetime
import uuid

from backend.database import get_db
from backend.models import ChatSession # <--- Import New Model
from backend.services.rag import hybrid_search, multi_query_search
from backend.services.chat import rewrite_query, generate_multi_queries, decompose_query
from backend.services.ingestion import process_document
from backend.services.router import route_query
from backend.services.llm import chat_with_llm

router = APIRouter()

class SearchPayload(BaseModel):
    text: str
    tenant_id: str
    session_id: Optional[str] = None # <--- New Field
    chat_history: List[Dict[str, str]] = []

class RenameChatPayload(BaseModel):
    title: str

# --- 1. SEARCH (Now Saves History) ---
@router.post("/api/v1/search")
async def search_rag(payload: SearchPayload, db: Session = Depends(get_db)):
    query_text = payload.text.strip()
    
    # --- ROUTING LOGIC ---
    q_lower = query_text.lower()
    strategy = "hybrid"
    summary_triggers = ["summarize", "summary", "tldr", "overview"]
    
    if q_lower in summary_triggers or any(q_lower.startswith(s) for s in summary_triggers):
        strategy = "summary"
    elif any(x in q_lower for x in ["hi", "hello", "hey", "how are you"]):
        strategy = "llm_only"
    else:
        strategy = route_query(query_text)

    # --- EXECUTE STRATEGY ---
    answer = ""
    results = []
    
    if strategy == "llm_only":
        msgs = [{"role": ("assistant" if m["role"]=="ai" else "user"), "content": m["content"]} for m in payload.chat_history]
        msgs.append({"role": "user", "content": query_text})
        answer = chat_with_llm(msgs)
    
    elif strategy == "summary":
        docs = db.execute(text("SELECT content FROM chunks WHERE tenant_id = :tid LIMIT 15"), {"tid": payload.tenant_id}).fetchall()
        if docs:
            combined = "\n\n".join([r.content for r in docs])
            answer = chat_with_llm([{"role": "user", "content": f"Summarize:\n{combined}"}])
        else:
            answer = "No documents found to summarize."

    else:
        # Search Strategy
        standalone_query = query_text
        if payload.chat_history:
            standalone_query = rewrite_query(query_text, payload.chat_history)
        
        if strategy == "multi_query":
            q_list = generate_multi_queries(standalone_query)
            results = multi_query_search(db, q_list, payload.tenant_id)
        else:
            results = hybrid_search(db, standalone_query, payload.tenant_id)
            
        if not results:
            # Fallback
            msgs = [{"role": ("assistant" if m["role"]=="ai" else "user"), "content": m["content"]} for m in payload.chat_history]
            msgs.append({"role": "user", "content": query_text})
            answer = chat_with_llm(msgs)
            strategy = "llm_fallback"

    # --- SAVE HISTORY TO DB ---
    if payload.session_id:
        # Get or Create Session
        session = db.query(ChatSession).filter(ChatSession.id == payload.session_id).first()
        if not session:
            session = ChatSession(
                id=payload.session_id, 
                tenant_id=payload.tenant_id, 
                title=query_text[:30] + "...",
                history=[]
            )
            db.add(session)
        
        # Update History
        new_history = list(session.history) if session.history else []
        new_history.append({"role": "user", "content": query_text})
        
        # If we have results, format them into the answer for storage
        final_response = answer
        if not final_response and results:
             # If no direct LLM answer but we have results, just store a placeholder or the first result
             # Usually frontend constructs the view, but for storage we should be explicit.
             # For now, let's just store a generic "See results" or the raw answer if exists.
             final_response = answer if answer else "Here are the search results."

        new_history.append({"role": "ai", "content": final_response, "strategy": strategy, "results": [r['content'] for r in results[:1]]}) # Store minimal result data
        
        session.history = new_history
        session.updated_at = datetime.datetime.utcnow()
        db.commit()

    return {
        "answer": answer,
        "results": results,
        "strategy_used": strategy
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