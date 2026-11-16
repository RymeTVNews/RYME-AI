"""Génération d'images locale via une API compatible Stable Diffusion WebUI / Forge.

Le serveur d'images (lancé avec l'option --api) tourne sur ton PC et utilise ta carte graphique.
"""

import base64
import json
import os
import urllib.error
import urllib.request

DEFAULT_IMAGE_HOST = "http://127.0.0.1:7860"


class ImageError(RuntimeError):
    pass


def _clamp(value, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def txt2img(prompt: str, negative_prompt: str = "", width=1024, height=1024, steps=25,
            host: str | None = None, timeout: int = 900) -> bytes:
    """Retourne les octets PNG de l'image générée."""
    host = (host or os.environ.get("RYME_IMAGE_HOST") or DEFAULT_IMAGE_HOST).rstrip("/")
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        # dimensions multiples de 8, bornées pour ne pas saturer la VRAM
        "width": _clamp(width, 256, 1536, 1024) // 8 * 8,
        "height": _clamp(height, 256, 1536, 1024) // 8 * 8,
        "steps": _clamp(steps, 1, 60, 25),
    }
    req = urllib.request.Request(
        host + "/sdapi/v1/txt2img", data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ImageError(
            f"Serveur d'images injoignable sur {host}. Lance Stable Diffusion WebUI Forge "
            f"avec l'option --api (voir le README). Détail : {exc}") from exc
    images = data.get("images") or []
    if not images:
        raise ImageError("Le serveur n'a renvoyé aucune image.")
    return base64.b64decode(images[0].split(",", 1)[-1])
