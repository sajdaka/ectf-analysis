"""All Qdrant retrieval functions with score-threshold splitting for Tier 2A/2B."""

import structlog
from qdrant_client import models

from src.config import (
    CORPUS_COLLECTION,
    KNOWLEDGE_COLLECTION,
    MEMORY_COLLECTION,
    TIER2A_SCORE_THRESHOLD,
    TIER2B_SCORE_THRESHOLD,
)
from src.embedder import embed_texts
from src.qdrant_factory import get_qdrant_client

log = structlog.get_logger()


def _embed_query(query: str) -> list[float]:
    """Embed a single query string and return as list of floats."""
    return embed_texts([query])[0].tolist()


# ── Tier 3: corpus (team-filtered) ──────────────────────────────────────

def retrieve_corpus(query: str, team: str, limit: int = 8) -> list[dict]:
    """Search corpus collection with mandatory team filter.

    Returns list of dicts with: score, function, file, code, start_line, end_line.
    """
    client = get_qdrant_client()
    query_vec = _embed_query(query)

    results = client.query_points(
        collection_name=CORPUS_COLLECTION,
        query=query_vec,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="team", match=models.MatchValue(value=team))]
        ),
        limit=limit,
        with_payload=True,
    )

    hits = []
    for r in results.points:
        hits.append({
            "score": r.score,
            "function": r.payload.get("function"),
            "file": r.payload.get("file"),
            "code": r.payload.get("code"),
            "start_line": r.payload.get("start_line"),
            "end_line": r.payload.get("end_line"),
        })

    log.info("retrieval.corpus", team=team, query=query[:60], hits=len(hits))
    return hits


# ── Tier 2: cluster memory (cross-team, score-split) ────────────────────

def retrieve_cluster_memory(query: str, limit: int = 10) -> tuple[list[dict], list[dict]]:
    """Search memory collection without team filter.

    Returns (directly_relevant, background):
        - directly_relevant: score > TIER2A threshold, full detail
        - background: score between TIER2B and TIER2A, one-line summaries
    """
    client = get_qdrant_client()
    query_vec = _embed_query(query)

    results = client.query_points(
        collection_name=MEMORY_COLLECTION,
        query=query_vec,
        score_threshold=TIER2B_SCORE_THRESHOLD,
        limit=limit,
        with_payload=True,
    )

    directly_relevant = []
    background = []

    for r in results.points:
        entry = {
            "score": r.score,
            "type": r.payload.get("type"),
            "vuln_class": r.payload.get("vuln_class"),
            "description": r.payload.get("description"),
            "generalization": r.payload.get("generalization"),
            "confidence": r.payload.get("confidence"),
            "evidence_summary": r.payload.get("evidence_summary"),
            "hunt_targets": r.payload.get("hunt_targets"),
            "team": r.payload.get("team"),
            "severity": r.payload.get("severity"),
        }

        if r.score >= TIER2A_SCORE_THRESHOLD:
            directly_relevant.append(entry)
        else:
            # background gets condensed to one-line
            background.append({
                "score": r.score,
                "vuln_class": entry["vuln_class"],
                "description": entry["description"],
            })

    log.info("retrieval.memory", query=query[:60],
             tier2a=len(directly_relevant), tier2b=len(background))
    return directly_relevant, background


# ── Tier 1: knowledge base ──────────────────────────────────────────────

def retrieve_knowledge(query: str, limit: int = 3) -> list[dict]:
    """Search knowledge collection (CWEs, ARM manual, eCTF rules).

    Returns list of dicts with: score, source, title, section, content.
    """
    client = get_qdrant_client()
    query_vec = _embed_query(query)

    results = client.query_points(
        collection_name=KNOWLEDGE_COLLECTION,
        query=query_vec,
        limit=limit,
        with_payload=True,
    )

    hits = []
    for r in results.points:
        hits.append({
            "score": r.score,
            "source": r.payload.get("source"),
            "title": r.payload.get("title"),
            "section": r.payload.get("section"),
            "content": r.payload.get("content"),
        })

    log.info("retrieval.knowledge", query=query[:60], hits=len(hits))
    return hits
