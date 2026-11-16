"""Génération d'images locale via une API compatible Stable Diffusion WebUI / Forge.

Le serveur d'images (lancé avec l'option --api) tourne sur ton PC et utilise ta carte graphique.
"""

import base64
import json
import math
import os
import struct
import urllib.error
import urllib.request
import zlib

DEFAULT_IMAGE_HOST = "http://127.0.0.1:7860"


class ImageError(RuntimeError):
    pass


def _clamp(value, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _post(route: str, payload: dict, host: str | None, timeout: int) -> bytes:
    host = (host or os.environ.get("RYME_IMAGE_HOST") or DEFAULT_IMAGE_HOST).rstrip("/")
    req = urllib.request.Request(
        host + route, data=json.dumps(payload).encode("utf-8"),
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


def txt2img(prompt: str, negative_prompt: str = "", width=1024, height=1024, steps=25,
            host: str | None = None, timeout: int = 900) -> bytes:
    """Retourne les octets PNG de l'image générée à partir d'un texte."""
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        # dimensions multiples de 8, bornées pour ne pas saturer la VRAM
        "width": _clamp(width, 256, 1536, 1024) // 8 * 8,
        "height": _clamp(height, 256, 1536, 1024) // 8 * 8,
        "steps": _clamp(steps, 1, 60, 25),
    }
    return _post("/sdapi/v1/txt2img", payload, host, timeout)


def image_size(data: bytes) -> tuple[int, int]:
    """Largeur et hauteur d'un PNG ou JPEG (sans bibliothèque externe)."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + length
    raise ImageError("Format d'image non pris en charge (PNG ou JPEG seulement).")


def img2img(image: bytes, prompt: str, negative_prompt: str = "", strength=0.6, steps=25,
            host: str | None = None, timeout: int = 900) -> bytes:
    """Retransforme une image existante selon le texte. strength : 0.05 (proche) à 1 (libre)."""
    w, h = image_size(image)
    fit = min(1.0, 1024 / max(w, h))  # garde les proportions, 1024 px max
    try:
        strength = max(0.05, min(1.0, float(strength)))
    except (TypeError, ValueError):
        strength = 0.6
    payload = {
        "init_images": [base64.b64encode(image).decode("ascii")],
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "denoising_strength": strength,
        "width": max(64, min(1536, round(w * fit / 8) * 8)),
        "height": max(64, min(1536, round(h * fit / 8) * 8)),
        "steps": _clamp(steps, 1, 60, 25),
    }
    return _post("/sdapi/v1/img2img", payload, host, timeout)


def _target_size(w: int, h: int) -> tuple[int, int]:
    fit = min(1.0, 1024 / max(w, h))  # garde les proportions, 1024 px max
    return (max(64, min(1536, round(w * fit / 8) * 8)),
            max(64, min(1536, round(h * fit / 8) * 8)))


def make_mask(width: int, height: int, left: float, top: float, right: float, bottom: float,
              shape: str = "rectangle") -> bytes:
    """PNG en niveaux de gris : blanc = zone à retoucher, noir = zone conservée.
    Les bords sont des fractions de l'image (0 = gauche/haut, 1 = droite/bas)."""
    left, top, right, bottom = (max(0.0, min(1.0, float(v))) for v in (left, top, right, bottom))
    if right - left < 0.01 or bottom - top < 0.01:
        raise ImageError("Zone invalide : il faut left < right et top < bottom (valeurs entre 0 et 1).")
    x0, x1 = left * width, right * width
    y0, y1 = top * height, bottom * height
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    rows = []
    for y in range(height):
        row = bytearray(width)
        if y0 <= y + 0.5 <= y1:
            if shape == "ellipse":
                dy = (y + 0.5 - cy) / ry
                half = rx * math.sqrt(max(0.0, 1 - dy * dy))
                a, b = round(cx - half), round(cx + half)
            else:
                a, b = round(x0), round(x1)
            a, b = max(0, a), min(width, b)
            row[a:b] = b"\xff" * max(0, b - a)
        rows.append(b"\x00" + bytes(row))  # filtre « aucun » + pixels

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b""))


def inpaint(image: bytes, prompt: str, left: float, top: float, right: float, bottom: float,
            shape: str = "rectangle", negative_prompt: str = "", strength=0.75, steps=25,
            host: str | None = None, timeout: int = 900) -> bytes:
    """Ne retouche que la zone indiquée ; le reste de l'image est conservé."""
    w, h = image_size(image)
    tw, th = _target_size(w, h)
    mask = make_mask(tw, th, left, top, right, bottom, shape)
    try:
        strength = max(0.05, min(1.0, float(strength)))
    except (TypeError, ValueError):
        strength = 0.75
    payload = {
        "init_images": [base64.b64encode(image).decode("ascii")],
        "mask": base64.b64encode(mask).decode("ascii"),
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "denoising_strength": strength,
        "inpainting_fill": 1,           # part du contenu d'origine
        "inpaint_full_res": True,       # travaille la zone en haute résolution
        "inpaint_full_res_padding": 32,
        "inpainting_mask_invert": 0,    # blanc = zone retouchée
        "mask_blur": 8,                 # fondu des bords pour éviter les coutures
        "width": tw,
        "height": th,
        "steps": _clamp(steps, 1, 60, 25),
    }
    return _post("/sdapi/v1/img2img", payload, host, timeout)
