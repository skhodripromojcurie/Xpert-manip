"""
fiche_generator.py
==================
Génération de fiches pédagogiques via l'API Groq (llama-3.3-70b-versatile).

Ce module est le cœur éditorial du pipeline. Il reçoit le texte fusionné
des sources nettoyées et demande à Groq/Llama de produire une fiche pédagogique
homogène, réécrite et structurée selon le template Xpermanip.

Le modèle ne copie PAS les sources : il synthétise, restructure et réécrit.
La fiche générée doit ensuite être validée par un humain avant publication.

Usage :
    from pipeline.fiche_generator import generate_fiche

    fiche_md = generate_fiche(
        merged_text=...,
        theme="embolie_pulmonaire",
        specialty="scanner",
        source_files=["cours_A.pdf", "slides_B.pptx"],
    )

Clé API gratuite :
    Créer un compte sur https://console.groq.com
    Puis : set GROQ_API_KEY=ta_cle   (Windows)
           export GROQ_API_KEY=ta_cle (Linux/Mac)
"""

import json
import os
import re
from datetime import date
from pathlib import Path

from groq import Groq

# ---------------------------------------------------------------------------
# Prompt système : persona pédagogique MERM
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
Tu es un expert en radiodiagnostic et en pédagogie médicale, spécialisé dans \
la formation des MERM (Manipulateurs En Électroradiologie Médicale).

Ton rôle est de créer des fiches pédagogiques synthétiques, claires et \
structurées à partir de supports de cours bruts fournis par l'utilisateur.

Règles absolues :
- NE copie PAS les phrases des sources : synthétise et réécris toujours.
- Adopte un ton pédagogique, professionnel, précis, orienté étudiant MERM.
- Respecte le format JSON demandé à la lettre (clés exactes, valeurs Markdown).
- Mets en valeur les points pratiques propres au rôle du manipulateur.
- Sois synthétique mais complet : chaque section doit apporter de la valeur.\
"""

# ---------------------------------------------------------------------------
# Template de rendu Markdown final
# ---------------------------------------------------------------------------

FICHE_TEMPLATE = """\
# {titre}

> **Spécialité :** {specialty} | **Thème :** {theme}
> **Niveau :** Étudiant MERM | **Statut :** ⚠️ À valider avant publication

---

## Objectif pédagogique

{objectif}

---

## Notions clés

{notions_cles}

---

## Explication structurée

{explication}

---

## Point terrain manipulateur

{point_terrain}

---

## Erreurs fréquentes

{erreurs}

---

## Mini quiz

{quiz}

---

## Résumé final

{resume}

---

