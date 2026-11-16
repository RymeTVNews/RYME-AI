# RYME AI

Agent IA **100 % local** pour Windows : il discute, lit et écrit des fichiers et lance des commandes dans un dossier de travail, avec ta confirmation avant toute action risquée. Aucune donnée ne quitte ton PC.

## Installation (Windows, RTX 3080 Ti)

1. Installe [Ollama](https://ollama.com) et lance-le.
2. Télécharge un modèle (14B quantifié, tient dans 12 Go de VRAM) :
   `ollama pull qwen2.5-coder:14b`
3. Télécharge `ryme-ai.exe` : onglet **Actions** du dépôt → dernier build → artefact `ryme-ai-windows` (ou page **Releases** pour une version taguée).
4. Ouvre un terminal dans ton dossier de projet et lance `ryme-ai.exe`.

Options : `--model`, `--host`, `--dir`. Variables : `RYME_MODEL`, `OLLAMA_HOST`.

## Développement

```
python -m unittest discover -s tests
python -m ryme_ai
```

Pour publier une version : `git tag v0.1.0 && git push --tags`.

## Feuille de route

- Interface graphique (fenêtre de chat)
- Génération d'images locale (type Nano Banana) avec un modèle Stable Diffusion/FLUX
- Recherche web et mémoire entre sessions
- Installeur `.msi`
