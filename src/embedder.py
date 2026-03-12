"""FastEmbed local embeddings + Qdrant upsert with batching."""

import os

import numpy as np
import structlog
from fastembed import TextEmbedding
from qdrant_client import models
from tenacity import retry, stop_after_attempt, wait_exponential

from src.qdrant_factory import get_qdrant_client

log = structlog.get_logger()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = 384  # bge-small-en-v1.5
BATCH_SIZE = 50
CORPUS_COLLECTION = "corpus"

_model = None


def get_embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
        log.info("embedder.loading_model", model=EMBEDDING_MODEL)
        _model = TextEmbedding(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: list[str]) -> list[np.ndarray]:
    """Embed a list of texts, returns list of numpy arrays."""
    model = get_embedding_model()
    return list(model.embed(texts))


def ensure_collection(collection_name: str = CORPUS_COLLECTION):
    """Create collection if it doesn't exist."""
    client = get_qdrant_client()
    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=EMBEDDING_DIM,
                distance=models.Distance.COSINE,
            ),
        )
        log.info("embedder.collection_created", collection=collection_name)


def _build_embed_text(chunk: dict) -> str:
    """Build the text to embed for a chunk — code + injected header context."""
    parts = []
    if chunk.get("injected_context"):
        parts.append(chunk["injected_context"])
    parts.append(chunk["code"])
    return "\n".join(parts)


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
def _upsert_batch(collection_name: str, points: list[models.PointStruct]):
    client = get_qdrant_client()
    client.upsert(collection_name=collection_name, points=points)


def upsert_chunks(chunks: list[dict], collection_name: str = CORPUS_COLLECTION):
    """Embed and upsert chunks to Qdrant in batches.

    Each chunk dict must have: id (UUID str), chunk_key, team, file,
    function, start_line, end_line, code, includes, injected_context.
    """
    ensure_collection(collection_name)

    total = len(chunks)
    upserted = 0

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [_build_embed_text(c) for c in batch]
        vectors = embed_texts(texts)

        points = []
        for chunk, vector in zip(batch, vectors):
            points.append(
                models.PointStruct(
                    id=chunk["id"],
                    vector=vector.tolist(),
                    payload={
                        "chunk_key": chunk["chunk_key"],
                        "team": chunk["team"],
                        "file": chunk["file"],
                        "function": chunk["function"],
                        "start_line": chunk["start_line"],
                        "end_line": chunk["end_line"],
                        "code": chunk["code"],
                        "includes": chunk.get("includes", []),
                        "injected_context": chunk.get("injected_context", ""),
                    },
                )
            )

        _upsert_batch(collection_name, points)
        upserted += len(points)
        log.info("embedder.batch_upserted", batch=i // BATCH_SIZE + 1,
                 points=len(points), progress=f"{upserted}/{total}")

    log.info("embedder.done", collection=collection_name, total_upserted=upserted)
    return upserted
