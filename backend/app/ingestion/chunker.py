"""Heading-aware recursive splitter.

Sections break on Markdown headings (`#` through `######`). Inside a section
the splitter prefers blank lines, then lines, then sentences, then words, and
finally fixed token windows. Consecutive pieces of the same section overlap by
`OVERLAP_TOKENS`. Overlap does not cross a heading. The same text always
produces the same chunks.

A token is a whitespace-separated word. That count is deterministic and does
not call a model tokenizer.
"""

import hashlib
import re
from dataclasses import dataclass

TARGET_TOKENS = 600
OVERLAP_TOKENS = 80

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)\s*$")
_TOKEN = re.compile(r"\S+")
_SEPARATORS = ("\n\n", "\n", ". ", " ")


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    heading_path: str | None
    token_count: int
    content_hash: str


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def tokenize(value: str) -> list[str]:
    return _TOKEN.findall(value)


def count_tokens(value: str) -> int:
    return len(tokenize(value))


def chunk_text(value: str, *, target: int = TARGET_TOKENS, overlap: int = OVERLAP_TOKENS) -> list[TextChunk]:
    """Split `value` into ordered chunks. Empty input returns an empty list."""
    pieces: list[tuple[str | None, str]] = []
    for path, section in _sections(value):
        parts = _with_overlap(_split_recursive(section, target), overlap)
        for part in parts:
            cleaned = part.strip()
            if cleaned:
                pieces.append((path, cleaned))
    return [
        TextChunk(
            chunk_index=index,
            text=body,
            heading_path=path,
            token_count=count_tokens(body),
            content_hash=text_hash(body),
        )
        for index, (path, body) in enumerate(pieces)
    ]


def _sections(value: str) -> list[tuple[str | None, str]]:
    stack: list[tuple[int, str]] = []
    path: str | None = None
    lines: list[str] = []
    sections: list[tuple[str | None, str]] = []

    def flush() -> None:
        body = "".join(lines).strip()
        if body:
            sections.append((path, body))

    for line in value.splitlines(keepends=True):
        match = _HEADING.match(line.rstrip("\r\n"))
        if match is None:
            lines.append(line)
            continue
        flush()
        lines = []
        level = len(match.group(1))
        title = match.group(2).strip()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        path = " / ".join(item for _, item in stack)
        lines.append(line if line.endswith("\n") else f"{line}\n")
    flush()
    return sections


def _split_recursive(value: str, target: int) -> list[str]:
    cleaned = value.strip()
    if not cleaned:
        return []
    if count_tokens(cleaned) <= target:
        return [cleaned]
    for separator in _SEPARATORS:
        parts = [part.strip() for part in cleaned.split(separator) if part.strip()]
        if len(parts) <= 1:
            continue
        packed = _pack(parts, separator, target)
        if len(packed) == 1 and count_tokens(packed[0]) > target:
            continue
        pieces: list[str] = []
        for piece in packed:
            if count_tokens(piece) > target:
                pieces.extend(_split_recursive(piece, target))
            elif piece.strip():
                pieces.append(piece.strip())
        if pieces:
            return pieces
    return _token_windows(cleaned, target)


def _pack(parts: list[str], separator: str, target: int) -> list[str]:
    packed: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for part in parts:
        part_tokens = count_tokens(part)
        overflows = bool(current) and current_tokens + part_tokens > target
        if overflows:
            packed.append(separator.join(current))
            current = []
            current_tokens = 0
        if part_tokens > target and not current:
            packed.append(part)
            continue
        current.append(part)
        current_tokens += part_tokens
    if current:
        packed.append(separator.join(current))
    return packed


def _token_windows(value: str, target: int) -> list[str]:
    tokens = tokenize(value)
    if not tokens:
        return []
    size = max(1, target)
    windows: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(len(tokens), start + size)
        windows.append(" ".join(tokens[start:end]))
        if end >= len(tokens):
            break
        start = end
    return windows


def _with_overlap(pieces: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(pieces) < 2:
        return pieces
    output = [pieces[0]]
    for piece in pieces[1:]:
        previous = tokenize(output[-1])
        width = min(overlap, len(previous))
        tail = previous[-width:]
        incoming = tokenize(piece)
        if incoming[:width] == tail:
            output.append(piece)
        else:
            output.append(" ".join([*tail, *incoming]))
    return output
