"""How an order is named to a person.

A row id is a 32-hex uuid nobody can read out over a chat; the partner's
order is a running number they call «#67191». So a deposit is «D-1A2B3C»,
a ₽ order «P-…», a withdrawal «W-…» -- the kind, and enough of the id to
find it -- and the partner's number keeps its «#».
"""

PREFIX = {"deposit": "D", "fiat_order": "P", "withdrawal": "W"}
SHORT = 6


def human_id(kind: str, row_id: str) -> str:
    return f"{PREFIX.get(kind, 'X')}-{row_id[:SHORT].upper()}"


def partner_number(number) -> str | None:
    """«#67191», or None while the partner has not numbered the order."""
    return None if number is None else f"#{number}"


def id_prefix(identifier: str) -> str | None:
    """The hex an operator typed -- «P-1A2B3C», «p-1a2b3c» or bare «1A2B3C» --
    lowercased for a prefix match on the row id, or None if it is not that."""
    text = identifier.strip()
    if len(text) > 2 and text[1] == "-" and text[0].upper() in PREFIX.values():
        text = text[2:]
    text = text.lower()
    if len(text) < SHORT or any(char not in "0123456789abcdef" for char in text):
        return None
    return text
