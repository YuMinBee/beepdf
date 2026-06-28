from __future__ import annotations

from v2.schemas import Chunk, PageMarkdown


def chunk_pages(
    pages: list[PageMarkdown],
    max_chars: int = 900,
    filename: str | None = None,
    doc_id: str | None = None,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        text = page.markdown
        if not text.strip():
            continue

        chunk_index = 1
        for start in range(0, len(text), max_chars):
            raw_part = text[start : start + max_chars]
            if not raw_part.strip():
                continue
            end = start + len(raw_part)
            metadata = {"parser": page.parser}
            if doc_id:
                metadata["doc_id"] = doc_id
            if filename:
                metadata["filename"] = filename
            chunks.append(
                Chunk(
                    chunk_id=f"p{page.page_number}_c{chunk_index}",
                    page=page.page_number,
                    text=raw_part.strip(),
                    char_start=start,
                    char_end=end,
                    metadata=metadata,
                )
            )
            chunk_index += 1
    return chunks
