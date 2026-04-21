from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import fitz
import requests
from bs4 import BeautifulSoup

from app.utils.text import clean_text, infer_title


@dataclass(slots=True)
class ParsedDocument:
    title: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)



def parse_html_text(html: str, source_url: str | None = None) -> ParsedDocument:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = infer_title(soup.title.get_text(strip=True) if soup.title else "")
    main_node = soup.find("article") or soup.find("main") or soup.body or soup
    text = clean_text(main_node.get_text("\n", strip=True))
    metadata: dict[str, str] = {}
    if source_url:
        parsed = urlparse(source_url)
        metadata["source_site"] = parsed.netloc

    return ParsedDocument(title=title, text=text, metadata=metadata)



def parse_pdf_bytes(pdf_bytes: bytes) -> ParsedDocument:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        texts = [page.get_text("text") for page in document]
    joined = clean_text("\n".join(texts))
    title = infer_title(joined, fallback="PDF文档")
    return ParsedDocument(
        title=title,
        text=joined,
        metadata={"parser": "pymupdf", "unstructured_hint": "如遇复杂 PDF，可扩展 unstructured/OCR 流程"},
    )



def fetch_remote_content(url: str, timeout: int, user_agent: str) -> tuple[bytes, str]:
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": user_agent},
    )
    response.raise_for_status()
    return response.content, response.headers.get("content-type", "")



def parse_local_file(path: str | Path) -> ParsedDocument:
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in {".md", ".markdown", ".txt"}:
        text = clean_text(file_path.read_text(encoding="utf-8"))
        return ParsedDocument(title=infer_title(text, file_path.stem), text=text)
    if suffix in {".html", ".htm"}:
        html = file_path.read_text(encoding="utf-8")
        return parse_html_text(html)
    if suffix == ".pdf":
        return parse_pdf_bytes(file_path.read_bytes())

    raise ValueError(f"暂不支持的文件类型: {suffix}")



def parse_remote_file(url: str, timeout: int, user_agent: str) -> ParsedDocument:
    content, content_type = fetch_remote_content(url, timeout=timeout, user_agent=user_agent)
    lowered = content_type.lower()

    if url.lower().endswith(".pdf") or "application/pdf" in lowered:
        parsed = parse_pdf_bytes(content)
    elif "text/html" in lowered or url.lower().endswith((".html", ".htm")):
        parsed = parse_html_text(content.decode("utf-8", errors="ignore"), source_url=url)
    elif "text/plain" in lowered or url.lower().endswith((".txt", ".md", ".markdown")):
        text = clean_text(content.decode("utf-8", errors="ignore"))
        parsed = ParsedDocument(title=infer_title(text, url), text=text)
    else:
        raise ValueError(f"无法识别远程文件类型: {content_type}")

    parsed.metadata["remote_url"] = url
    return parsed
