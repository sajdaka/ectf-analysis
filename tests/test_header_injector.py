"""Tests for header injector — include resolution and definition extraction."""

import tempfile
from pathlib import Path

from src.header_injector import (
    extract_definitions,
    find_header,
    inject_headers,
    parse_include_names,
)

SAMPLE_HEADER = b"""\
#ifndef MESSAGING_H
#define MESSAGING_H

#include <stdint.h>

#define MAX_MSG_LEN 256
#define MSG_TYPE_CMD 0x01

typedef struct {
    uint8_t type;
    uint16_t len;
    uint8_t *data;
} msg_t;

typedef enum {
    STATE_IDLE,
    STATE_ACTIVE,
    STATE_ERROR,
} device_state_t;

struct config {
    int baud_rate;
    int timeout;
};

void dispatch_message(msg_t *msg);
int validate_length(int len);

#endif
"""

SAMPLE_EMPTY_HEADER = b"""\
#ifndef EMPTY_H
#define EMPTY_H
#endif
"""


def _make_repo(tmpdir, headers: dict[str, bytes] = None, sources: dict[str, bytes] = None):
    """Create a minimal repo structure with given headers and sources."""
    repo = Path(tmpdir)
    if headers:
        inc_dir = repo / "include"
        inc_dir.mkdir(exist_ok=True)
        for name, content in headers.items():
            (inc_dir / name).write_bytes(content)
    if sources:
        src_dir = repo / "src"
        src_dir.mkdir(exist_ok=True)
        for name, content in sources.items():
            (src_dir / name).write_bytes(content)
    return repo


# ── parse_include_names ──────────────────────────────────────────────────

def test_parse_include_names_quoted():
    includes = ['#include "messaging.h"', '#include "config.h"']
    names = parse_include_names(includes)
    assert names == ["messaging.h", "config.h"]


def test_parse_include_names_angle_brackets():
    includes = ['#include <stdint.h>', '#include <messaging.h>']
    names = parse_include_names(includes)
    assert names == ["stdint.h", "messaging.h"]


def test_parse_include_names_mixed():
    includes = ['#include "local.h"', '#include <system.h>']
    names = parse_include_names(includes)
    assert len(names) == 2


# ── find_header ──────────────────────────────────────────────────────────

def test_find_header_exists():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _make_repo(tmpdir, headers={"messaging.h": SAMPLE_HEADER})
        result = find_header("messaging.h", repo)
        assert result is not None
        assert result.name == "messaging.h"


def test_find_header_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _make_repo(tmpdir, headers={"other.h": b"// nope"})
        result = find_header("messaging.h", repo)
        assert result is None


def test_find_header_nested():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        deep = repo / "lib" / "drivers" / "inc"
        deep.mkdir(parents=True)
        (deep / "uart.h").write_bytes(b"typedef int uart_cfg;")
        result = find_header("uart.h", repo)
        assert result is not None
        assert result.name == "uart.h"


# ── extract_definitions ─────────────────────────────────────────────────

def test_extract_definitions_typedef_struct():
    with tempfile.NamedTemporaryFile(suffix=".h", delete=False) as f:
        f.write(SAMPLE_HEADER)
        f.flush()
        defs = extract_definitions(Path(f.name))

    texts = "\n".join(defs)
    assert "msg_t" in texts
    assert "device_state_t" in texts
    assert "MAX_MSG_LEN" in texts
    assert "MSG_TYPE_CMD" in texts


def test_extract_definitions_struct_with_body():
    with tempfile.NamedTemporaryFile(suffix=".h", delete=False) as f:
        f.write(SAMPLE_HEADER)
        f.flush()
        defs = extract_definitions(Path(f.name))

    # "struct config" has a body, should be extracted
    texts = "\n".join(defs)
    assert "baud_rate" in texts


def test_extract_definitions_empty_header():
    with tempfile.NamedTemporaryFile(suffix=".h", delete=False) as f:
        f.write(SAMPLE_EMPTY_HEADER)
        f.flush()
        defs = extract_definitions(Path(f.name))

    # only #define guards, no real definitions
    # the EMPTY_H define will be extracted but that's fine
    assert isinstance(defs, list)


def test_extract_definitions_skips_prototypes():
    """Function prototypes should NOT be extracted."""
    with tempfile.NamedTemporaryFile(suffix=".h", delete=False) as f:
        f.write(SAMPLE_HEADER)
        f.flush()
        defs = extract_definitions(Path(f.name))

    texts = "\n".join(defs)
    # prototypes like "void dispatch_message(msg_t *msg);" are declarations
    # but not in our extractable set, so they shouldn't appear
    assert "void dispatch_message" not in texts


# ── inject_headers (integration) ─────────────────────────────────────────

def test_inject_headers_adds_context():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _make_repo(tmpdir, headers={"messaging.h": SAMPLE_HEADER})

        chunks = [
            {
                "function": "dispatch_message",
                "code": "void dispatch_message(msg_t *msg) { ... }",
                "includes": ['#include "messaging.h"'],
            }
        ]

        inject_headers(chunks, str(repo))

        assert "injected_context" in chunks[0]
        ctx = chunks[0]["injected_context"]
        assert "msg_t" in ctx
        assert "MAX_MSG_LEN" in ctx


def test_inject_headers_skips_system_headers():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _make_repo(tmpdir)

        chunks = [
            {
                "function": "main",
                "code": "int main() {}",
                "includes": ['#include <stdio.h>', '#include <stdlib.h>'],
            }
        ]

        inject_headers(chunks, str(repo))

        # should have empty injected_context — system headers are skipped
        assert chunks[0]["injected_context"] == ""


def test_inject_headers_missing_header_graceful():
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _make_repo(tmpdir)  # no headers at all

        chunks = [
            {
                "function": "foo",
                "code": "void foo() {}",
                "includes": ['#include "nonexistent.h"'],
            }
        ]

        # should not raise
        inject_headers(chunks, str(repo))
        assert chunks[0]["injected_context"] == ""


def test_inject_headers_caches():
    """Multiple chunks including the same header should only parse it once."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = _make_repo(tmpdir, headers={"messaging.h": SAMPLE_HEADER})

        chunks = [
            {
                "function": "fn1",
                "code": "void fn1() {}",
                "includes": ['#include "messaging.h"'],
            },
            {
                "function": "fn2",
                "code": "void fn2() {}",
                "includes": ['#include "messaging.h"'],
            },
        ]

        inject_headers(chunks, str(repo))

        # both should have the same injected context
        assert chunks[0]["injected_context"] == chunks[1]["injected_context"]
        assert "msg_t" in chunks[0]["injected_context"]
