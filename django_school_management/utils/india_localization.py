"""
PrimeSoul School ERP - India Localization & Standards Layer
Defines statutory identifiers, regional defaults, currency helpers, and validation rules for Indian K-12 education.
"""

import re
from decimal import Decimal

# Regional & Statutory Constants
COUNTRY_NAME = "India"
COUNTRY_CODE = "IN"
DEFAULT_TIMEZONE = "Asia/Kolkata"
CURRENCY_CODE = "INR"
CURRENCY_SYMBOL = "₹"

# Academic Year Cycle for Indian Schools (CBSE / ICSE / State Boards typically run April to March)
ACADEMIC_YEAR_START_MONTH = 4  # April
ACADEMIC_YEAR_END_MONTH = 3    # March
ACADEMIC_YEAR_CYCLE_NAME = "April to March"

# Indian Education Boards
INDIAN_SCHOOL_BOARDS = (
    ('CBSE', 'Central Board of Secondary Education (CBSE)'),
    ('ICSE', 'Council for the Indian School Certificate Examinations (ICSE/ISC)'),
    ('STATE', 'State Board of Secondary Education'),
    ('IB', 'International Baccalaureate (IB)'),
    ('CAMBRIDGE', 'Cambridge Assessment International Education (IGCSE)'),
    ('OTHER', 'Other / Independent Board'),
)

# Standard K-12 Grades in India
INDIAN_GRADE_LEVELS = [
    (1, "Class 1"),
    (2, "Class 2"),
    (3, "Class 3"),
    (4, "Class 4"),
    (5, "Class 5"),
    (6, "Class 6"),
    (7, "Class 7"),
    (8, "Class 8"),
    (9, "Class 9"),
    (10, "Class 10"),
    (11, "Class 11"),
    (12, "Class 12"),
]

# Higher Secondary Streams (Classes 11 & 12)
INDIAN_ACADEMIC_STREAMS = (
    ('SCIENCE_PCM', 'Science (PCM - Physics, Chemistry, Mathematics)'),
    ('SCIENCE_PCB', 'Science (PCB - Physics, Chemistry, Biology)'),
    ('COMMERCE', 'Commerce (with / without Mathematics)'),
    ('HUMANITIES', 'Humanities / Arts'),
)

# Phone Regex: 10-digit Indian mobile number starting with 6, 7, 8, or 9
# Optionally prefixed with +91, 91, or 0, with optional spaces/hyphens
INDIAN_MOBILE_REGEX = re.compile(r'^(?:\+91[\-\s]?|91[\-\s]?|0)?[6-9]\d{9}$')

# Aadhaar Regex: 12-digit Indian National Identity Number (optional spaces every 4 digits)
AADHAAR_REGEX = re.compile(r'^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$')


def is_valid_indian_mobile(phone_str: str) -> bool:
    """Validates whether a string matches standard Indian 10-digit mobile phone format."""
    if not phone_str:
        return False
    clean = phone_str.strip()
    return bool(INDIAN_MOBILE_REGEX.match(clean))


def clean_indian_mobile(phone_str: str) -> str:
    """Normalizes an Indian phone number to 10 standard digits."""
    if not phone_str:
        return ""
    digits = re.sub(r'\D', '', phone_str)
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    return digits


def format_inr(amount: Decimal | float | int | str) -> str:
    """
    Formats a numeric amount into Indian numbering system (Lakhs & Crores):
    e.g. 10000 -> ₹10,000.00
         150000 -> ₹1,50,000.00
    """
    try:
        dec_amount = Decimal(str(amount))
    except Exception:
        return f"{CURRENCY_SYMBOL}0.00"

    sign = "-" if dec_amount < 0 else ""
    abs_dec = abs(dec_amount)
    parts = f"{abs_dec:.2f}".split(".")
    integer_part = parts[0]
    decimal_part = parts[1]

    if len(integer_part) <= 3:
        formatted_int = integer_part
    else:
        last3 = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_int = ",".join(groups) + "," + last3

    return f"{sign}{CURRENCY_SYMBOL}{formatted_int}.{decimal_part}"
