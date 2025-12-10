from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

try:
    import pytesseract  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pytesseract = None  # type: ignore

try:
    from PIL import Image  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    Image = None  # type: ignore

try:
    import cv2  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    cv2 = None  # type: ignore

try:
    import numpy as np  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    np = None  # type: ignore

logger = logging.getLogger(__name__)

if pytesseract is None or Image is None:
    logger.warning("OCR optional dependencies missing; falling back to mocked OCR output.")

# Regex helpers shared across field extractors
_DATE_PATTERNS = [
    r"\d{2}[/-]\d{2}[/-]\d{4}",
    r"\d{4}[/-]\d{2}[/-]\d{2}",
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}",
]
_DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%Y-%m-%d",
    "%d %b %Y",
    "%d %B %Y",
]


def process_receipt_with_ocr(image_file) -> Dict[str, Any]:
    """
    Extract structured receipt data using pytesseract (if available).
    Returns vendor, date, total, tax amount, line items (best-effort) and raw text.
    """
    text = ""
    confidence = None
    engine = "mock"

    if pytesseract and Image:
        try:
            text, confidence = _run_tesseract(image_file)
            engine = "tesseract"
        except Exception:  # noqa: BLE001
            logger.exception("receipt_ocr.failed_pytesseract")

    if not text:
        logger.info("receipt_ocr.mock_response")
        return _mock_response()

    parsed = _parse_receipt_text(text)
    parsed["raw_text"] = text.strip()
    parsed["confidence"] = confidence
    parsed["engine"] = engine
    return parsed


def _run_tesseract(image_file) -> Tuple[str, Optional[float]]:
    """Run pytesseract with light pre-processing."""
    with Image.open(image_file) as img:
        prepared = _preprocess_image(img)
        text = pytesseract.image_to_string(prepared, config="--psm 6")
        confidence = _compute_confidence(prepared)
    return text, confidence


def _preprocess_image(img):
    """Improve OCR quality using grayscale + threshold when OpenCV is available."""
    if not cv2 or not np:
        return img

    array = np.array(img)
    if len(array.shape) == 2:  # Already grayscale
        gray = array
    else:
        gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
    # Light denoise + adaptive threshold to boost contrast
    denoised = cv2.bilateralFilter(gray, 9, 75, 75)
    _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return Image.fromarray(thresh)


def _compute_confidence(img) -> Optional[float]:
    """Average pytesseract confidence score, ignoring -1 placeholders."""
    try:
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confs = [
            float(conf)
            for conf in data.get("conf", [])
            if conf not in ("-1", -1, "-1.0")
        ]
        return round(sum(confs) / len(confs), 2) if confs else None
    except Exception:  # noqa: BLE001
        logger.debug("receipt_ocr.confidence_failed", exc_info=True)
        return None


def _parse_receipt_text(text: str) -> Dict[str, Any]:
    """Parse key fields from OCR text output."""
    cleaned = text.replace("\r", "\n")
    vendor = _extract_vendor(cleaned)
    date = _extract_date(cleaned)
    total = _extract_amount(cleaned)
    tax_amount = _extract_tax(cleaned)
    line_items = _extract_line_items(cleaned)

    return {
        "vendor": vendor,
        "date": date,
        "total": _decimal_to_str(total),
        "tax_amount": _decimal_to_str(tax_amount),
        "line_items": [
            {"description": item["description"], "amount": _decimal_to_str(item["amount"])}
            for item in line_items
        ],
    }


def _mock_response() -> Dict[str, Any]:
    """Fallback response when OCR dependencies are missing."""
    return {
        "vendor": "Mock Supermarket",
        "date": "2023-10-27",
        "total": "125.50",
        "tax_amount": "15.50",
        "line_items": [
            {"description": "Milk", "amount": "3.50"},
            {"description": "Bread", "amount": "2.00"},
            {"description": "Eggs", "amount": "4.00"},
        ],
        "raw_text": "",
        "confidence": None,
        "engine": "mock",
    }


def _extract_date(text: str) -> Optional[str]:
    """Extract date from receipt text using regex patterns."""
    for pattern in _DATE_PATTERNS:
        for match in re.findall(pattern, text):
            normalized = match.replace("-", "/")
            for fmt in _DATE_FORMATS:
                try:
                    parsed = datetime.strptime(normalized, fmt)
                    return parsed.strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return None


def _extract_amount(text: str) -> Optional[Decimal]:
    """Extract total amount from receipt text."""
    amounts: List[Decimal] = []
    for line in text.splitlines():
        if re.search(r"(total|amount due|grand total|balance)", line, re.IGNORECASE):
            amounts.extend(_find_amounts(line))
    if amounts:
        return max(amounts)

    # Fallback: pick the largest currency-like number found in the document
    for line in text.splitlines():
        amounts.extend(_find_amounts(line))
    return max(amounts) if amounts else None


def _extract_vendor(text: str) -> Optional[str]:
    """Extract vendor name from receipt text (first non-numeric header line)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    header_candidates = lines[:5]
    for line in header_candidates:
        if not re.search(r"\d+[.,]\d{2}", line) and not re.search(r"\d{2}[/-]\d{2}[/-]\d{2,4}", line):
            return line[:120]
    return None


def _extract_tax(text: str) -> Optional[Decimal]:
    """Extract tax amount from receipt text."""
    tax_patterns = [
        r"(TAX|VAT|GST)[^\d]*(-?\d+[.,]\d{2})",
    ]
    for pattern in tax_patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            amount = _safe_decimal(match[1])
            if amount is not None:
                return amount
    return None


def _extract_line_items(text: str) -> List[Dict[str, Any]]:
    """Extract individual line items from receipt text."""
    items: List[Dict[str, Any]] = []
    for line in text.splitlines():
        match = re.search(r"(.+?)\s+[\$ƒ,ªAœ]?\s*(\d+[.,]\d{2})\s*$", line)
        if match:
            amount = _safe_decimal(match.group(2))
            if amount is not None:
                items.append({
                    "description": match.group(1).strip()[:120],
                    "amount": amount,
                })
    return items


def _find_amounts(line: str) -> List[Decimal]:
    """Return all currency-like numbers from a line of text."""
    matches = re.findall(r"(-?\d+[.,]\d{2})", line)
    amounts: List[Decimal] = []
    for match in matches:
        amount = _safe_decimal(match)
        if amount is not None:
            amounts.append(amount)
    return amounts


def _safe_decimal(value) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        cleaned = value.replace(",", ".")
        return Decimal(cleaned)
    except (InvalidOperation, AttributeError):
        return None


def _decimal_to_str(value: Optional[Decimal]) -> Optional[str]:
    return f"{value:.2f}" if value is not None else None
