"""Tests for tree-sitter C chunker."""

import tempfile
from pathlib import Path

from src.chunker import chunk_file, chunk_repo, chunk_id_to_uuid, make_chunk_id, parse_functions

SAMPLE_C = b"""\
#include <stdio.h>
#include "messaging.h"

typedef struct {
    int len;
    char *data;
} msg_t;

void dispatch_message(msg_t *msg) {
    char buf[256];
    memcpy(buf, msg->data, msg->len);  // potential overflow
    process(buf);
}

int validate_length(int len) {
    if (len < 0 || len > 1024) {
        return -1;
    }
    return 0;
}

static void helper(void) {
    // internal helper
}
"""


def test_make_chunk_id_deterministic():
    id1 = make_chunk_id("teamA", "src/main.c", "dispatch_message")
    id2 = make_chunk_id("teamA", "src/main.c", "dispatch_message")
    assert id1 == id2
    assert id1.startswith("teamA__")
    assert id1.endswith("__dispatch_message")


def test_make_chunk_id_different_teams():
    id1 = make_chunk_id("teamA", "src/main.c", "foo")
    id2 = make_chunk_id("teamB", "src/main.c", "foo")
    assert id1 != id2


def test_parse_functions_extracts_all():
    functions = parse_functions(SAMPLE_C, "test.c")
    names = [f["function"] for f in functions]
    assert "dispatch_message" in names
    assert "validate_length" in names
    assert "helper" in names
    assert len(functions) == 3


def test_parse_functions_line_numbers():
    functions = parse_functions(SAMPLE_C, "test.c")
    dispatch = next(f for f in functions if f["function"] == "dispatch_message")
    assert dispatch["start_line"] >= 1
    assert dispatch["end_line"] > dispatch["start_line"]


def test_parse_functions_includes():
    functions = parse_functions(SAMPLE_C, "test.c")
    assert len(functions) > 0
    includes = functions[0]["includes"]
    assert any("stdio.h" in inc for inc in includes)
    assert any("messaging.h" in inc for inc in includes)


def test_parse_functions_code_content():
    functions = parse_functions(SAMPLE_C, "test.c")
    dispatch = next(f for f in functions if f["function"] == "dispatch_message")
    assert "memcpy" in dispatch["code"]
    assert "msg->data" in dispatch["code"]


def test_chunk_file_with_real_file():
    with tempfile.NamedTemporaryFile(suffix=".c", delete=False) as f:
        f.write(SAMPLE_C)
        f.flush()
        chunks = chunk_file(f.name, "test_team")

    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk["team"] == "test_team"
        assert chunk["chunk_key"].startswith("test_team__")
        # id is a valid UUID derived from chunk_key
        assert chunk["id"] == chunk_id_to_uuid(chunk["chunk_key"])
        assert "code" in chunk
        assert "function" in chunk


def test_chunk_file_empty():
    with tempfile.NamedTemporaryFile(suffix=".c", delete=False) as f:
        f.write(b"")
        f.flush()
        chunks = chunk_file(f.name, "test_team")
    assert chunks == []


def test_chunk_file_no_functions():
    with tempfile.NamedTemporaryFile(suffix=".c", delete=False) as f:
        f.write(b"#include <stdio.h>\ntypedef int foo;\n")
        f.flush()
        chunks = chunk_file(f.name, "test_team")
    assert chunks == []


def test_chunk_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal repo structure
        src_dir = Path(tmpdir) / "src"
        src_dir.mkdir()
        (src_dir / "main.c").write_bytes(SAMPLE_C)
        (src_dir / "empty.c").write_bytes(b"// no functions\n")

        chunks = chunk_repo(tmpdir, "test_team")
        assert len(chunks) == 3
        # File paths should be relative
        for chunk in chunks:
            print(chunk['file'])
            assert not chunk["file"].startswith("/")
