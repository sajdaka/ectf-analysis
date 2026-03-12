"""Ingestion CLI — chunks repo code and knowledge markdown into Qdrant."""

import argparse
import hashlib
import sys
from pathlib import Path

import structlog

from src.chunker import chunk_repo
from src.embedder import (
    EMBEDDING_DIM,
    embed_texts,
    ensure_collection,
    _upsert_batch,
)
from src.header_injector import inject_headers
from src.qdrant_factory import get_qdrant_client
from qdrant_client import models

log = structlog.get_logger()

CORPUS_COLLECTION = "corpus"
KNOWLEDGE_COLLECTION = "knowledge"


# ── corpus ingestion (team C code) ───────────────────────────────────────

def ingest_team(team: str, repo_path: str):
    """Full pipeline: chunk → inject headers → embed → upsert to corpus."""
    from src.embedder import upsert_chunks

    log.info("ingest.team_start", team=team, repo=repo_path)

    chunks = chunk_repo(repo_path, team)
    if not chunks:
        log.warning("ingest.no_chunks", team=team)
        return 0

    chunks = inject_headers(chunks, repo_path)
    count = upsert_chunks(chunks, CORPUS_COLLECTION)

    log.info("ingest.team_done", team=team, chunks_upserted=count)
    return count


# ── knowledge ingestion (markdown files) ─────────────────────────────────

def chunk_markdown(filepath: Path) -> list[dict]:
    """Split a markdown file into chunks by ## headings.

    Each chunk gets the file's # title prepended for context.
    Returns list of dicts with: id, source, title, section, content.
    """
    text = filepath.read_text(encoding="utf-8")
    lines = text.split("\n")

    # extract file-level title (first # heading)
    file_title = filepath.stem.replace("_", " ").title()
    for line in lines:
        if line.startswith("# ") and not line.startswith("## "):
            file_title = line.lstrip("# ").strip()
            break

    chunks = []
    current_section = None
    current_lines = []

    def flush():
        if current_lines and current_section:
            content = "\n".join(current_lines).strip()
            if content:
                # deterministic ID from file + section
                raw_id = f"knowledge__{filepath.name}__{current_section}"
                chunk_id = hashlib.md5(raw_id.encode()).hexdigest()
                chunks.append({
                    "id": int(chunk_id[:15], 16),  # Qdrant integer ID
                    "source": filepath.name,
                    "title": file_title,
                    "section": current_section,
                    "content": f"# {file_title}\n## {current_section}\n{content}",
                })

    for line in lines:
        if line.startswith("## "):
            flush()
            current_section = line.lstrip("# ").strip()
            current_lines = []
        elif current_section is not None:
            current_lines.append(line)
        # lines before first ## go into an "Overview" section
        elif line.strip() and not line.startswith("# "):
            if current_section is None:
                current_section = "Overview"
            current_lines.append(line)

    flush()

    # if no ## headings, treat entire file as one chunk
    if not chunks and text.strip():
        raw_id = f"knowledge__{filepath.name}__full"
        chunk_id = hashlib.md5(raw_id.encode()).hexdigest()
        chunks.append({
            "id": int(chunk_id[:15], 16),
            "source": filepath.name,
            "title": file_title,
            "section": "Full Document",
            "content": text.strip(),
        })

    return chunks


def ingest_knowledge(knowledge_dir: str = "./knowledge"):
    """Ingest all markdown files from knowledge directory into Qdrant."""
    kdir = Path(knowledge_dir)
    if not kdir.is_dir():
        log.error("ingest.knowledge_dir_not_found", path=knowledge_dir)
        return 0

    ensure_collection(KNOWLEDGE_COLLECTION)

    md_files = sorted(kdir.glob("*.md"))
    # skip README
    md_files = [f for f in md_files if f.name.lower() != "readme.md"]

    log.info("ingest.knowledge_start", files=len(md_files))

    all_chunks = []
    for md_file in md_files:
        chunks = chunk_markdown(md_file)
        all_chunks.extend(chunks)
        log.info("ingest.knowledge_file", file=md_file.name, chunks=len(chunks))

    if not all_chunks:
        log.warning("ingest.knowledge_empty")
        return 0

    # embed and upsert
    texts = [c["content"] for c in all_chunks]
    vectors = embed_texts(texts)

    points = []
    for chunk, vector in zip(all_chunks, vectors):
        points.append(
            models.PointStruct(
                id=chunk["id"],
                vector=vector.tolist(),
                payload={
                    "source": chunk["source"],
                    "title": chunk["title"],
                    "section": chunk["section"],
                    "content": chunk["content"],
                },
            )
        )

    _upsert_batch(KNOWLEDGE_COLLECTION, points)
    log.info("ingest.knowledge_done", total_chunks=len(points))
    return len(points)


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ingest team repos or knowledge base into Qdrant")
    sub = parser.add_subparsers(dest="command")

    team_p = sub.add_parser("team", help="Ingest a team's C codebase")
    team_p.add_argument("--name", required=True, help="Team name")
    team_p.add_argument("--repo-path", required=True, help="Path to team repo")

    sub.add_parser("knowledge", help="Ingest knowledge base markdown files")

    args = parser.parse_args()

    if args.command == "team":
        count = ingest_team(args.name, args.repo_path)
        print(f"Ingested {count} chunks for {args.name}")
    elif args.command == "knowledge":
        count = ingest_knowledge()
        print(f"Ingested {count} knowledge chunks")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
