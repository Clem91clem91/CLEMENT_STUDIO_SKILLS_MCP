# CLEMENT STUDIO SKILLS MCP

P0-02 fournit une interface MCP **READ-ONLY**, déterministe et auditable au-dessus du registre matérialisé par `CLEMENT_STUDIO_SKILLS_HUB`.

## Contrat

Le serveur expose exactement neuf outils :

- `skills_status`
- `skills_list`
- `skills_search`
- `skills_get`
- `skills_match`
- `skills_dependencies`
- `skills_conflicts`
- `skills_validate`
- `skills_bundle_plan`

Tous les outils sont annotés MCP `read_only_hint=True` et `open_world_hint=False`. Le serveur ne contient aucune opération d'écriture vers le Skills Hub.

## Source de vérité

Par défaut, le serveur attend le Hub dans le dépôt frère :

```text
04_TOOLS/
├── CLEMENT_STUDIO_SKILLS_HUB/
└── CLEMENT_STUDIO_SKILLS_MCP/
```

Registre attendu :

```text
CLEMENT_STUDIO_SKILLS_HUB/registry/skills_registry.json
```

Surcharges optionnelles :

- `CLEMENT_SKILLS_HUB_ROOT`
- `CLEMENT_SKILLS_REGISTRY_PATH`

Toute lecture de `SKILL.md` est contrôlée pour rester strictement à l'intérieur de la racine du Hub.

## Matching déterministe

P0-02 n'utilise initialement ni ChromaDB ni embeddings. Le ranking combine de manière reproductible :

1. correspondance exacte `name` / `id` ;
2. tokens du nom ;
3. mots-clés ;
4. catégorie ;
5. description ;
6. couverture complète des tokens demandés.

Les égalités sont triées par nom normalisé puis identifiant afin de conserver un résultat stable.

## Bundle planning

`skills_bundle_plan` résout les dépendances, calcule l'ordre d'exécution, détecte les dépendances manquantes et les cycles, contrôle les conflits entre skills sélectionnés, additionne `estimated_context_cost` et retourne un verdict `PASS`, `PARTIAL` ou `FAIL`.

## Installation Shadow

```powershell
Set-Location "C:\Users\Shadow\Documents\CLEMENT_STUDIO\04_TOOLS\CLEMENT_STUDIO_SKILLS_MCP"
py -3.11 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m pytest
```

Lancer en stdio :

```powershell
& .\.venv\Scripts\clement-skills-mcp.exe
```

ou :

```powershell
& .\.venv\Scripts\python.exe -m clement_skills_mcp.server
```

## CI

La CI `skills-mcp-ci` exécute compilation + tests sur :

- Windows / Python 3.11
- Windows / Python 3.13
- Ubuntu / Python 3.11
- Ubuntu / Python 3.13

## Gouvernance Git

- `main` : versions certifiées ;
- `develop` : intégration validée ;
- `feat/p0-skills-mcp` : développement P0-02.

Aucun merge, tag, release ou déploiement n'est effectué sans validation explicite.
