# RYME AI

Agent IA **100 % local** pour Windows : il discute, lit et écrit des fichiers et lance des commandes dans un dossier de travail, avec ta confirmation avant toute action risquée. Aucune donnée ne quitte ton PC.

## Installation (Windows, RTX 3080 Ti)

1. Installe [Ollama](https://ollama.com) et lance-le.
2. Télécharge un modèle (14B quantifié, tient dans 12 Go de VRAM) :
   `ollama pull qwen2.5-coder:14b`
3. Télécharge le build : onglet **Actions** du dépôt → dernier build → artefact `ryme-ai-windows` (ou page **Releases** pour une version taguée).
4. Double-clique `RYME-AI.exe` : la fenêtre de chat s'ouvre. Choisis ton dossier de travail avec le bouton « Dossier… ».
   (`ryme-ai-cli.exe` est la version terminal.)

Options : `--model`, `--host`, `--dir`. Variables : `RYME_MODEL`, `OLLAMA_HOST`.

## Développement

```
python -m unittest discover -s tests
python run_gui.py   # fenêtre de chat
python run_cli.py   # terminal
```

Pour publier une version : `git tag v0.1.0 && git push --tags`.

## Feuille de route

- Génération d'images locale (type Nano Banana) avec un modèle Stable Diffusion/FLUX
- Recherche web et mémoire entre sessions
- Installeur `.msi`
