"""FastEmbed local embeddings + Qdrant upsert with batching."""

import os

import numpy as np
import structlog
from fastembed import TextEmbedding
from qdrant_client import models
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import CORPUS_COLLECTION
from src.qdrant_factory import get_qdrant_client

log = structlog.get_logger()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
BATCH_SIZE = 50

_model = None
_embedding_dim = None


def get_embedding_model() -> TextEmbedding:
    global _model
    if _model is None:
        log.info("embedder.loading_model", model=EMBEDDING_MODEL)
        _model = TextEmbedding(EMBEDDING_MODEL)
    return _model


def get_embedding_dim() -> int:
    """Derive embedding dimension from the loaded model."""
    global _embedding_dim
    if _embedding_dim is None:
        vecs = list(get_embedding_model().embed(["dim probe"]))
        _embedding_dim = len(vecs[0])
    return _embedding_dim


def embed_texts(texts: list[str]) -> list[np.ndarray]:
    """Embed a list of texts, returns list of numpy arrays."""
    model = get_embedding_model()
    return list(model.embed(texts))


def ensure_collection(collection_name: str = CORPUS_COLLECTION):
    """Create collection if it doesn't exist."""
    client = get_qdrant_client()
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=get_embedding_dim(),
                distance=models.Distance.COSINE,
            ),
        )
        log.info("embedder.collection_created", collection=collection_name)


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, max=30))
def upsert_batch(collection_name: str, points: list[models.PointStruct]):
    """Upsert a batch of pre-built PointStructs to Qdrant with retry."""
    client = get_qdrant_client()
    client.upsert(collection_name=collection_name, points=points)


def embed_and_upsert(chunks: list[dict], collection_name: str, payload_fn):
    """Generic embed + upsert. payload_fn(chunk) returns the payload dict for each chunk.

    Each chunk must have 'id' and a text field buildable by payload_fn or _build_embed_text.
    """
    ensure_collection(collection_name)

    total = len(chunks)
    upserted = 0

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i : i + BATCH_SIZE]
        texts = [c.get("content") or _build_embed_text(c) for c in batch]
        vectors = embed_texts(texts)

        points = [
            models.PointStruct(
                id=chunk["id"],
                vector=vector.tolist(),
                payload=payload_fn(chunk),
            )
            for chunk, vector in zip(batch, vectors)
        ]

        upsert_batch(collection_name, points)
        upserted += len(points)
        log.info("embedder.batch_upserted", batch=i // BATCH_SIZE + 1,
                 points=len(points), progress=f"{upserted}/{total}")

    log.info("embedder.done", collection=collection_name, total_upserted=upserted)
    return upserted


def _build_embed_text(chunk: dict) -> str:
    """Build the text to embed for a code chunk — code + injected header context."""
    parts = []
    if chunk.get("injected_context"):
        parts.append(chunk["injected_context"])
    parts.append(chunk["code"])
    return "\n".join(parts)


def _corpus_payload(chunk: dict) -> dict:
    return {
        "chunk_key": chunk["chunk_key"],
        "team": chunk["team"],
        "file": chunk["file"],
        "function": chunk["function"],
        "start_line": chunk["start_line"],
        "end_line": chunk["end_line"],
        "code": chunk["code"],
        "includes": chunk.get("includes", []),
        "injected_context": chunk.get("injected_context", ""),
    }


def upsert_chunks(chunks: list[dict], collection_name: str = CORPUS_COLLECTION):
    """Embed and upsert code chunks to Qdrant in batches."""
    return embed_and_upsert(chunks, collection_name, _corpus_payload)
