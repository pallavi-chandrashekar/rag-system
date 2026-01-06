from sentence_transformers import SentenceTransformer

# Load the local model (384 dimensions)
# It downloads automatically on the first run
print("Loading Local Embedding Model (all-MiniLM-L6-v2)...")
model = SentenceTransformer('all-MiniLM-L6-v2')

def get_embeddings(texts: list) -> list:
    """
    Generates embeddings locally using the CPU/GPU.
    Returns: List of Lists (e.g., [[0.1, ...], [0.3, ...]])
    """
    if not texts:
        return []
        
    # Clean newlines just in case
    cleaned_texts = [t.replace("\n", " ") for t in texts]
    
    # Generate embeddings
    embeddings = model.encode(cleaned_texts)
    
    # Convert numpy array to standard Python list for JSON serialization
    return embeddings.tolist()