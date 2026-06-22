"""Local embedding generation (sentence-transformers).

The model is loaded lazily on first use so that importing this module (and the
services that depend on it) stays cheap and dependency-free for unit tests and
tooling. Only `get_embeddings` requires the heavy `sentence-transformers`
dependency and downloads the model on first call.
"""

from backend.config import settings

_model = None


def _get_model():
    """Load and cache the embedding model on first use."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        print(f"Loading Local Embedding Model ({settings.LOCAL_EMBEDDING_MODEL})...")
        _model = SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)
    return _model


def get_embeddings(texts: list) -> list:
    """Generate embeddings locally. Returns a list of float lists."""
    if not texts:
        return []

    cleaned_texts = [t.replace("\n", " ") for t in texts]
    embeddings = _get_model().encode(cleaned_texts)
    return embeddings.tolist()
