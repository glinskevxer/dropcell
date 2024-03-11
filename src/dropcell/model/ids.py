"""Identifier rules for the codes that appear on drawings and in the field.

Line codes, segment codes, test post numbers and rectifier tags are written on
posts, painted on cabinets and typed into a logger by someone standing in a
field. They come back with stray whitespace, mixed case and the occasional
smart dash. Normalising them once here is the difference between one test post
and three that look alike.
"""

from __future__ import annotations

import re
from typing import Final

from dropcell.errors import ValidationError

_CODE: Final = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,23}$")
_DASHES: Final = str.maketrans({"‐": "-", "‑": "-", "–": "-", "—": "-"})

MAX_CODE_LENGTH: Final = 24


def normalise_code(raw: str, *, kind: str = "code") -> str:
    """Fold a field written identifier onto its canonical form."""
    if not isinstance(raw, str):
        raise ValidationError(f"{kind} must be text", value=raw)
    text = raw.translate(_DASHES).strip().upper()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    if not text:
        raise ValidationError(f"{kind} cannot be blank", value=raw)
    if len(text) > MAX_CODE_LENGTH:
        raise ValidationError(
            f"{kind} is too long",
            value=raw,
            length=len(text),
            limit=MAX_CODE_LENGTH,
        )
    if _CODE.match(text) is None:
        raise ValidationError(f"{kind} has characters that are not allowed", value=raw)
    return text


def normalise_post_number(raw: str) -> str:
    """Test post numbers are codes, but a bare integer keeps its leading zeros off."""
    text = normalise_code(raw, kind="test post number")
    if text.isdigit():
        return str(int(text))
    return text


def is_code(raw: str) -> bool:
    """Whether a string would survive normalisation without changing meaning."""
    try:
        return normalise_code(raw) == raw
    except ValidationError:
        return False
