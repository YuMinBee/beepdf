from __future__ import annotations

from v2.schemas import Chunk, PageMarkdown


def chunk_pages(pages: list[PageMarkdown], max_chars: int = 900) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        text = page.markdown.strip()
        if not text:
            continue
        parts = [text[index : index + max_chars] for index in range(0, len(text), max_chars)]
        for offset, part in enumerate(parts, start=1):
            chunks.append(
                Chunk(
                    chunk_id=f"p{page.page_number}_c{offset}",
                    page_number=page.page_number,
                    text=part,
                    metadata={"parser": page.parser},
                )
            )
    return chunks
