"""Interface en ligne de commande de RYME AI."""

import argparse
import os
import sys
import time

from . import __version__
from .agent import Agent
from .history import History
from .memory import Memory
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
    parser.add_argument("--continue", dest="resume", nargs="?", const="1", metavar="N|ID",
                        help="reprendre une discussion : la dernière, ou le numéro (voir --list) / l'identifiant")
    parser.add_argument("--list", action="store_true", help="lister les discussions sauvegardées")
    parser.add_argument("--version", action="version", version=f"RYME AI {__version__}")
    args = parser.parse_args(argv)

    history = History()
    if args.list:
        found = history.list()
        if not found:
            print("Aucune discussion sauvegardée.")
        for n, d in enumerate(found, 1):
            when = time.strftime("%d/%m/%Y %H:%M", time.localtime(d["updated"]))
            print(f"{n:>3}. {when}  {d['title']}  ({d['count']} échange(s))  [{d['id']}]")
        return 0

    saved = None
    if args.resume:
        found = history.list()
        if args.resume.isdigit():
            n = int(args.resume)
            saved = found[n - 1] if 1 <= n <= len(found) else None
        else:
            saved = history.load(args.resume)
        if not saved:
            print(f"Discussion introuvable : {args.resume} (voir --list).")
            return 1

    llm = OllamaClient(host=args.host, model=args.model)
    if not llm.is_up():
        print("Ollama ne répond pas. Installe-le depuis https://ollama.com, lance-le,")
        print(f"puis télécharge le modèle :  ollama pull {args.model}")
        input("\nAppuie sur Entrée pour quitter.")
        return 1

    directory = saved["directory"] if saved and saved["directory"] and os.path.isdir(saved["directory"]) else args.dir
    agent = Agent(llm, Workspace(directory, confirm=_confirm, memory=Memory()),
                  on_tool=_show_tool, history=history)
    if saved:
        agent.restore(saved["id"], saved["messages"])
        users = sum(1 for m in saved["messages"] if m.get("role") == "user")
        print(f"Discussion reprise ({users} échange(s)) dans {directory}")
    args.dir = directory
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
