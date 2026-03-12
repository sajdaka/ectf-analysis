"""Smoke test: Qdrant in-memory — create collections, upsert, query, filter.

Exercises the exact patterns the pipeline will use:
  - corpus collection with mandatory team filter
  - memory collection queried cross-team
  - knowledge collection with payload filter on relevance_tags

Qdrant in-memory mode requires string IDs to be valid UUIDs.
We use uuid5 with a fixed namespace to get deterministic UUIDs from readable keys.
"""

import os
import uuid
import pytest
from qdrant_client import QdrantClient, models

# same namespace used in chunker.py
_NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

def _uuid(key: str) -> str:
    """Deterministic UUID from a readable key."""
    return str(uuid.uuid5(_NS, key))


@pytest.fixture
def client():
    """Fresh in-memory Qdrant client per test."""
    return QdrantClient(location=":memory:")


VECTOR_SIZE = 8  # small for smoke test; real pipeline uses Anthropic embedding dim


# ── helpers ──────────────────────────────────────────────────────────────

def make_collection(client: QdrantClient, name: str):
    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(
            size=VECTOR_SIZE,
            distance=models.Distance.COSINE,
        ),
    )


def fake_vector(seed: float = 0.1) -> list[float]:
    """Deterministic fake vector for testing."""
    return [seed * (i + 1) for i in range(VECTOR_SIZE)]


# ── corpus collection: team-filtered search ──────────────────────────────

class TestCorpus:

    def test_create_and_upsert(self, client):
        make_collection(client, "corpus")

        client.upsert(
            collection_name="corpus",
            points=[
                models.PointStruct(
                    id=_uuid("teamA__abc123__dispatch_message"),
                    vector=fake_vector(0.1),
                    payload={
                        "chunk_key": "teamA__abc123__dispatch_message",
                        "team": "teamA",
                        "file": "src/messaging.c",
                        "function": "dispatch_message",
                        "code": "void dispatch_message() { memcpy(buf, data, len); }",
                    },
                ),
                models.PointStruct(
                    id=_uuid("teamB__def456__handle_request"),
                    vector=fake_vector(0.12),
                    payload={
                        "chunk_key": "teamB__def456__handle_request",
                        "team": "teamB",
                        "file": "src/handler.c",
                        "function": "handle_request",
                        "code": "void handle_request() { ... }",
                    },
                ),
            ],
        )

        info = client.get_collection("corpus")
        assert info.points_count == 2

    def test_search_with_team_filter(self, client):
        make_collection(client, "corpus")

        client.upsert(
            collection_name="corpus",
            points=[
                models.PointStruct(
                    id=_uuid("teamA__a__fn1"),
                    vector=fake_vector(0.1),
                    payload={"team": "teamA", "function": "fn1"},
                ),
                models.PointStruct(
                    id=_uuid("teamB__b__fn2"),
                    vector=fake_vector(0.1),  # identical vector
                    payload={"team": "teamB", "function": "fn2"},
                ),
            ],
        )

        # search with teamA filter — must NOT return teamB's point
        results = client.query_points(
            collection_name="corpus",
            query=fake_vector(0.1),
            query_filter=models.Filter(
                must=[models.FieldCondition(key="team", match=models.MatchValue(value="teamA"))]
            ),
            limit=10,
        )

        functions = [r.payload["function"] for r in results.points]
        assert "fn1" in functions
        assert "fn2" not in functions

    def test_upsert_idempotent(self, client):
        """Re-upserting same deterministic UUID overwrites, doesn't duplicate."""
        make_collection(client, "corpus")

        uid = _uuid("teamA__a__fn1")
        point = models.PointStruct(
            id=uid,
            vector=fake_vector(0.1),
            payload={"team": "teamA", "function": "fn1", "code": "v1"},
        )
        client.upsert(collection_name="corpus", points=[point])
        # update payload
        point.payload["code"] = "v2"
        client.upsert(collection_name="corpus", points=[point])

        info = client.get_collection("corpus")
        assert info.points_count == 1

        retrieved = client.retrieve("corpus", ids=[uid])
        assert retrieved[0].payload["code"] == "v2"


# ── memory collection: cross-team search with score thresholds ───────────

class TestMemory:

    def test_cross_team_search(self, client):
        make_collection(client, "memory")

        client.upsert(
            collection_name="memory",
            points=[
                models.PointStruct(
                    id=1,
                    vector=fake_vector(0.5),
                    payload={
                        "type": "generalization",
                        "team": None,
                        "vuln_class": "buffer_overflow",
                        "description": "Teams skip bounds check on IPC length fields",
                    },
                ),
                models.PointStruct(
                    id=2,
                    vector=fake_vector(0.9),
                    payload={
                        "type": "finding",
                        "team": "teamA",
                        "vuln_class": "use_after_free",
                        "description": "Freed pointer reused in callback",
                    },
                ),
            ],
        )

        # query without team filter — should return both
        results = client.query_points(
            collection_name="memory",
            query=fake_vector(0.5),
            limit=10,
        )
        assert len(results.points) == 2

    def test_score_threshold(self, client):
        make_collection(client, "memory")

        # insert vectors with different similarity to query
        client.upsert(
            collection_name="memory",
            points=[
                models.PointStruct(id=1, vector=fake_vector(0.5), payload={"desc": "close match"}),
                models.PointStruct(id=2, vector=fake_vector(5.0), payload={"desc": "far match"}),
            ],
        )

        results = client.query_points(
            collection_name="memory",
            query=fake_vector(0.5),
            score_threshold=0.99,
            limit=10,
        )

        # the exact match should pass threshold, the far one may not
        descs = [r.payload["desc"] for r in results.points]
        assert "close match" in descs


# ── knowledge collection: payload filter on relevance_tags ───────────────

class TestKnowledge:

    def test_tag_filter(self, client):
        make_collection(client, "knowledge")

        # knowledge uses integer IDs (CWE number)
        client.upsert(
            collection_name="knowledge",
            points=[
                models.PointStruct(
                    id=120,
                    vector=fake_vector(0.3),
                    payload={
                        "source": "cwe",
                        "cwe_id": "CWE-120",
                        "title": "Buffer Copy without Checking Size",
                        "relevance_tags": ["memcpy", "strcpy", "buffer"],
                    },
                ),
                models.PointStruct(
                    id=416,
                    vector=fake_vector(0.4),
                    payload={
                        "source": "cwe",
                        "cwe_id": "CWE-416",
                        "title": "Use After Free",
                        "relevance_tags": ["free", "dangling", "pointer"],
                    },
                ),
            ],
        )

        # filter for points where relevance_tags contains "memcpy"
        results = client.query_points(
            collection_name="knowledge",
            query=fake_vector(0.3),
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="relevance_tags",
                        match=models.MatchAny(any=["memcpy", "buffer"]),
                    )
                ]
            ),
            limit=10,
        )

        titles = [r.payload["title"] for r in results.points]
        assert "Buffer Copy without Checking Size" in titles
        assert "Use After Free" not in titles


# ── factory integration ──────────────────────────────────────────────────

class TestFactory:

    def test_factory_returns_client(self):
        from src.qdrant_factory import get_qdrant_client, reset_client

        reset_client()
        os.environ["QDRANT_MODE"] = "memory"
        c = get_qdrant_client()
        assert isinstance(c, QdrantClient)

        # singleton — same object
        c2 = get_qdrant_client()
        assert c is c2
        reset_client()
