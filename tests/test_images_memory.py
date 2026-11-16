import base64
import json
import tempfile
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


class FakeSD(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        LAST_REQUEST.update(json.loads(body))
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
