from backend.services.llm import chat_with_llm

def route_query(query: str):
    # 1. Normalize
    q = query.lower().strip()
    print(f"DEBUG: Routing query '{q}'") # <--- DEBUG PRINT

    # 2. FAST PATH - GREETINGS (Hardcoded)
    greetings = ["hi", "hello", "hey", "how are you", "how are you doing", "hola", "greetings", "good morning", "good evening"]
    # Check exact match OR start match
    if q in greetings or any(q.startswith(g + " ") for g in greetings):
        print("DEBUG: Hit Fast-Path -> 'llm_only'")
        return "llm_only"

    # 3. FAST PATH - SUMMARY (Hardcoded)
    summary_triggers = ["summarize", "summary", "tldr", "overview", "explain this document", "what is this file about"]
    if q in summary_triggers or any(q.startswith(s) for s in summary_triggers):
        print("DEBUG: Hit Fast-Path -> 'summary'")
        return "summary"

    # 4. LLM ROUTER (Slow Path)
    print("DEBUG: Fast-Path missed. Asking LLM...")
    system_prompt = """
    You are a Router. Classify the user query into ONE of these strategies:
    1. "llm_only": Greetings, small talk, or general knowledge NOT about files.
    2. "summary": Requests to summarize or explain the document content.
    3. "hybrid": Specific questions about the uploaded files.
    
    Output ONLY the strategy name (lowercase).
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Query: {query}"}
    ]
    
    try:
        response = chat_with_llm(messages).strip().lower()
        print(f"DEBUG: LLM decided -> '{response}'")
        if "llm_only" in response: return "llm_only"
        if "summary" in response: return "summary"
    except Exception as e:
        print(f"DEBUG: Router Error {e}")

    return "hybrid"