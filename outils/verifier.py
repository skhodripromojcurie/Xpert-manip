#!/usr/bin/env python3
"""Vérifie qu'aucune des 42 fiches d'origine n'a dérivé.

L'extraction vers donnees/protocoles.json était une refonte de tuyauterie, pas de
contenu. Ce script le prouve en comparant la page générée à la version d'origine
que git conserve : les 42 fiches reçues doivent toujours dire exactement la même
chose. Les fiches ajoutées depuis sont signalées, pas reprochées.

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

# Modifications volontaires d'une fiche d'origine. Chaque entrée dit pourquoi : sans
# cela le contrôle ne distingue pas un enrichissement décidé d'une dérive subie, et
# on finirait par le désarmer.
ENRICHISSEMENTS = {
    ("pied-traumato", "parameters"):
        "apophyse de la base du 5e métatarsien — fait de manuel remonté du cas 3",
    ("pied-traumato", "keywords"):
        "mots-clés de l'apophyse et du pied de l'enfant",
}


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

    ecarts, assumes = [], []
    if pre_o != pre_a:
        ecarts.append("l'en-tête de la page (style, structure) a changé")
    if suf_o != suf_a:
        ecarts.append("le script de rendu et de recherche a changé")

    fiches_o, fiches_a = lire_fiches(bloc_o), lire_fiches(bloc_a)
    # Les fiches d'origine n'ont pas d'identifiant : on les apparie par titre.
    par_titre = {f["title"]: f for f in fiches_a}
    for avant in fiches_o:
        apres = par_titre.get(avant["title"])
        if apres is None:
            ecarts.append(f"fiche d'origine disparue : « {avant['title'][:60]} »")
            continue
        nom = apres.get("id", avant["title"][:40])
        apres = {k: v for k, v in apres.items() if k not in AJOUTS}
        for champ in sorted(set(avant) | set(apres)):
            if avant.get(champ) == apres.get(champ):
                continue
            raison = ENRICHISSEMENTS.get((nom, champ))
            if raison:
                assumes.append(f"{nom} · {champ} — {raison}")
            else:
                ecarts.append(f"{nom} : champ « {champ} » modifié")

    ajoutees = [f["id"] for f in fiches_a
                if f["title"] not in {o["title"] for o in fiches_o}]

    if ecarts:
        print("Écarts avec la page d'origine :", file=sys.stderr)
        for e in ecarts:
            print(f"  - {e}", file=sys.stderr)
        raise SystemExit(1)

    intactes = len(fiches_o) - len({e.split(" · ")[0] for e in assumes})
    print(f"Fiches d'origine : {intactes} intactes, "
          f"{len(fiches_o) - intactes} enrichies volontairement.")
    for a in assumes:
        print(f"  · {a}")
    if ajoutees:
        print(f"Ajoutées depuis ({len(ajoutees)}) : {', '.join(ajoutees)}.")


if __name__ == "__main__":
    main()
