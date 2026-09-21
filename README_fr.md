# PyKMExtract

[English](README.md) | [中文](README_zh.md) | **Français**

PyKMExtract est un outil de numérisation de courbes Kaplan-Meier orienté recherche. Il extrait des courbes structurées `time / survival` à partir de figures publiées, valide le résultat et exporte des tableaux et superpositions visuelles faciles à vérifier.

## Vue d’ensemble

Le principe central du projet est :

`pipeline par défaut simple + modules d’amélioration IA optionnels`

Le chemin par défaut reste lisible et vérifiable. L’IA peut intervenir, mais comme couche de raffinement explicite, pas comme moteur de mesure opaque.

Pipeline par défaut :

`semantic -> axis detection -> color extraction -> KM step sampling -> coordinate mapping -> validation`

## État actuel

Le dépôt est aujourd’hui un MVP pratique, pas encore un numériseur KM universel.

Fonctionnalités déjà solides :

- entrée sémantique structurée via JSON ou modèle de vision
- détection automatique des axes gauche/bas sur des figures KM classiques à fond blanc
- extraction par couleur pour 1-2 courbes à fort contraste
- échantillonnage en marches adapté aux KM, plutôt qu’une interpolation linéaire naïve
- validation, score de confiance et export d’un bundle de revue
- exports CSV génériques pour les outils d’analyse de survie en aval

Cas encore traités de façon prudente :

- figures en niveaux de gris ou couleurs proches
- figures denses à plusieurs courbes
- bandes de confiance marquées et marques de censure denses
- scans basse résolution ou captures compressées
- découpage PDF entièrement automatisé et interface graphique de correction

## Fonctions principales

- extraction sémantique structurée depuis `semantic.json` ou un endpoint compatible OpenAI
- détection des axes et raffinement optionnel par quatre ancres
- échantillonnage en marches spécifique aux courbes KM
- validation via monotonie, plage, couverture, `at-risk` et ambiguïté de chevauchement
- bundle de revue humaine avec `overlay.png`, `review.md`, courbes numérisées et CSV de validation
- workflow batch pour des études groupées du type `study01_full.png`, `study01_pfs.png`, `study01_os.png`

## Installation

Installation en mode éditable :

```bash
pip install -e .
```

Ou exécution directe depuis les sources :

```bash
PYTHONPATH=src python3 -m pykmextract.cli ...
```

## Démarrage rapide

### 1. Figure unique avec `semantic.json`

```bash
PYTHONPATH=src python3 -m pykmextract.cli figure.png \
  --semantic-json semantic.json \
  --output-json extraction.json \
  --overlay overlay.png
```

### 2. Figure unique avec endpoint de vision compatible OpenAI

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH=src python3 -m pykmextract.cli figure.png \
  --provider openai-compatible \
  --base-url https://openrouter.ai/api/v1 \
  --model openai/gpt-5.4 \
  --api-key-env OPENROUTER_API_KEY \
  --output-json extraction.json \
  --overlay overlay.png
```

### 3. Raffinement IA optionnel des axes

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH=src python3 -m pykmextract.cli figure.png \
  --provider openai-compatible \
  --base-url https://openrouter.ai/api/v1 \
  --model openai/gpt-5.4 \
  --api-key-env OPENROUTER_API_KEY \
  --axis-refine \
  --axis-review-image axis_review.png \
  --output-json extraction.json \
  --overlay overlay.png
```

### 4. Utilisation en Python

```python
import pykmextract as pkm

result = pkm.extract("figure.png", semantic=semantic_payload)
curve_df = result.curve_frame()
validation_df = result.validation_frame()

result.save_review_bundle("runs/example")
```

## Workflow batch

Convention de nommage recommandée :

- `study01_full.png`
- `study01_pfs.png`
- `study01_os.png`

Générer le manifest :

```bash
PYTHONPATH=src python3 -m pykmextract.batch \
  --image-dir images \
  --literature-md images/literatures.md \
  --output-json images/manifest.json
```

Lancer le batch :

```bash
export OPENROUTER_API_KEY="..."
PYTHONPATH=src python3 -m pykmextract.batch_run \
  --image-dir images \
  --literature-md images/literatures.md \
  --base-url https://openrouter.ai/api/v1 \
  --model openai/gpt-5.4 \
  --api-key-env OPENROUTER_API_KEY \
  --axis-refine \
  --output-dir runs/openrouter-batch
```

La sortie est structurée par étude et par endpoint :

- `runs/study01/os/`
- `runs/study01/pfs/`
- `runs/study02/os/`
- `runs/study02/pfs/`

## Sorties

