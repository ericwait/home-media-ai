"""
Utility functions for HomeMedia.
"""

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def parse_date_from_filename(filename: str) -> Optional[datetime]:
    """
    Attempt to parse a date from a filename using common patterns.

    Supported patterns:
    - YYYYMMDD_HHMMSS (e.g., IMG_20250101_123045.jpg)
    - YYYY-MM-DD_HH-MM-SS (e.g., 2025-01-01_12-30-45.jpg)
    - YYYY-MM-DD (e.g., Screenshot_2025-01-01.png)
    - YYYYMMDD (e.g., IMG-20250101-WA0001.jpg)

    Args:
        filename: The filename to parse

    Returns:
        datetime object if a pattern matches, else None
    """
    # 1. YYYYMMDD_HHMMSS (standard Android/Pixel)
    # Match: 20250101_123045
    match = re.search(r"(\d{8})_(\d{6})", filename)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S")
        except ValueError:
            pass

    # 2. YYYY-MM-DD_HH-MM-SS (our own canonical format)
    # Match: 2025-01-01_12-30-45
    match = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})", filename)
    if match:
        try:
            date_str = match.group(1)
            time_str = match.group(2).replace("-", "")
            return datetime.strptime(f"{date_str}{time_str}", "%Y-%m-%d%H%M%S")
        except ValueError:
            pass
            
    # 3. YYYY-MM-DD HH.MM.SS (some downloads)
    match = re.search(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}\.\d{2}\.\d{2})", filename)
    if match:
        try:
            date_str = match.group(1)
            time_str = match.group(2).replace(".", ":")
            return datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    # 4. YYYYMMDD-HHMMSS (Screenshots)
    # Match: Screenshot_20251214-082305
    match = re.search(r"(\d{8})-(\d{6})", filename)
    if match:
        try:
            return datetime.strptime(f"{match.group(1)}{match.group(2)}", "%Y%m%d%H%M%S")
        except ValueError:
            pass

    # 5. YYYYMMDD (WhatsApp, generic) - usually followed by - or _ or end
    # Match: 20250101 within IMG-20250101-WA...
    # We look for 201x-202x to avoid matching random numbers
    match = re.search(r"(20[1-2]\d{5})", filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d")
        except ValueError:
            pass

    # 5. YYYY-MM-DD (Screenshots)
    match = re.search(r"(20[1-2]\d-\d{2}-\d{2})", filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d")
        except ValueError:
            pass

    return None
