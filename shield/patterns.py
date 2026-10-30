import re

# A link ends before the sentence's own punctuation: "see https://x.com/a." keeps the full stop.
URL = re.compile(r"https?://[^\s<>\"')\]]*[^\s<>\"')\].,;:!?]")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# (?<![\w\[]) so a stand-in like [Phone 2] is never read as a phone number again
PHONE = re.compile(r"(?<![\w\[])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")

REMOVED = "[removed]"

# These never get a stand-in. There's no reason a model needs to tell two SSNs apart,
# and a stand-in would mean keeping the real number in the lookup table.
REMOVE = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), REMOVED),                       # SSN
    (re.compile(r"\b(?:\d{4}[\s-]){3}\d{1,4}\b"), REMOVED),                # card number
    (re.compile(r"\b((?:routing|account|acct)\s*(?:number|no\.?|#)?\s*:?\s*)\d[\d-]{5,}", re.I),
     r"\1" + REMOVED),                                                      # "account # 12345678"
]

# Words that make a business name longer without making it more specific.
# "Delta Air Lines" is also just "Delta".
GENERIC = {"air", "lines", "airlines", "airline", "inc", "llc", "ltd", "co", "corp", "corporation", "company",
           "dental", "clinic", "group", "bank", "store", "stores", "services", "service", "the"}


def loose(value):
    """A pattern for one of your own numbers that ignores how it's punctuated.
    123-45-6789, 123 45 6789 and 123456789 are the same number."""
    digits = re.sub(r"[\s\-./]", "", value)
    if len(digits) < 4:  # too short to find without hitting everything else
        return None
    return re.compile(r"(?<![\w])" + r"[\s\-./]?".join(re.escape(c) for c in digits) + r"(?![\w])", re.I)
