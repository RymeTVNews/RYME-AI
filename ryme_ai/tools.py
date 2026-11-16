"""Outils que l'agent peut utiliser (lecture/écriture de fichiers, commandes)."""

import subprocess
import time
from pathlib import Path

from . import images, web

MAX_OUTPUT = 8000


class Workspace:
    """Dossier de travail : l'agent ne peut pas écrire en dehors."""

    def __init__(self, root: str | Path, confirm=None, memory=None):
        self.root = Path(root).resolve()
        self.memory = memory  # objet Memory ou None
        # confirm(description) -> bool ; par défaut tout est refusé pour les actions risquées
        self.confirm = confirm or (lambda _desc: False)

    def _resolve(self, path: str) -> Path:
        p = (self.root / path).resolve()
        if p != self.root and self.root not in p.parents:
            raise ValueError(f"Chemin en dehors du dossier de travail : {path}")
        return p

    def list_dir(self, path: str = ".") -> str:
        p = self._resolve(path)
        entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        return "\n".join(f"{e.name}{'/' if e.is_dir() else ''}" for e in entries) or "(vide)"

    def read_file(self, path: str) -> str:
        text = self._resolve(path).read_text(encoding="utf-8", errors="replace")
        return text[:MAX_OUTPUT] + ("\n...[tronqué]" if len(text) > MAX_OUTPUT else "")

    def write_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        if not self.confirm(f"Écrire le fichier {p} ({len(content)} caractères)"):
            return "Refusé par l'utilisateur."
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Fichier écrit : {path}"

    def run_command(self, command: str) -> str:
        if not self.confirm(f"Exécuter la commande : {command}"):
            return "Refusé par l'utilisateur."
        try:
            res = subprocess.run(
                command, shell=True, cwd=self.root, capture_output=True, text=True, timeout=120
            )
        except subprocess.TimeoutExpired:
            return "Commande interrompue (délai de 120 s dépassé)."
        out = (res.stdout + res.stderr)[:MAX_OUTPUT]
        return f"[code {res.returncode}]\n{out}"

    def generate_image(self, prompt: str, negative_prompt: str = "", width: int = 1024,
                       height: int = 1024, steps: int = 25) -> str:
        png = images.txt2img(prompt, negative_prompt, width, height, steps)
        out = self._resolve("images")
        out.mkdir(exist_ok=True)
        path = out / f"ryme_{time.strftime('%Y%m%d_%H%M%S')}.png"
        path.write_bytes(png)
        return f"Image créée : {path.relative_to(self.root).as_posix()}"

    def edit_image(self, path: str, prompt: str, negative_prompt: str = "",
                   strength: float = 0.6, steps: int = 25) -> str:
        src = self._resolve(path)
        if src.stat().st_size > 20_000_000:
            return "Image trop volumineuse (20 Mo maximum)."
        png = images.img2img(src.read_bytes(), prompt, negative_prompt, strength, steps)
        out = self._resolve("images")
        out.mkdir(exist_ok=True)
        dest = out / f"ryme_edit_{time.strftime('%Y%m%d_%H%M%S')}.png"
        dest.write_bytes(png)  # l'original n'est jamais modifié
        return f"Image créée : {dest.relative_to(self.root).as_posix()}"

    def remember(self, note: str) -> str:
        if self.memory is None:
            return "La mémoire est désactivée."
        if not self.confirm(f"Mémoriser pour les prochaines sessions : « {note} »"):
            return "Refusé par l'utilisateur."
        return self.memory.add(note)

    def forget(self, text: str) -> str:
        if self.memory is None:
            return "La mémoire est désactivée."
        if not self.confirm(f"Oublier les notes contenant : « {text} »"):
            return "Refusé par l'utilisateur."
        return self.memory.forget(text)

    def call(self, name: str, args: dict) -> str:
        fn = {
            "list_dir": self.list_dir,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "run_command": self.run_command,
            "web_search": web.web_search,
            "fetch_url": web.fetch_url,
            "generate_image": self.generate_image,
            "edit_image": self.edit_image,
            "remember": self.remember,
            "forget": self.forget,
        }.get(name)
        if fn is None:
            return f"Outil inconnu : {name}"
        try:
            return fn(**args)
        except Exception as exc:  # l'erreur est renvoyée au modèle pour qu'il corrige
            return f"Erreur : {exc}"


def _tool(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


TOOL_SPECS = [
    _tool("list_dir", "Liste le contenu d'un dossier.",
          {"path": {"type": "string", "description": "Chemin relatif"}}, []),
    _tool("read_file", "Lit un fichier texte.",
          {"path": {"type": "string"}}, ["path"]),
    _tool("write_file", "Crée ou remplace un fichier texte.",
          {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _tool("run_command", "Exécute une commande shell dans le dossier de travail.",
          {"command": {"type": "string"}}, ["command"]),
    _tool("web_search", "Cherche sur le web (informations récentes, documentation).",
          {"query": {"type": "string"}}, ["query"]),
    _tool("fetch_url", "Télécharge une page web et retourne son texte.",
          {"url": {"type": "string"}}, ["url"]),
    _tool("generate_image",
          "Génère une image avec le GPU local à partir d'une description en anglais (plus "
          "précise qu'en français). Retourne le chemin du fichier PNG créé.",
          {"prompt": {"type": "string", "description": "Description détaillée, en anglais"},
           "negative_prompt": {"type": "string"},
           "width": {"type": "integer"}, "height": {"type": "integer"},
           "steps": {"type": "integer"}}, ["prompt"]),
    _tool("edit_image",
          "Modifie une image existante (PNG ou JPEG du dossier de travail) selon une description "
          "en anglais, et enregistre le résultat dans une nouvelle image (l'original est conservé). "
          "strength : 0.2-0.4 = retouche légère, 0.6 = changement net, 0.8+ = refonte libre.",
          {"path": {"type": "string", "description": "Image à modifier, chemin relatif"},
           "prompt": {"type": "string", "description": "Description du résultat voulu, en anglais"},
           "negative_prompt": {"type": "string"},
           "strength": {"type": "number"}, "steps": {"type": "integer"}},
          ["path", "prompt"]),
    _tool("remember", "Garde une information durable sur l'utilisateur ou ses projets "
          "pour les prochaines sessions (préférences, décisions). Une phrase courte.",
          {"note": {"type": "string"}}, ["note"]),
    _tool("forget", "Supprime de la mémoire les notes contenant ce texte.",
          {"text": {"type": "string"}}, ["text"]),
]
