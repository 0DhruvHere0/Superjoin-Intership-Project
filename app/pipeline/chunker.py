from dataclasses import dataclass
from typing import Iterable, List
from app.pipeline.pdf_extractor import ExtractedPage
@dataclass
class TextChunk:
    text: str
    page_start: int
    page_end: int
def _split_long_text(
    text: str,
    max_characters: int,
) -> Iterable[str]:
    start = 0
    text_length = len(text)
    while start < text_length:
        end = min(start + max_characters, text_length)
        if end < text_length:
            whitespace_position = text.rfind(" ", start, end)
            if whitespace_position > start:
                end = whitespace_position
        piece = text[start:end].strip()
        if piece:
            yield piece
        start = end
        while start < text_length and text[start].isspace():
            start += 1
def chunk_pages(
    pages: List[ExtractedPage],
    max_characters: int = 3000,
) -> List[TextChunk]:
    if max_characters <= 0:
        raise ValueError("max_characters must be greater than zero")
    chunks: List[TextChunk] = []
    current_parts: List[str] = []
    current_length = 0
    current_page_start = None
    current_page_end = None
    def save_current_chunk() -> None:
        nonlocal current_parts
        nonlocal current_length
        nonlocal current_page_start
        nonlocal current_page_end
        if not current_parts:
            return
        chunks.append(
            TextChunk(
                text="\n\n".join(current_parts),
                page_start=current_page_start,
                page_end=current_page_end,
            )
        )
        current_parts = []
        current_length = 0
        current_page_start = None
        current_page_end = None
    for page in pages:
        page_text = page.text.strip()
        if not page_text:
            continue
        if len(page_text) > max_characters:
            save_current_chunk()
            for piece in _split_long_text(
                page_text,
                max_characters,
            ):
                chunks.append(
                    TextChunk(
                        text=piece,
                        page_start=page.page_number,
                        page_end=page.page_number,
                    )
                )
            continue
        separator_length = 2 if current_parts else 0
        would_exceed_limit = (
            current_length
            + separator_length
            + len(page_text)
            > max_characters
        )
        if current_parts and would_exceed_limit:
            save_current_chunk()
        if current_page_start is None:
            current_page_start = page.page_number
        current_page_end = page.page_number
        current_parts.append(page_text)
        current_length += separator_length + len(page_text)
    save_current_chunk()
    return chunks