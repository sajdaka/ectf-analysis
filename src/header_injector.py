"""Resolve #include directives, extract typedefs/struct defs, inject into chunks."""

import re
from pathlib import Path

import structlog
import tree_sitter_c as tsc
from tree_sitter import Language, Parser

log = structlog.get_logger()

C_LANG = Language(tsc.language())

# node types we want to extract from headers
_EXTRACTABLE = frozenset({
    "type_definition",      # typedef ... ;
    "struct_specifier",     # struct foo { ... };
    "enum_specifier",       # enum foo { ... };
    "union_specifier",      # union foo { ... };
    "preproc_def",          # #define macros (useful for constants/magic numbers)
})

# matches the header name from an include directive
# handles both #include "foo.h" and #include <foo.h>
_INCLUDE_RE = re.compile(r'#include\s+["<]([^">]+)[">]')


def find_header(header_name: str, repo_path: Path) -> Path | None:
    """Find a header file in the repo by name. Searches the whole tree."""
    # strip any leading path components — just match the filename
    base = Path(header_name).name
    matches = list(repo_path.rglob(base))
    if not matches:
        return None
    # prefer shortest path (closest to root)
    return min(matches, key=lambda p: len(p.parts))


def extract_definitions(header_path: Path) -> list[str]:
    """Parse a header file and extract typedef/struct/enum/union/define nodes."""
    try:
        source = header_path.read_bytes()
    except (OSError, IOError) as e:
        log.warning("header_injector.read_error", file=str(header_path), error=str(e))
        return []

    if not source.strip():
        return []

    parser = Parser(C_LANG)
    tree = parser.parse(source)

    definitions = []
    _walk_nodes(tree.root_node.children, source, definitions)
    return definitions


# node types that contain nested definitions (include guards, conditional compilation)
_CONTAINER_TYPES = frozenset({
    "preproc_ifdef", "preproc_ifndef", "preproc_if", "preproc_else", "preproc_elif",
})


def _walk_nodes(nodes, source: bytes, definitions: list[str]):
    """Recursively walk nodes, descending into preprocessor guard blocks."""
    for node in nodes:
        if node.type in _EXTRACTABLE:
            text = source[node.start_byte : node.end_byte].decode(errors="replace").strip()
            definitions.append(text)
        elif node.type == "declaration":
            for child in node.children:
                if child.type in ("struct_specifier", "enum_specifier", "union_specifier"):
                    if _has_body(child):
                        text = source[node.start_byte : node.end_byte].decode(errors="replace").strip()
                        definitions.append(text)
                        break
        elif node.type in _CONTAINER_TYPES:
            _walk_nodes(node.children, source, definitions)


def _has_body(node) -> bool:
    """Check if a struct/enum/union specifier has a field_declaration_list (body)."""
    for child in node.children:
        if child.type in ("field_declaration_list", "enumerator_list"):
            return True
    return False


def parse_include_names(includes: list[str]) -> list[str]:
    """Extract header filenames from include directive strings."""
    names = []
    for inc in includes:
        m = _INCLUDE_RE.search(inc)
        if m:
            names.append(m.group(1))
    return names


def inject_headers(chunks: list[dict], repo_path: str) -> list[dict]:
    """For each chunk, resolve its includes and inject extracted definitions.

    Adds 'injected_context' key to each chunk dict.
    Modifies chunks in place and returns them.
    """
    repo = Path(repo_path)
    # cache: header_name -> list of definition strings
    header_cache: dict[str, list[str]] = {}

    for chunk in chunks:
        header_names = parse_include_names(chunk.get("includes", []))
        all_defs = []

        for hname in header_names:
            # skip system headers — we only resolve project headers
            if hname.startswith("std") or "/" not in hname and hname.endswith(".h"):
                # could be a project header with just a name like "messaging.h"
                pass
            # always skip obvious system headers
            if hname in ("stdio.h", "stdlib.h", "string.h", "stdint.h", "stdbool.h",
                         "stddef.h", "math.h", "assert.h", "errno.h", "signal.h",
                         "time.h", "limits.h", "float.h", "ctype.h", "unistd.h",
                         "fcntl.h", "sys/types.h", "sys/stat.h", "sys/socket.h",
                         "pthread.h", "semaphore.h"):
                continue

            if hname not in header_cache:
                hpath = find_header(hname, repo)
                if hpath is None:
                    log.debug("header_injector.header_not_found", header=hname,
                              chunk_fn=chunk.get("function"))
                    header_cache[hname] = []
                else:
                    defs = extract_definitions(hpath)
                    header_cache[hname] = defs
                    log.debug("header_injector.extracted", header=hname, definitions=len(defs))

            all_defs.extend(header_cache[hname])

        chunk["injected_context"] = "\n".join(all_defs) if all_defs else ""

    found = sum(1 for c in chunks if c["injected_context"])
    log.info("header_injector.done", chunks=len(chunks), with_context=found,
             cached_headers=len(header_cache))
    return chunks
