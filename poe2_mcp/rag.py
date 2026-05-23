"""ChromaDB-backed semantic search over the local corpus."""
from __future__ import annotations

from pathlib import Path

_collection = None
_DB_PATH = Path(__file__).parent.parent / "chroma_db"
_COLLECTION_NAME = "poe2"


def _get_collection():
    global _collection
    if _collection is not None:
        return _collection
    if not _DB_PATH.exists():
        return None
    try:
        import chromadb
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        client = chromadb.PersistentClient(path=str(_DB_PATH))
        _collection = client.get_collection(
            name=_COLLECTION_NAME,
            embedding_function=DefaultEmbeddingFunction(),
        )
    except Exception:
        return None
    return _collection


def query(text: str, n_results: int = 5, category: str = "") -> list[dict]:
    col = _get_collection()
    if col is None:
        return []
    where = {"category": category} if category else None
    results = col.query(
        query_texts=[text],
        n_results=min(n_results, col.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        out.append({
            "title": meta["title"],
            "category": meta["category"],
            "content": doc,
            "score": round(1.0 - dist, 3),
        })
    return out


def is_available() -> bool:
    return _get_collection() is not None
