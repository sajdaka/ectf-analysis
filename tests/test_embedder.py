"""Tests for embedder — embedding + Qdrant upsert pipeline."""

import os
import pytest
from qdrant_client import models

from src.embedder import (
    EMBEDDING_DIM,
    _build_embed_text,
    embed_texts,
    ensure_collection,
    upsert_chunks,
)
from src.qdrant_factory import get_qdrant_client, reset_client


@pytest.fixture(autouse=True)
def fresh_qdrant():
    """Reset Qdrant client to in-memory for each test."""
    reset_client()
    os.environ["QDRANT_MODE"] = "memory"
    yield
    reset_client()


def _make_chunk(fn_name="dispatch_message", team="teamA", code="void dispatch_message() {}"):
    from src.chunker import chunk_id_to_uuid, make_chunk_id
    readable = make_chunk_id(team, "src/main.c", fn_name)
    return {
        "id": chunk_id_to_uuid(readable),
        "chunk_key": readable,
        "team": team,
        "file": "src/main.c",
        "function": fn_name,
        "start_line": 1,
        "end_line": 3,
        "code": code,
        "includes": ['#include "messaging.h"'],
        "injected_context": "typedef struct { int len; } msg_t;",
    }


# ── embed_texts ──────────────────────────────────────────────────────────

def test_embed_texts_returns_vectors():
    vecs = embed_texts(["hello world"])
    assert len(vecs) == 1
    assert len(vecs[0]) == EMBEDDING_DIM


def test_embed_texts_batch():
    vecs = embed_texts(["one", "two", "three"])
    assert len(vecs) == 3
    for v in vecs:
        assert len(v) == EMBEDDING_DIM


# ── _build_embed_text ────────────────────────────────────────────────────

def test_build_embed_text_with_context():
    chunk = _make_chunk()
    text = _build_embed_text(chunk)
    assert "msg_t" in text
    assert "dispatch_message" in text


def test_build_embed_text_without_context():
    chunk = _make_chunk()
    chunk["injected_context"] = ""
    text = _build_embed_text(chunk)
    assert "dispatch_message" in text
    assert "msg_t" not in text


# ── ensure_collection ────────────────────────────────────────────────────

def test_ensure_collection_creates():
    ensure_collection("test_corpus")
    client = get_qdrant_client()
    names = [c.name for c in client.get_collections().collections]
    assert "test_corpus" in names


def test_ensure_collection_idempotent():
    ensure_collection("test_corpus")
    ensure_collection("test_corpus")  # should not raise
    client = get_qdrant_client()
    names = [c.name for c in client.get_collections().collections]
    assert names.count("test_corpus") == 1


# ── upsert_chunks (integration) ─────────────────────────────────────────

def test_upsert_single_chunk():
    chunk = _make_chunk()
    count = upsert_chunks([chunk], "test_corpus")
    assert count == 1

    client = get_qdrant_client()
    info = client.get_collection("test_corpus")
    assert info.points_count == 1


def test_upsert_multiple_chunks():
    chunks = [
        _make_chunk("fn1", code="void fn1() { memcpy(a, b, n); }"),
        _make_chunk("fn2", code="int fn2() { return validate(x); }"),
        _make_chunk("fn3", code="void fn3() { free(ptr); }"),
    ]
    count = upsert_chunks(chunks, "test_corpus")
    assert count == 3

    client = get_qdrant_client()
    info = client.get_collection("test_corpus")
    assert info.points_count == 3


def test_upsert_idempotent():
    chunk = _make_chunk()
    upsert_chunks([chunk], "test_corpus")
    upsert_chunks([chunk], "test_corpus")  # same ID, should overwrite

    client = get_qdrant_client()
    info = client.get_collection("test_corpus")
    assert info.points_count == 1


def test_upsert_then_search():
    chunks = [
        _make_chunk("dispatch_message", code="void dispatch_message(msg_t *msg) { memcpy(buf, msg->data, msg->len); }"),
        _make_chunk("validate_length", code="int validate_length(int len) { if (len > 1024) return -1; return 0; }"),
    ]
    upsert_chunks(chunks, "test_corpus")

    # search for buffer-related code
    from src.embedder import embed_texts
    query_vec = embed_texts(["buffer overflow memcpy"])[0].tolist()

    client = get_qdrant_client()
    results = client.query_points(
        collection_name="test_corpus",
        query=query_vec,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="team", match=models.MatchValue(value="teamA"))]
        ),
        limit=5,
    )

    assert len(results.points) > 0
    # dispatch_message (has memcpy) should rank higher than validate_length
    top_fn = results.points[0].payload["function"]
    assert top_fn == "dispatch_message"
