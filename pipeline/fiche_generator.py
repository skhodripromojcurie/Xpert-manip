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
Tu es un expert senior en radiodiagnostic et en pédagogie médicale, spécialisé \
dans la formation des MERM (Manipulateurs En Électroradiologie Médicale).

Ton rôle est de créer des fiches pédagogiques COMPLÈTES, RICHES et STRUCTURÉES \
à partir de supports de cours bruts fournis par l'utilisateur.

Règles absolues :
- NE copie PAS les phrases des sources : synthétise, développe et réécris toujours.
- Adopte un ton pédagogique, professionnel, précis, orienté étudiant MERM.
- Respecte le format JSON demandé à la lettre (clés exactes, valeurs Markdown).
- Mets EN VALEUR les points pratiques propres au rôle du manipulateur.
- Chaque section doit être DÉVELOPPÉE et APPROFONDIE : pas de résumé superficiel.
- Les étudiants doivent pouvoir réviser UNIQUEMENT avec ta fiche, sans les sources originales.
- Utilise des sous-titres (###), des tableaux Markdown, des exemples concrets.
- Pour chaque erreur : explique la CAUSE et la CORRECTION.
- Pour chaque notion : explique le POURQUOI, pas seulement le QUOI.\
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
        max_tokens=16000,
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

À partir de ces sources, génère une fiche pédagogique COMPLÈTE et DÉTAILLÉE \
pour des étudiants MERM. La fiche doit être suffisamment riche pour permettre \
une révision complète sans recourir aux sources originales.

EXIGENCES DE LONGUEUR ET DE CONTENU PAR SECTION :

1. "titre" : Titre professionnel précis (ex: "IRM Pelvienne Féminine : Anatomie, Protocoles et Sémiologie")

2. "objectif" : 3 à 4 phrases directes et mesurables couvrant les compétences \
théoriques ET pratiques visées.

3. "notions_cles" : 12 à 15 notions essentielles. Pour chaque notion : \
une ligne de titre en gras (**Notion**) suivie d'1 à 2 phrases d'explication \
du POURQUOI et du COMMENT. Utilise des sous-groupes (### Anatomie, \
### Physique IRM, ### Protocole, etc.).

4. "explication" : Développement structuré en MINIMUM 5 sous-sections (### Titre). \
Chaque sous-section doit contenir 2 à 4 paragraphes avec exemples concrets, \
valeurs numériques, paramètres techniques, éléments de sémiologie. \
Utilise des tableaux Markdown quand pertinent (protocoles, séquences, \
paramètres). Minimum 800 mots.

5. "point_terrain" : 10 à 14 points pratiques CONCRETS du rôle MERM. \
Format : **Point** suivi du détail (préparation patient, protocole injection, \
positionnement, antennes, séquences à adapter, communications équipe, \
vigilance effets secondaires, gestion artefacts). \
Chaque point doit répondre à "que fait le MERM concrètement et POURQUOI".

6. "erreurs" : 6 à 8 erreurs fréquentes. Pour chaque erreur : \
❌ **Erreur** : description → ✅ **Correction** : solution précise. \
Inclure les causes et conséquences cliniques éventuelles.

7. "quiz" : 6 à 8 questions progressives (des plus simples aux plus complexes). \
**Q1.** Question ?\\n> **R.** Réponse développée en 3 à 5 phrases avec justification. \
Couvrir : anatomie, physique, protocole, sémiologie, cas cliniques.

8. "resume" : 6 à 8 points de synthèse essentiels à retenir pour l'examen \
et pour la pratique professionnelle.

Réponds UNIQUEMENT avec un objet JSON valide contenant exactement ces 8 clés \
(valeurs en Markdown, pas de JSON imbriqué) :

{{
  "titre": "...",
  "objectif": "...",
  "notions_cles": "...",
  "explication": "...",
  "point_terrain": "...",
  "erreurs": "...",
  "quiz": "...",
  "resume": "..."
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
