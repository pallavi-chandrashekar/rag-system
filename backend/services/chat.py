import os
from openai import OpenAI
from typing import List, Dict

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def rewrite_query(user_query: str, history: List[Dict[str, str]]) -> str:
    if not history:
        return user_query

    recent_history = history[-3:]
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])

    prompt = f"""
    Rewrite the following follow-up question into a standalone search query based on the history.
    History: {history_text}
    Follow-up: {user_query}
    Standalone Query:
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except:
        return user_query