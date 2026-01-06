import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chat_with_llm(messages: list, model="gpt-3.5-turbo"):
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"LLM Error: {e}")
        return "I'm having trouble connecting to my brain right now."