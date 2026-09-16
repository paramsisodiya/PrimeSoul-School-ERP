"""
Education boards library: country-based boards for admission forms.

Bangladesh (BD) boards are used for both polytechnic and school/madrasah admission.
Other countries can add boards via the database (EducationBoard model) or keep
free-text board field for backward compatibility.
"""

# Country ISO 3166-1 alpha-2
COUNTRY_IN = 'IN'
COUNTRY_BD = 'BD'

# India education boards (for CBSE, ICSE, State Boards)
IN_BOARDS = [
    ('Central Board of Secondary Education (CBSE)', 'CBSE'),
    ('Council for the Indian School Certificate Examinations (ICSE/ISC)', 'ICSE'),
    ('State Board of Secondary Education', 'STATE'),
    ('International Baccalaureate (IB)', 'IB'),
    ('Cambridge Assessment International Education (IGCSE)', 'CAMBRIDGE'),
]

# India streams choices for Senior Secondary (Classes 11 & 12)
IN_GROUP_SCIENCE = 'Science'
IN_GROUP_COMMERCE = 'Commerce'
IN_GROUP_HUMANITIES = 'Humanities'

IN_GROUPS = [
    (IN_GROUP_SCIENCE, IN_GROUP_SCIENCE),
    (IN_GROUP_COMMERCE, IN_GROUP_COMMERCE),
    (IN_GROUP_HUMANITIES, 'Humanities / Arts'),
]

# Bangladesh education boards (legacy compatibility)
# Order matches common usage; code can be used for display or reporting.
BD_BOARDS = [
    ('Dhaka Board (BISE, Dhaka)', 'Dhaka'),
    ('Rajshahi Board', 'Rajshahi'),
    ('Cumilla Board', 'Cumilla'),
    ('Jessore Board', 'Jessore'),
    ('Chittagong Board', 'Chittagong'),
    ('Barisal Board', 'Barisal'),
    ('Sylhet Board', 'Sylhet'),
    ('Dinajpur Board', 'Dinajpur'),
    ('Mymensingh Board', 'Mymensingh'),
    ('Bangladesh Madrasah Education Board', 'Madrasah'),
]

# BD group choices for polytechnic (SSC/HSC style)
BD_GROUP_SCIENCE = 'Science'
BD_GROUP_ARTS = 'Arts'
BD_GROUP_COMMERCE = 'Commerce'

BD_GROUPS = [
    (BD_GROUP_SCIENCE, BD_GROUP_SCIENCE),
    (BD_GROUP_ARTS, BD_GROUP_ARTS),
    (BD_GROUP_COMMERCE, BD_GROUP_COMMERCE),
]

# Class levels for Indian K-12 school (Classes 1-12)
APPLYING_FOR_CLASS_MIN = 1
APPLYING_FOR_CLASS_MAX = 12
APPLYING_FOR_CLASS_JSC_START = 9  # Legacy BD exam section shown for 9-10 only

