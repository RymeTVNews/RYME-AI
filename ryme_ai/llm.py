"""Client minimal pour Ollama (API locale, aucune dépendance externe)."""

import json
import urllib.error
import urllib.request

DEFAULT_HOST = "http://127.0.0.1:11434"
# Un modèle 14B quantifié tient dans les 12 Go de VRAM d'une RTX 3080 Ti.
DEFAULT_MODEL = "qwen2.5-coder:14b"


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, host: str = DEFAULT_HOST, model: str = DEFAULT_MODEL, timeout: int = 600):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def _post(self, path: str, payload: dict) -> dict:
        req = urllib.request.Request(
            self.host + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise OllamaError(
                f"Impossible de joindre Ollama sur {self.host}. "
                "Installe-le depuis https://ollama.com puis lance-le. "
                f"Détail : {exc}"
            ) from exc

    def is_up(self) -> bool:
        try:
            urllib.request.urlopen(self.host + "/api/tags", timeout=3).read()
            return True
        except Exception:
            return False

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Envoie la conversation et retourne le message de l'assistant."""
        payload = {"model": self.model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = tools
        data = self._post("/api/chat", payload)
        return data.get("message", {})
