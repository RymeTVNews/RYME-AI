import unittest

from ryme_ai import web
from ryme_ai.tools import Workspace

SAMPLE = """
<div class="result">
  <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fa&rut=x">Titre <b>A</b></a>
  <a class="result__snippet" href="#">Un extrait
     sur deux lignes</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.org/b">Titre B</a>
  <a class="result__snippet" href="#">Extrait B</a>
</div>
"""


class WebTest(unittest.TestCase):
    def test_parse_results(self):
        r = web.parse_results(SAMPLE)
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0]["url"], "https://example.com/a")
        self.assertEqual(r[0]["title"], "Titre A")
        self.assertEqual(r[0]["snippet"], "Un extrait sur deux lignes")

    def test_max_results(self):
        self.assertEqual(len(web.parse_results(SAMPLE, 1)), 1)

    def test_html_to_text(self):
        text = web.html_to_text("<html><head><title>x</title></head><body><script>bad()</script>"
                                "<p>Bonjour</p><p>monde</p></body></html>")
        self.assertEqual(text, "Bonjour\nmonde")

    def test_private_urls_refused(self):
        for url in ("http://127.0.0.1:11434/", "http://localhost/", "file:///etc/passwd",
                    "http://192.168.1.1/"):
            with self.assertRaises(ValueError):
                web.check_public_url(url)

    def test_tool_error_returned_to_model(self):
        out = Workspace(".").call("fetch_url", {"url": "http://127.0.0.1/"})
        self.assertTrue(out.startswith("Erreur"))


if __name__ == "__main__":
    unittest.main()
