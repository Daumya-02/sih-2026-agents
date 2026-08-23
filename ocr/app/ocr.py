"""
Extracts raw text from a medical report photo.
Two engines supported — pick one in .env (OCR_ENGINE).
"""
from app.config import OCR_ENGINE
from PIL import Image
import io

_easyocr_reader = None  # lazy-loaded singleton, model load is slow


def _extract_easyocr(image_bytes: bytes) -> str:
    global _easyocr_reader
    import easyocr
    import numpy as np

    if _easyocr_reader is None:
        _easyocr_reader = easyocr.Reader(["en"], gpu=False)

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    result = _easyocr_reader.readtext(np.array(img), detail=0, paragraph=True)
    return "\n".join(result)


def _extract_tesseract(image_bytes: bytes) -> str:
    import pytesseract

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    return pytesseract.image_to_string(img)


def extract_text(image_bytes: bytes) -> str:
    if OCR_ENGINE == "tesseract":
        text = _extract_tesseract(image_bytes)
    else:
        text = _extract_easyocr(image_bytes)

    text = text.strip()
    if not text:
        raise ValueError("OCR found no readable text in this image.")
    return text
