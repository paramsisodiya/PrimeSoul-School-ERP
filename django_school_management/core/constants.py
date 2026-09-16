"""
PrimeSoul Core - System Constants & Indian K-12 Regional Defaults
"""

DEFAULT_CURRENCY = 'INR'
DEFAULT_CURRENCY_SYMBOL = '₹'
DEFAULT_TIME_ZONE = 'Asia/Kolkata'

# Standard Indian Board Affiliations
BOARD_CBSE = 'CBSE'
BOARD_ICSE = 'ICSE'
BOARD_STATE = 'STATE'
BOARD_IB = 'IB'
BOARD_CAMBRIDGE = 'CAMBRIDGE'

BOARD_CHOICES = (
    (BOARD_CBSE, 'Central Board of Secondary Education (CBSE)'),
    (BOARD_ICSE, 'Council for the Indian School Certificate Examinations (ICSE/ISC)'),
    (BOARD_STATE, 'State Board of Education'),
    (BOARD_IB, 'International Baccalaureate (IB)'),
    (BOARD_CAMBRIDGE, 'Cambridge Assessment International Education (CIE)'),
)

# Standard Indian Fiscal & Academic Session defaults
SESSION_START_MONTH = 4   # April
SESSION_END_MONTH = 3     # March
