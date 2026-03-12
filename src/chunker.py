

import hashlib
import os
from pathlib import Path

import structlog
import tree_sitter_c as tsc
from tree_sitter import Language, Parser

log = structlog.get_logger()

C_LANG = Language(tsc.language())

#makes a chunk id that is identifiable no matter similarity
def make_chunk_id(team: str, filepath: str, function_name: str) -> str:
    file_hash = hashlib.md5(filepath.encode()).hexdigest()[:6]
    return f"{team}__{file_hash}__{function_name}"


def parse_functions(source: bytes, filepath: str) -> list[dict]:

    parser = Parser(C_LANG)
    tree = parser.parse(source)

    functions = []
    includes = []

    # get the pre-processor shit
    for node in tree.root_node.children:
        if node.type == "preproc_include":
            include_text = source[node.start_byte : node.end_byte].decode(errors="replace").strip()
            includes.append(include_text)

    for node in tree.root_node.children:
        if node.type != "function_definition":
            continue

        # Extract function name from the declarator
        fn_name = _extract_function_name(node, source)
        if fn_name is None:
            log.warning("chunker.unnamed_function", file=filepath, line=node.start_point[0] + 1)
            continue

        code = source[node.start_byte : node.end_byte].decode(errors="replace")
        functions.append(
            {
                "function": fn_name,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "code": code,
                "includes": includes,
            }
        )

    return functions


def _extract_function_name(node, source: bytes) -> str | None:
    """Walk the declarator subtree to find the function identifier."""
    declarator = node.child_by_field_name("declarator")
    if declarator is None:
        return None

    # Walk down through pointer_declarator, function_declarator, etc.
    current = declarator
    while current is not None:
        if current.type == "identifier":
            return source[current.start_byte : current.end_byte].decode(errors="replace")
        # function_declarator → its first child is the name declarator
        if current.type == "function_declarator":
            inner = current.child_by_field_name("declarator")
            if inner and inner.type == "identifier":
                return source[inner.start_byte : inner.end_byte].decode(errors="replace")
            current = inner
        elif current.type in ("pointer_declarator", "parenthesized_declarator"):
            current = current.child_by_field_name("declarator") or (
                current.children[1] if len(current.children) > 1 else None
            )
        else:
            # Try first named child as fallback
            current = current.children[0] if current.children else None

    return None

#Parse a single C file and return chunk dicts ready for embedding.
def chunk_file(filepath: str, team: str) -> list[dict]:

    try:
        source = Path(filepath).read_bytes()
    except (OSError, IOError) as e:
        log.error("chunker.read_error", file=filepath, error=str(e))
        return []

    if not source.strip():
        log.info("chunker.empty_file", file=filepath)
        return []

    functions = parse_functions(source, filepath)
    if not functions:
        log.info("chunker.no_functions", file=filepath)
        return []

    chunks = []
    for fn in functions:
        chunk_id = make_chunk_id(team, filepath, fn["function"])
        chunks.append(
            {
                "id": chunk_id,
                "team": team,
                "file": filepath,
                "function": fn["function"],
                "start_line": fn["start_line"],
                "end_line": fn["end_line"],
                "code": fn["code"],
                "includes": fn["includes"],
            }
        )

    log.info("chunker.file_done", file=filepath, chunks=len(chunks))
    return chunks

#walks a repo and chunks all the files
def chunk_repo(repo_path: str, team: str) -> list[dict]:
    all_chunks = []
    repo = Path(repo_path)

    if not repo.is_dir():
        log.error("chunker: repo_not_found", path=repo_path)
        return []

    c_files = sorted(repo.rglob("*.c"))
    log.info("chunker: repo_chunking_start", team=team, c_files=len(c_files))

    for c_file in c_files:
        # Use relative path from repo root
        rel_path = str(c_file.relative_to(repo))
        chunks = chunk_file(str(c_file), team)
        # Overwrite absolute file path with relative
        for chunk in chunks:
            chunk['file'] = rel_path
        all_chunks.extend(chunks)

    log.info("chunker: repo_chunking_done", team=team, total_chunks=len(all_chunks))
    return all_chunks
