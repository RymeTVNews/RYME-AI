import base64
import json
import struct
import tempfile
import zlib
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from ryme_ai import images
from ryme_ai.agent import Agent
from ryme_ai.memory import Memory
from ryme_ai.tools import Workspace

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
LAST_REQUEST: dict = {}


def make_png(w: int, h: int) -> bytes:
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff\x00\x00" * w for _ in range(h))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class FakeSD(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        LAST_REQUEST.clear()
        LAST_REQUEST.update(json.loads(body))
        LAST_REQUEST["_route"] = self.path
        out = json.dumps({"images": [base64.b64encode(PNG).decode()]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


class ImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeSD)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.host = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_txt2img_returns_png_and_clamps_size(self):
        png = images.txt2img("un chat", width=99999, height=5, steps=0, host=self.host)
        self.assertEqual(png, PNG)
        self.assertEqual(LAST_REQUEST["width"], 1536)
        self.assertEqual(LAST_REQUEST["height"], 256)
        self.assertEqual(LAST_REQUEST["steps"], 1)

    def test_workspace_saves_image(self):
        import os
        os.environ["RYME_IMAGE_HOST"] = self.host
        with tempfile.TemporaryDirectory() as d:
            out = Workspace(d).call("generate_image", {"prompt": "a cat"})
            self.assertTrue(out.startswith("Image créée : images/ryme_"), out)
            self.assertEqual((Path(d) / out.split(" : ")[1]).read_bytes(), PNG)

    def test_image_size_png_and_jpeg(self):
        self.assertEqual(images.image_size(make_png(300, 200)), (300, 200))
        jpeg = (b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
                b"\xff\xc0\x00\x11\x08\x01\x2c\x01\x90\x03\x01\x22\x00\x02\x11\x01\x03\x11\x01")
        self.assertEqual(images.image_size(jpeg), (400, 300))
        with self.assertRaises(images.ImageError):
            images.image_size(b"GIF89a....")

    def test_img2img_keeps_proportions_and_clamps_strength(self):
        images.img2img(make_png(2000, 1000), "make it blue", strength=5, host=self.host)
        self.assertEqual(LAST_REQUEST["_route"], "/sdapi/v1/img2img")
        self.assertEqual((LAST_REQUEST["width"], LAST_REQUEST["height"]), (1024, 512))
        self.assertEqual(LAST_REQUEST["denoising_strength"], 1.0)
        self.assertEqual(len(LAST_REQUEST["init_images"]), 1)

    def test_edit_image_keeps_original_and_blocks_escape(self):
        import os
        os.environ["RYME_IMAGE_HOST"] = self.host
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.png"
            original = make_png(64, 64)
            src.write_bytes(original)
            ws = Workspace(d)
            out = ws.call("edit_image", {"path": "a.png", "prompt": "blue"})
            self.assertTrue(out.startswith("Image créée : images/ryme_edit_"), out)
            self.assertEqual(src.read_bytes(), original)
            self.assertTrue(ws.call("edit_image", {"path": "../x.png", "prompt": "b"}).startswith("Erreur"))

    @staticmethod
    def _pixels(png: bytes):
        """Décode un PNG gris 8 bits produit par make_mask -> liste de lignes."""
        w, h = images.image_size(png)
        i, idat = 8, b""
        while i < len(png):
            n = struct.unpack(">I", png[i:i + 4])[0]
            if png[i + 4:i + 8] == b"IDAT":
                idat += png[i + 8:i + 8 + n]
            i += 12 + n
        raw = zlib.decompress(idat)
        return [raw[r * (w + 1) + 1:(r + 1) * (w + 1)] for r in range(h)]

    def test_make_mask_rectangle(self):
        rows = self._pixels(images.make_mask(100, 80, 0.5, 0, 1, 0.5))
        self.assertEqual(rows[10][75], 255)   # haut-droite : retouché
        self.assertEqual(rows[10][25], 0)     # haut-gauche : conservé
        self.assertEqual(rows[70][75], 0)     # bas-droite : conservé

    def test_make_mask_ellipse_corners_stay_black(self):
        rows = self._pixels(images.make_mask(100, 100, 0, 0, 1, 1, "ellipse"))
        self.assertEqual(rows[50][50], 255)
        self.assertEqual(rows[1][1], 0)

    def test_make_mask_rejects_empty_zone(self):
        with self.assertRaises(images.ImageError):
            images.make_mask(100, 100, 0.6, 0.6, 0.4, 0.4)

    def test_inpaint_sends_mask_matching_target_size(self):
        images.inpaint(make_png(2000, 1000), "a hat", 0, 0, 0.5, 0.5, host=self.host)
        self.assertEqual(LAST_REQUEST["_route"], "/sdapi/v1/img2img")
        mask = base64.b64decode(LAST_REQUEST["mask"])
        self.assertEqual(images.image_size(mask), (1024, 512))
        self.assertEqual((LAST_REQUEST["width"], LAST_REQUEST["height"]), (1024, 512))
        self.assertEqual(LAST_REQUEST["inpainting_mask_invert"], 0)

    def test_edit_zone_tool_keeps_original_and_validates(self):
        import os
        os.environ["RYME_IMAGE_HOST"] = self.host
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "a.png"
            original = make_png(64, 64)
            src.write_bytes(original)
            ws = Workspace(d)
            ok = ws.call("edit_image_zone", {"path": "a.png", "prompt": "hat",
                                             "left": 0, "top": 0, "right": 0.5, "bottom": 0.5})
            self.assertTrue(ok.startswith("Image créée : images/ryme_zone_"), ok)
            self.assertEqual(src.read_bytes(), original)
            bad = ws.call("edit_image_zone", {"path": "a.png", "prompt": "hat",
                                              "left": 0.9, "top": 0, "right": 0.1, "bottom": 1})
            self.assertTrue(bad.startswith("Erreur"), bad)

    def test_server_down_gives_clear_error(self):
        with self.assertRaises(images.ImageError):
            images.txt2img("x", host="http://127.0.0.1:9", timeout=2)


class MemoryTest(unittest.TestCase):
    def test_add_forget_and_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.md")
            m.add("Préfère les réponses courtes")
            m.add("Projet : RYME AI")
            self.assertEqual(m.add("Projet : RYME AI"), "Déjà en mémoire.")
            self.assertIn("Projet : RYME AI", m.as_prompt())
            self.assertIn("1 note", m.forget("courtes"))
            self.assertEqual(m.notes(), ["Projet : RYME AI"])

    def test_persists_across_instances(self):
        with tempfile.TemporaryDirectory() as d:
            Memory(Path(d) / "m.md").add("fait durable")
            self.assertEqual(Memory(Path(d) / "m.md").notes(), ["fait durable"])

    def test_remember_needs_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.md")
            self.assertIn("Refusé", Workspace(d, memory=m).call("remember", {"note": "x"}))
            self.assertEqual(m.notes(), [])
            Workspace(d, confirm=lambda _: True, memory=m).call("remember", {"note": "x"})
            self.assertEqual(m.notes(), ["x"])

    def test_agent_sees_memory_in_system_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory(Path(d) / "m.md")
            m.add("Machine : RTX 3080 Ti")
            agent = Agent(object(), Workspace(d, memory=m))
            self.assertIn("RTX 3080 Ti", agent.messages[0]["content"])


if __name__ == "__main__":
    unittest.main()