Champs structurés principaux :

- `semantic`
- `axis_bounds`
- `axis_anchors`
- `curves[].time`
- `curves[].survival`
- `validation.score`
- `validation.level`
- `validation.issues`

Bundle de revue :

- `original.png`
- `overlay.png`
- `digitized_curves.csv`
- `review.md`
- `validation_issues.csv`

## Résultats actuels sur figures réelles

Dernier résumé batch :

- [`runs/summary.json`](runs/summary.json)

Vue d’ensemble des 10 overlays :

![all overlays](runs/all_overlays_contact_sheet.png)

Évaluation visuelle manuelle du batch actuel :

| Panneau | Score / Niveau | Appréciation | Point principal |
| --- | --- | --- | --- |
| `study01 / os` | `80 / high` | bon | divergence en fin de courbe vs `at-risk` |
| `study01 / pfs` | `85 / high` | utilisable mais plus faible au milieu et à la fin | couverture insuffisante pour `Sorafenib` |
| `study02 / os` | `80 / high` | utilisable | les deux courbes divergent de `at-risk` |
| `study02 / pfs` | `80 / high` | faible | `Placebo plus chemotherapy` reste trop basse |
| `study03 / os` | `80 / high` | faible | marches grossières et faible accord avec `at-risk` |
| `study03 / pfs` | `80 / high` | faible | segments tardifs encore trop approximatifs |
| `study04 / os` | `100 / high` | meilleur panneau du lot | meilleure correspondance visuelle |
| `study04 / pfs` | `100 / medium` | bon mais relecture humaine nécessaire | long segment de chevauchement |
| `study05 / os` | `80 / high` | bon | visuellement fort, pénalisé surtout par `at-risk` |
| `study05 / pfs` | `80 / high` | bon | proche de `study05 / os` |

Conclusion réaliste :

- `study04 / os` est le meilleur panneau à montrer
- `study05 / os` et `study05 / pfs` sont visuellement meilleurs que leur simple `80 / high`
- `study02 / pfs`, `study03 / os` et `study03 / pfs` restent des cas faibles
- `study04 / pfs` est abaissé volontairement à cause de `overlap_ambiguity`

## Structure du dépôt

Modules clés :

- [`src/pykmextract/pipeline.py`](src/pykmextract/pipeline.py) : orchestration principale
- [`src/pykmextract/runtime.py`](src/pykmextract/runtime.py) : runtime partagé entre CLI et batch
- [`src/pykmextract/extractor/semantic.py`](src/pykmextract/extractor/semantic.py) : extraction sémantique et normalisation
- [`src/pykmextract/extractor/coord.py`](src/pykmextract/extractor/coord.py) : axes et mapping pixel -> données
- [`src/pykmextract/extractor/pixel.py`](src/pykmextract/extractor/pixel.py) : extraction couleur et échantillonnage KM
- [`src/pykmextract/extractor/validator.py`](src/pykmextract/extractor/validator.py) : validation et score de confiance
- [`src/pykmextract/extractor/axis_refiner.py`](src/pykmextract/extractor/axis_refiner.py) : orchestration du raffinement IA des axes
- [`src/pykmextract/extractor/_axis_refiner_prompts.py`](src/pykmextract/extractor/_axis_refiner_prompts.py) : prompts
- [`src/pykmextract/extractor/_axis_refiner_payloads.py`](src/pykmextract/extractor/_axis_refiner_payloads.py) : candidats et normalisation des réponses
- [`src/pykmextract/extractor/_axis_refiner_board.py`](src/pykmextract/extractor/_axis_refiner_board.py) : boards de revue
- [`src/pykmextract/enhancements.py`](src/pykmextract/enhancements.py) : modules IA optionnels
- [`src/pykmextract/microtune.py`](src/pykmextract/microtune.py) : micro-ajustements bornés après extraction
- [`src/pykmextract/review.py`](src/pykmextract/review.py) : export overlay et bundles de revue

## Développement

Lancer tous les tests :

```bash
python3 -m unittest discover -s tests -v
```

Couverture actuelle :

- extraction de bout en bout sur figures synthétiques
- chemins CLI
- prompts et logique de raffinement des axes
- comportement de l’échantillonnage pixel
- export des bundles de revue
- parsing des réponses provider

Fichiers du projet :

- [LICENSE](LICENSE)
- [Guide de contribution](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Principes de conception

- garder le pipeline par défaut simple
- garder les modules IA optionnels et explicites
- préférer des heuristiques compréhensibles à une accumulation de cas spéciaux
- conserver les figures difficiles comme cas limites visibles plutôt que les masquer
