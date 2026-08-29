#!/usr/bin/env python3
"""Vérifie que docs/index.html reste équivalent, en contenu, à la page d'origine.

L'extraction des 42 fiches vers donnees/protocoles.json était une refonte de
tuyauterie, pas de contenu : la page livrée doit dire exactement la même chose
qu'avant. Ce script le prouve, en comparant la page générée à la version d'origine
telle que git la conserve.

    python3 outils/verifier.py
"""
import json
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "docs" / "index.html"

# Commit « mise à l'abri » : le référentiel tel que reçu, avant toute refonte.
REFERENCE = "b6eb37c:docs/index.html"

DEBUT, FIN = "  const protocols = [\n", "  ];\n"

# Champs ajoutés par la refonte : absents de l'origine, donc hors comparaison.
AJOUTS = ("id",)


def decouper(html):
    i = html.index(DEBUT)
    j = html.index(FIN, i)
    return html[:i], html[i + len(DEBUT):j], html[j + len(FIN):]


def lire_fiches(bloc):
    """Le bloc d'origine est du littéral JS ; celui d'aujourd'hui est du JSON."""
    txt = "[\n" + bloc + "]"
    txt = re.sub(r'(?m)^(\s+)([A-Za-z][A-Za-z0-9_]*):', r'\1"\2":', txt)
    txt = re.sub(r',(\s*[}\]])', r'\1', txt)
    return json.loads(txt)


def main():
    origine = subprocess.run(
        ["git", "show", REFERENCE], cwd=RACINE, check=True,
        capture_output=True, text=True).stdout
    actuel = SORTIE.read_text(encoding="utf-8")

    pre_o, bloc_o, suf_o = decouper(origine)
    pre_a, bloc_a, suf_a = decouper(actuel)

    ecarts = []
    if pre_o != pre_a:
        ecarts.append("l'en-tête de la page (style, structure) a changé")
    if suf_o != suf_a:
        ecarts.append("le script de rendu et de recherche a changé")

    fiches_o, fiches_a = lire_fiches(bloc_o), lire_fiches(bloc_a)
    if len(fiches_o) != len(fiches_a):
        ecarts.append(f"{len(fiches_o)} fiches à l'origine, {len(fiches_a)} aujourd'hui")
    else:
        for rang, (avant, apres) in enumerate(zip(fiches_o, fiches_a)):
            apres = {k: v for k, v in apres.items() if k not in AJOUTS}
            if avant != apres:
                nom = fiches_a[rang].get("id", f"rang {rang}")
                for champ in sorted(set(avant) | set(apres)):
                    if avant.get(champ) != apres.get(champ):
                        ecarts.append(f"{nom} : champ « {champ} » modifié")

    if ecarts:
        print("Écarts avec la page d'origine :", file=sys.stderr)
        for e in ecarts:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Équivalence confirmée : {len(fiches_a)} fiches, "
          "contenu identique à la page d'origine.")


if __name__ == "__main__":
    main()
