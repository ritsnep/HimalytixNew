from typing import Dict, Any
import pytesseract
from PIL import Image
import cv2
import numpy as np
from decimal import Decimal
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def process_receipt_with_ocr(image_file):
    """
    Mocks an OCR service that processes a receipt image and returns structured data.
    In a real implementation, this function would call an external OCR API.
    """
    logger.info("Processing receipt with OCR (mocked)")
    # Mocked response
    return {
        'vendor': 'Mock Supermarket',
        'date': '2023-10-27',
        'total': '125.50',
        'line_items': [
            {'description': 'Milk', 'amount': '3.50'},
            {'description': 'Bread', 'amount': '2.00'},
            {'description': 'Eggs', 'amount': '4.00'},
        ]
    }


def _extract_date(text: str) -> str:
    """Extract date from receipt text using regex patterns."""
    date_patterns = [
        r'\d{2}/\d{2}/\d{4}',
        r'\d{2}-\d{2}-\d{4}',
        r'\d{4}/\d{2}/\d{2}'
    ]

    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                date_str = match.group(0)
                return datetime.strptime(date_str, '%Y/%m/%d').strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None


def _extract_amount(text: str) -> Decimal:
    """Extract total amount from receipt text."""
    amount_patterns = [
        r'TOTAL\s*[\$€£]?\s*(\d+[.,]\d{2})',
        r'Amount\s*[\$€£]?\s*(\d+[.,]\d{2})'
    ]

    for pattern in amount_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return Decimal(match.group(1).replace(',', '.'))
            except:
                continue
    return None


def _extract_vendor(text: str) -> str:
    """Extract vendor name from receipt text."""
    # Simple heuristic: take first line that's not a date or amount
    lines = text.split('\n')
    for line in lines:
        line = line.strip()
        if line and not re.search(r'\d{2}/\d{2}/\d{4}', line) and not re.search(r'\d+[.,]\d{2}', line):
            return line
    return None


def _extract_tax(text: str) -> Decimal:
    """Extract tax amount from receipt text."""
    tax_patterns = [
        r'TAX\s*[\$€£]?\s*(\d+[.,]\d{2})',
        r'VAT\s*[\$€£]?\s*(\d+[.,]\d{2})'
    ]

    for pattern in tax_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return Decimal(match.group(1).replace(',', '.'))
            except:
                continue
    return None


def _extract_line_items(text: str) -> list:
    """Extract individual line items from receipt text."""
    lines = text.split('\n')
    items = []

    for line in lines:
        # Look for lines with amount at the end
        match = re.search(r'(.+?)\s+[\$€£]?\s*(\d+[.,]\d{2})\s*$', line)
        if match:
            items.append({
                'description': match.group(1).strip(),
                'amount': Decimal(match.group(2).replace(',', '.'))
            })

    return items