*Fiche générée le {date} par Xpermanip Content Engine.*
*Sources utilisées : {sources}*
*⚠️ Ce document doit être relu et validé par un expert avant toute diffusion.*
"""


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def generate_fiche(
    merged_text: str,
    theme: str,
    specialty: str,
    source_files: list[str],
    *,
    verbose: bool = True,
) -> str:
    """
    Génère une fiche pédagogique Markdown via Groq (llama-3.3-70b-versatile).

    Args:
        merged_text: Texte nettoyé fusionné de toutes les sources du thème.
        theme: Nom du thème (ex: "embolie_pulmonaire").
        specialty: Nom de la spécialité (ex: "scanner").
        source_files: Liste des noms de fichiers sources (traçabilité).
        verbose: Affiche les infos de génération si True.

    Returns:
        str: Fiche pédagogique complète au format Markdown.

    Raises:
        ValueError: Clé API GROQ_API_KEY manquante ou réponse JSON malformée.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "Clé API manquante. Définis la variable d'environnement GROQ_API_KEY.\n"
            "Obtiens une clé gratuite sur : https://console.groq.com"
        )

    client = Groq(api_key=api_key)

    prompt = _build_prompt(merged_text, theme, specialty)

    if verbose:
        print(f"  [Groq] Génération de la fiche '{theme}' en cours...")

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=8000,
        temperature=0.3,
    )

    text = completion.choices[0].message.content.strip()

    if verbose:
        usage = completion.usage
        print(
            f"  [Groq] Tokens : {usage.prompt_tokens} in / "
            f"{usage.completion_tokens} out"
        )

    # Parser le JSON renvoyé par Groq
    data = _parse_json_response(text)

    return FICHE_TEMPLATE.format(
        titre=data["titre"],
        specialty=specialty,
        theme=theme.replace("_", " ").title(),
        objectif=data["objectif"],
        notions_cles=data["notions_cles"],
        explication=data["explication"],
        point_terrain=data["point_terrain"],
        erreurs=data["erreurs"],
        quiz=data["quiz"],
        resume=data["resume"],
        sources=", ".join(source_files) if source_files else "—",
        date=date.today().isoformat(),
    )


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _build_prompt(merged_text: str, theme: str, specialty: str) -> str:
    """Construit le prompt utilisateur envoyé à Groq."""
    # Tronquer si trop long (sécurité context window)
    max_chars = 120_000
    if len(merged_text) > max_chars:
        merged_text = merged_text[:max_chars] + "\n\n[... contenu tronqué ...]"

    return f"""\
Voici des extraits de cours sur le thème "{theme}" (spécialité : {specialty}).
Ces sources ont été extraites et nettoyées automatiquement.

=== SOURCES DE COURS ===
{merged_text}
=== FIN DES SOURCES ===

À partir de ces sources, génère une fiche pédagogique complète pour des \
étudiants MERM.

Réponds UNIQUEMENT avec un objet JSON valide contenant exactement ces 8 clés \
(valeurs en Markdown, pas de JSON imbriqué) :

{{
  "titre": "Titre court et professionnel de la fiche (ex: Scanner thoracique : Embolie pulmonaire)",
  "objectif": "L'objectif pédagogique en 1-2 phrases directes et mesurables",
  "notions_cles": "- Notion 1\\n- Notion 2\\n... (5 à 8 notions essentielles)",
  "explication": "Explication structurée avec sous-titres Markdown (### Physiopathologie, ### Sémiologie scanner, etc.)",
  "point_terrain": "Points pratiques propres au rôle du MERM : positionnement, injection, protocole, vigilance",
  "erreurs": "- Erreur fréquente 1\\n- Erreur fréquente 2\\n... (3 à 6 erreurs)",
  "quiz": "**Q1.** Question ?\\n> **R.** Réponse courte.\\n\\n**Q2.** ...  (3 à 5 questions)",
  "resume": "- Point clé 1\\n- Point clé 2\\n... (3 à 5 points de synthèse)"
}}

Réponds avec le JSON uniquement, sans aucun texte avant ou après.\
"""


def _parse_json_response(text: str) -> dict:
    """
    Parse la réponse JSON de Groq avec nettoyage des artefacts courants.

    Gère :
    - Blocs de code Markdown (```json ... ```)
    - Espaces/retours à la ligne parasites
    - Réponse directement JSON

    Raises:
        ValueError: Si le JSON ne peut pas être parsé.
    """
    # Supprimer les balises de bloc de code si présentes
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Tentative de récupération : extraire le premier {...} trouvé
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
            except json.JSONDecodeError:
                raise ValueError(
                    f"Impossible de parser la réponse JSON de Groq.\n"
                    f"Erreur : {exc}\n"
                    f"Début de la réponse : {text[:300]}"
                ) from exc
        else:
            raise ValueError(
                f"Aucun JSON trouvé dans la réponse Groq.\n"
                f"Début : {text[:300]}"
            ) from exc

    # Vérifier que les 8 clés obligatoires sont présentes
    required = {
        "titre", "objectif", "notions_cles", "explication",
        "point_terrain", "erreurs", "quiz", "resume",
    }
    missing = required - set(data.keys())
    if missing:
        raise ValueError(
            f"Clés manquantes dans la réponse Groq : {missing}"
        )

    return data
