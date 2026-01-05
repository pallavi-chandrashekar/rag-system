import os
from typing import List
from openai import OpenAI

# Simple singleton wrapper
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embeddings(texts: List[str], model="text-embedding-3-small") -> List[List[float]]:
    """
    Generates embeddings for a list of texts.
    replace with HuggingFace implementation if you want to run locally.
    """
    if not texts:
        return []
        
    # OpenAI requires stripping newlines for best results
    cleaned_texts = [t.replace("\n", " ") for t in texts]
    
    response = client.embeddings.create(input=cleaned_texts, model=model)
    return [data.embedding for data in response.data]