"""Interface en ligne de commande de RYME AI."""

import argparse
import os
import sys

from . import __version__
from .agent import Agent
from .llm import DEFAULT_HOST, DEFAULT_MODEL, OllamaClient, OllamaError
from .tools import Workspace


def _confirm(description: str) -> bool:
    answer = input(f"\n⚠  {description}\n   Autoriser ? [o/N] ").strip().lower()
    return answer in ("o", "oui", "y", "yes")


def _show_tool(name, args, result):
    first = result.splitlines()[0] if result else ""
    print(f"  🔧 {name}({', '.join(f'{k}=…' for k in args)}) → {first[:80]}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ryme-ai", description="RYME AI : agent IA local")
    parser.add_argument("--model", default=os.environ.get("RYME_MODEL", DEFAULT_MODEL))
    parser.add_argument("--host", default=os.environ.get("OLLAMA_HOST", DEFAULT_HOST))
    parser.add_argument("--dir", default=os.getcwd(), help="dossier de travail de l'agent")
    parser.add_argument("--version", action="version", version=f"RYME AI {__version__}")
    args = parser.parse_args(argv)

    llm = OllamaClient(host=args.host, model=args.model)
    if not llm.is_up():
        print("Ollama ne répond pas. Installe-le depuis https://ollama.com, lance-le,")
        print(f"puis télécharge le modèle :  ollama pull {args.model}")
        input("\nAppuie sur Entrée pour quitter.")
        return 1

    agent = Agent(llm, Workspace(args.dir, confirm=_confirm), on_tool=_show_tool)
    print(f"RYME AI {__version__} — modèle {args.model} — dossier {args.dir}")
    print("Tape ta demande (« exit » pour quitter).\n")
    while True:
        try:
            text = input("vous › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if text.lower() in ("exit", "quit", "q"):
            return 0
        if not text:
            continue
        try:
            print(f"\nryme › {agent.ask(text)}\n")
        except OllamaError as exc:
            print(f"\nErreur : {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
