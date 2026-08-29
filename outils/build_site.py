#!/usr/bin/env python3
"""Génère docs/index.html depuis donnees/protocoles.json et outils/template.html.

Le site livré est un fichier unique et autonome : le JSON est réinjecté dans la
page au moment du build, pas chargé en fetch. C'est délibéré — le référentiel
doit s'ouvrir depuis un téléphone, hors connexion, et s'envoyer d'un bloc.

    python3 outils/build_site.py             # écrit docs/index.html
    python3 outils/build_site.py --verifier  # vérifie sans écrire
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "donnees" / "protocoles.json"
TEMPLATE = RACINE / "outils" / "template.html"
SORTIE = RACINE / "docs" / "index.html"

MARQUEUR = "{{PROTOCOLES}}"

# Champs internes, utiles au classement et aux renvois du guide, mais qui n'ont
# rien à faire dans la page livrée.
CHAMPS_INTERNES = ("groupe", "axe")

GROUPES = {
    "thorax": "Thorax, gril costal et sternum",
    "rachis": "Rachis",
    "bassin": "Bassin, hanche, sacrum et coccyx",
    "epaule": "Épaule, clavicule et acromio-claviculaire",
    "coude-bras": "Coude, humérus et avant-bras",
    "main-poignet": "Poignet, main et doigts",
    "femur-jambe": "Fémur et jambe",
    "genou": "Genou",
    "cheville-pied": "Cheville, pied et calcanéum",
    "tete": "Crâne et massif facial",
    "asp": "Abdomen (ASP)",
}

AXES = {"traumato", "rhumato", "mixte"}


def controler(fiches):
    """Refuse de construire sur des données incohérentes."""
    erreurs = []
    identifiants = [f["id"] for f in fiches]
    for doublon in {i for i in identifiants if identifiants.count(i) > 1}:
        erreurs.append(f"identifiant en double : {doublon}")
    for f in fiches:
        if f["groupe"] not in GROUPES:
            erreurs.append(f"{f['id']} : groupe inconnu « {f['groupe']} »")
        if f["axe"] not in AXES:
            erreurs.append(f"{f['id']} : axe inconnu « {f['axe']} »")
        if "</" in json.dumps(f, ensure_ascii=False):
            erreurs.append(f"{f['id']} : contient « </ », qui fermerait le <script>")
    if erreurs:
        raise SystemExit("Données invalides :\n  - " + "\n  - ".join(erreurs))


def construire():
    fiches = json.loads(DONNEES.read_text(encoding="utf-8"))
    controler(fiches)

    publiables = [{k: v for k, v in f.items() if k not in CHAMPS_INTERNES}
                  for f in fiches]
    blob = json.dumps(publiables, ensure_ascii=False, indent=2)
    blob = "\n".join("  " + ligne for ligne in blob.splitlines())

    template = TEMPLATE.read_text(encoding="utf-8")
    if MARQUEUR not in template:
        raise SystemExit(f"Marqueur {MARQUEUR} absent de {TEMPLATE}")
    return template.replace(MARQUEUR, f"  const protocols = {blob.strip()};\n"), len(fiches)


def main():
    page, nombre = construire()
    if "--verifier" in sys.argv:
        actuel = SORTIE.read_text(encoding="utf-8") if SORTIE.exists() else None
        if actuel != page:
            raise SystemExit(
                f"{SORTIE.relative_to(RACINE)} n'est plus en phase avec "
                f"{DONNEES.relative_to(RACINE)} — relancer le build.")
        print(f"À jour : {nombre} fiches.")
        return
    SORTIE.write_text(page, encoding="utf-8")
    print(f"{SORTIE.relative_to(RACINE)} généré : {nombre} fiches.")


if __name__ == "__main__":
    main()
