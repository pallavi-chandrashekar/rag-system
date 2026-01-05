import os
from openai import OpenAI
from typing import List, Dict

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def rewrite_query(user_query: str, history: List[Dict[str, str]]) -> str:
    """Coreference resolution (Standard Contextual Rewriting)"""
    if not history:
        return user_query

    recent_history = history[-3:]
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])

    prompt = f"""
    Rewrite the following follow-up question into a standalone search query based on the history.
    If the question is already standalone, return it as is.
    History: {history_text}
    Follow-up: {user_query}
    Standalone Query:
    """
    
    return _call_llm(prompt) or user_query

def generate_multi_queries(query: str, n: int = 3) -> List[str]:
    """Generates multiple variations of the query to broaden search coverage."""
    prompt = f"""
    You are an AI assistant. Generate {n} different versions of the following user question to retrieve relevant documents from a vector database. 
    Focus on different keywords and perspectives.
    Return only the questions separated by newlines.
    Original Question: {query}
    """
    response = _call_llm(prompt)
    return [q.strip() for q in response.split('\n') if q.strip()] if response else [query]

def decompose_query(query: str) -> List[str]:
    """Breaks a complex query into simple sub-questions."""
    prompt = f"""
    Decompose the following complex question into a set of simple, standalone sub-questions that can be answered independently.
    Return only the sub-questions separated by newlines.
    Complex Question: {query}
    """
    response = _call_llm(prompt)
    return [q.strip() for q in response.split('\n') if q.strip()] if response else [query]

def generate_hyde_answer(query: str) -> str:
    """Generates a hypothetical answer to be used for vector search."""
    prompt = f"""
    Write a brief, hypothetical passage that answers the following question. 
    Focus on including keywords and factual patterns likely to appear in a relevant technical document.
    Do not include the question itself.
    Question: {query}
    """
    return _call_llm(prompt) or query

def _call_llm(prompt: str) -> str:
    """Helper to call OpenAI"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM Error: {e}")
        return None