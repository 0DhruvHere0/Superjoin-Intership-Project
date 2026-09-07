from dataclasses import dataclass
from pathlib import Path
from typing import List, Union
import fitz
@dataclass
class ExtractedPage:
    page_number: int
    text: str
class PDFExtractionError(Exception):
    pass
def extract_pdf_text(
    pdf_path: Union[str, Path],
) -> List[ExtractedPage]:
    path = Path(pdf_path)
    if not path.exists():
        raise PDFExtractionError(
            f"PDF file does not exist: {path}"
        )
    if not path.is_file():
        raise PDFExtractionError(
            f"Path is not a file: {path}"
        )
    try:
        document = fitz.open(str(path))
    except Exception as error:
        raise PDFExtractionError(
            f"Could not open PDF: {error}"
        ) from error
    extracted_pages: List[ExtractedPage] = []
    try:
        if document.page_count == 0:
            raise PDFExtractionError(
                "The PDF does not contain any pages."
            )
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            page_text = page.get_text("text")

            extracted_pages.append(
                ExtractedPage(
                    page_number=page_index + 1,
                    text=page_text.strip(),
                )
            )
    finally:
        document.close()
    has_extractable_text = any(
        page.text for page in extracted_pages
    )
    if not has_extractable_text:
        raise PDFExtractionError(
            "The PDF contains no extractable text. "
            "It may be a scanned or image-only PDF."
        )
    return extracted_pages