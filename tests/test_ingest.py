"""Tests for ingest — team code + knowledge markdown ingestion."""

import os
import tempfile
from pathlib import Path

import pytest

from src.ingest import chunk_markdown, ingest_knowledge, ingest_team
from src.qdrant_factory import get_qdrant_client, reset_client


@pytest.fixture(autouse=True)
def fresh_qdrant():
    reset_client()
    os.environ["QDRANT_MODE"] = "memory"
    yield
    reset_client()


SAMPLE_C = b"""\
#include <stdint.h>

void dispatch_message(uint8_t *buf, int len) {
    char tmp[256];
    memcpy(tmp, buf, len);
}

int validate(int x) {
    return x > 0 ? x : -1;
}
"""

SAMPLE_HEADER = b"""\
#ifndef MSG_H
#define MSG_H
typedef struct { int len; uint8_t *data; } msg_t;
#endif
"""

SAMPLE_MD = """\
# eCTF 2026 — Security Requirements

Security requirements are important.

## Security Requirement 1: Permission Enforcement
An attacker should not be able to perform any file action without valid permissions.

## Security Requirement 2: PIN Protection
No PIN-protected action should be completed without prior knowledge of the PIN.
"""


# ── chunk_markdown ───────────────────────────────────────────────────────

def test_chunk_markdown_splits_by_heading():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(SAMPLE_MD)
        f.flush()
        chunks = chunk_markdown(Path(f.name))

    sections = [c["section"] for c in chunks]
    assert "Security Requirement 1: Permission Enforcement" in sections
    assert "Security Requirement 2: PIN Protection" in sections


def test_chunk_markdown_includes_title():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(SAMPLE_MD)
        f.flush()
        chunks = chunk_markdown(Path(f.name))

    for chunk in chunks:
        assert "Security Requirements" in chunk["title"]
        # content should have title prepended
        assert chunk["content"].startswith("# ")


def test_chunk_markdown_deterministic_ids():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(SAMPLE_MD)
        f.flush()
        chunks1 = chunk_markdown(Path(f.name))
        chunks2 = chunk_markdown(Path(f.name))

    ids1 = [c["id"] for c in chunks1]
    ids2 = [c["id"] for c in chunks2]
    assert ids1 == ids2


def test_chunk_markdown_no_headings():
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write("# Title\n\nJust a paragraph with no subheadings.\n")
        f.flush()
        chunks = chunk_markdown(Path(f.name))

    assert len(chunks) == 1
    assert chunks[0]["section"] in ("Overview", "Full Document")


def test_chunk_markdown_overview_text():
    md = "# Title\n\nSome overview text before headings.\n\n## Section 1\nContent.\n"
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(md)
        f.flush()
        chunks = chunk_markdown(Path(f.name))

    sections = [c["section"] for c in chunks]
    assert "Overview" in sections
    assert "Section 1" in sections


# ── ingest_team (integration) ────────────────────────────────────────────

def test_ingest_team():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        src = repo / "src"
        src.mkdir()
        (src / "main.c").write_bytes(SAMPLE_C)
        inc = repo / "include"
        inc.mkdir()
        (inc / "msg.h").write_bytes(SAMPLE_HEADER)

        count = ingest_team("test_team", str(repo))
        assert count == 2  # dispatch_message + validate

        client = get_qdrant_client()
        info = client.get_collection("corpus")
        assert info.points_count == 2


def test_ingest_team_empty_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        count = ingest_team("empty_team", tmpdir)
        assert count == 0


# ── ingest_knowledge (integration) ───────────────────────────────────────

def test_ingest_knowledge():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "security_reqs.md").write_text(SAMPLE_MD)
        (Path(tmpdir) / "README.md").write_text("# Readme\nIgnored.\n")

        count = ingest_knowledge(tmpdir)
        assert count > 0  # should have chunks from security_reqs.md

        client = get_qdrant_client()
        info = client.get_collection("knowledge")
        assert info.points_count == count


def test_ingest_knowledge_searchable():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "security_reqs.md").write_text(SAMPLE_MD)
        ingest_knowledge(tmpdir)

        from src.embedder import embed_texts
        query_vec = embed_texts(["PIN protection authentication"])[0].tolist()

        client = get_qdrant_client()
        results = client.query_points(
            collection_name="knowledge",
            query=query_vec,
            limit=3,
        )

        assert len(results.points) > 0
        # PIN section should rank high
        top = results.points[0].payload
        assert "PIN" in top["content"]
