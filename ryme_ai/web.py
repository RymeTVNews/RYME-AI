"""Recherche web et lecture de pages, sans clé d'API (DuckDuckGo + urllib)."""

import ipaddress
import re
import socket
import urllib.parse
import urllib.request
from html.parser import HTMLParser

MAX_PAGE = 8000
USER_AGENT = "Mozilla/5.0 (compatible; RYME-AI/0.1)"


class _ResultParser(HTMLParser):
    """Extrait titre, lien et extrait des résultats de html.duckduckgo.com."""

    def __init__(self):
        super().__init__()
        self.results: list[dict] = []
        self._field = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "a" and "result__a" in cls:
            self.results.append({"title": "", "url": _real_url(a.get("href", "")), "snippet": ""})
            self._field = "title"
        elif tag == "a" and "result__snippet" in cls and self.results:
            self._field = "snippet"

    def handle_endtag(self, tag):
        if tag == "a":
            self._field = None

    def handle_data(self, data):
        if self._field and self.results:
            self.results[-1][self._field] += data


def _real_url(href: str) -> str:
    """DuckDuckGo enveloppe les liens : on récupère l'adresse réelle."""
    if href.startswith("//"):
        href = "https:" + href
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
    return qs["uddg"][0] if "uddg" in qs else href


def parse_results(html: str, max_results: int = 5) -> list[dict]:
    p = _ResultParser()
    p.feed(html)
    out = []
    for r in p.results:
        r = {k: " ".join(v.split()) for k, v in r.items()}
        if r["title"] and r["url"].startswith("http"):
            out.append(r)
    return out[:max_results]


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    """Vérifie aussi chaque redirection (pas de détour vers une adresse privée)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _get(url: str, data: bytes | None = None, timeout: int = 15) -> str:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    opener = urllib.request.build_opener(_SafeRedirect)
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read(2_000_000)
        charset = resp.headers.get_content_charset() or "utf-8"
    return raw.decode(charset, errors="replace")


def web_search(query: str, max_results: int = 5) -> str:
    html = _get("https://html.duckduckgo.com/html/", data=urllib.parse.urlencode({"q": query}).encode())
    results = parse_results(html, int(max_results))
    if not results:
        return "Aucun résultat."
    return "\n\n".join(
        f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}" for i, r in enumerate(results, 1)
    )


class _TextParser(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        elif tag in ("p", "br", "div", "li", "h1", "h2", "h3", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    p = _TextParser()
    p.feed(html)
    text = "".join(p.parts)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def check_public_url(url: str) -> None:
    """Refuse les adresses locales ou privées (une page web ne doit pas viser ton PC/réseau)."""
    parts = urllib.parse.urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Seules les adresses http(s) sont autorisées.")
    for info in socket.getaddrinfo(parts.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ValueError("Adresse locale ou privée refusée.")


def fetch_url(url: str) -> str:
    check_public_url(url)
    body = _get(url)
    text = html_to_text(body) if "<" in body[:2000] else body
    return text[:MAX_PAGE] + ("\n...[tronqué]" if len(text) > MAX_PAGE else "")
