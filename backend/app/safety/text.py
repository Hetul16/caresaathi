"""Text helpers shared by the quote checker and the output guard."""
import re
import unicodedata

_WS = re.compile(r"\s+")


def normalize_text(s: str) -> str:
    """Case-fold, apply NFKC and collapse whitespace so quotes survive OCR line breaks."""
    return _WS.sub(" ", unicodedata.normalize("NFKC", s)).strip().casefold()


def quote_in_text(quote: str, text: str) -> bool:
    """True when the quote appears in the text after normalization. An empty quote never matches."""
    q = normalize_text(quote)
    return bool(q) and q in normalize_text(text)
