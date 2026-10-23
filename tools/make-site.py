"""Build index.html, the project's home page, from tools/site/index.template.html.

Fills in the sound list from sounds/catalog.tsv (written by make-sounds.py, so
run that first).
Usage: python tools/make-site.py
The page plays sounds/<name>.wav by relative path, so GitHub Pages serves it
from the repository root (https://tzamaranth.github.io/claude-tada/). To try it
locally, open index.html from inside the repository.
"""

import json
from pathlib import Path

REPOSITORY_DIRECTORY = Path(__file__).resolve().parent.parent
CATALOG_PATH = REPOSITORY_DIRECTORY / "sounds" / "catalog.tsv"
TEMPLATE_PATH = REPOSITORY_DIRECTORY / "tools" / "site" / "index.template.html"
OUTPUT_PATH = REPOSITORY_DIRECTORY / "index.html"

SOUND_GROUPS = ("synth", "recording", "voice")
SOUND_KINDS = ("done", "nudge")


def read_catalog() -> list[dict[str, str]]:
    """Every bundled sound as {name, kind, description, group}."""
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"{CATALOG_PATH} is missing; run tools/make-sounds.py first")
    sounds = []
    for line_number, line in enumerate(CATALOG_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        fields = line.split("\t")
        if len(fields) != 4:
            raise ValueError(f"{CATALOG_PATH}:{line_number}: expected name, kind, description, group separated by tabs")
        name, kind, description, group = fields
        if group not in SOUND_GROUPS or kind not in SOUND_KINDS:
            raise ValueError(f"{CATALOG_PATH}:{line_number}: unknown group '{group}' or kind '{kind}'")
        sounds.append({"name": name, "kind": kind, "description": description, "group": group})
    return sounds


def fill_template(template: str, placeholder: str, value: object) -> str:
    if template.count(placeholder) != 1:
        raise ValueError(f"{TEMPLATE_PATH}: expected one {placeholder}, found {template.count(placeholder)}")
    return template.replace(placeholder, json.dumps(value, ensure_ascii=False))


def main() -> None:
    sounds = read_catalog()
    page = fill_template(TEMPLATE_PATH.read_text(encoding="utf-8"), "__SOUNDS__", sounds)
    OUTPUT_PATH.write_text(page, encoding="utf-8", newline="\n")
    print(f"wrote {OUTPUT_PATH} with {len(sounds)} sounds")


if __name__ == "__main__":
    main()
