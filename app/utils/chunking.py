from __future__ import annotations

import re
from dataclasses import dataclass

from app.utils.text import extract_keywords, simple_token_count


HEADING_PATTERN = re.compile(
    r"^(#{1,6}\s+.+|第[一二三四五六七八九十百千0-9]+[章节条款].+|[一二三四五六七八九十]+、.+|[0-9]{1,2}[.、].+)$"
)


@dataclass(slots=True)
class TextChunk:
    chunk_index: int
    section_path: str
    content: str
    token_count: int
    keywords: list[str]



def split_into_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_heading = "正文"
    buffer: list[str] = []

    def flush() -> None:
        content = "\n".join(buffer).strip()
        if content:
            sections.append((current_heading, content))
        buffer.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if buffer and buffer[-1] != "":
                buffer.append("")
            continue
        if HEADING_PATTERN.match(line):
            flush()
            current_heading = line.lstrip("#").strip()
            continue
        buffer.append(line)

    flush()
    return sections or [("正文", text)]



def chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    chunk_index = 0

    for section_path, section_text in split_into_sections(text):
        normalized = re.sub(r"\n{2,}", "\n", section_text).strip()
        if not normalized:
            continue

        start = 0
        while start < len(normalized):
            end = min(len(normalized), start + chunk_size)
            snippet = normalized[start:end].strip()
            if snippet:
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_index,
                        section_path=section_path,
                        content=snippet,
                        token_count=simple_token_count(snippet),
                        keywords=extract_keywords(snippet),
                    )
                )
                chunk_index += 1
            if end >= len(normalized):
                break
            start = max(0, end - overlap)

    return chunks
