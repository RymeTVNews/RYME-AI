"""Zone choisie à la souris sur une image -> bloc de texte compris par l'agent."""

import re

MIN_SIZE = 0.02  # une zone plus petite que 2 % de l'image est ignorée (simple clic)
_HINT_RE = re.compile(r"\[zone :[^\]]*\]\s*")


def selection_to_fractions(x0: float, y0: float, x1: float, y1: float,
                           width: int, height: int) -> tuple[float, float, float, float] | None:
    """Pixels du canevas -> (left, top, right, bottom) en fractions de 0 à 1.
    Accepte un glissement dans n'importe quel sens et reste dans l'image."""
    if width <= 0 or height <= 0:
        return None
    left, right = sorted((x0, x1))
    top, bottom = sorted((y0, y1))
    left, right = (max(0.0, min(1.0, v / width)) for v in (left, right))
    top, bottom = (max(0.0, min(1.0, v / height)) for v in (top, bottom))
    if right - left < MIN_SIZE or bottom - top < MIN_SIZE:
        return None
    return round(left, 3), round(top, 3), round(right, 3), round(bottom, 3)


def format_hint(path: str, fractions: tuple[float, float, float, float],
                shape: str = "rectangle") -> str:
    left, top, right, bottom = fractions
    return (f"[zone : {path} | left={left:.3f} top={top:.3f} right={right:.3f} "
            f"bottom={bottom:.3f} | {shape}]")


def replace_hint(text: str, hint: str) -> str:
    """Met le bloc de zone au début du texte saisi, en remplaçant un éventuel ancien bloc."""
    rest = _HINT_RE.sub("", text).strip()
    return hint + " " + rest if rest else hint + " "
