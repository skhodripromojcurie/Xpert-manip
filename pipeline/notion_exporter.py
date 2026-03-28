"""
notion_exporter.py
==================
Export de la fiche pédagogique vers une base Notion.

Prérequis :
    1. Créer une intégration Notion sur https://www.notion.so/my-integrations
    2. Partager la base de données cible avec l'intégration
    3. Définir les variables d'environnement :
           NOTION_TOKEN       = secret_xxx...
           NOTION_DATABASE_ID = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

    pip install notion-client

La fiche est publiée en statut "Brouillon — À valider".
Elle ne doit PAS être publiée/partagée avant validation humaine.

Usage :
    from pipeline.notion_exporter import export_to_notion

    url = export_to_notion(fiche_md, theme="embolie_pulmonaire", specialty="scanner")
    # Retourne l'URL Notion de la page créée, ou None si non configuré.
"""

import os
import re
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers de conversion Markdown → blocs Notion
# ---------------------------------------------------------------------------

def _md_to_notion_blocks(md: str) -> list[dict]:
    """
    Convertit un texte Markdown en liste de blocs Notion API.

    Supporte :
    - Titres H2 (heading_2), H3 (heading_3)
    - Paragraphes
    - Listes à puces (bulleted_list_item)
    - Séparateurs (---  → divider)
    - Citations (> ... → quote)
    """
    blocks: list[dict] = []
    lines = md.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Séparateur
        if re.match(r"^-{3,}$", stripped):
            blocks.append({"object": "block", "type": "divider", "divider": {}})

        # Titre H1 → heading_1
        elif stripped.startswith("# ") and not stripped.startswith("## "):
            blocks.append(_heading(1, stripped[2:].strip()))

        # Titre H2 → heading_2
        elif stripped.startswith("## "):
            blocks.append(_heading(2, stripped[3:].strip()))

        # Titre H3 → heading_3
        elif stripped.startswith("### "):
            blocks.append(_heading(3, stripped[4:].strip()))

        # Citation (> ...)
        elif stripped.startswith("> "):
            blocks.append(_quote(stripped[2:].strip()))

        # Liste à puces
        elif re.match(r"^[-*•]\s+", stripped):
            content = re.sub(r"^[-*•]\s+", "", stripped)
            blocks.append(_bullet(content))

        # Paragraphe standard
        else:
            blocks.append(_paragraph(stripped))

        i += 1

    return blocks


def _rich_text(text: str) -> list[dict]:
    """Convertit une chaîne en rich_text Notion avec support gras/italique."""
    parts: list[dict] = []
    # Découper sur le gras (**...**)
    tokens = re.split(r"(\*\*.*?\*\*)", text)
    for token in tokens:
        if token.startswith("**") and token.endswith("**"):
            parts.append({
                "type": "text",
                "text": {"content": token[2:-2]},
                "annotations": {"bold": True},
            })
        elif token:
            parts.append({"type": "text", "text": {"content": token}})
    return parts or [{"type": "text", "text": {"content": text}}]


def _heading(level: int, text: str) -> dict:
    t = f"heading_{level}"
    return {"object": "block", "type": t, t: {"rich_text": _rich_text(text)}}


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": _rich_text(text)},
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": _rich_text(text)},
    }


def _quote(text: str) -> dict:
    return {
        "object": "block",
        "type": "quote",
        "quote": {"rich_text": _rich_text(text)},
    }


def _callout(text: str, emoji: str = "⚠️") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": _rich_text(text),
            "icon": {"type": "emoji", "emoji": emoji},
            "color": "yellow_background",
        },
    }


# ---------------------------------------------------------------------------
# Export principal
# ---------------------------------------------------------------------------

def export_to_notion(
    fiche_md: str,
    theme: str,
    specialty: str,
) -> str | None:
    """
    Crée une page Notion dans la base de données configurée.

    La page est créée en statut "Brouillon — À valider".
    Elle doit être relue et validée manuellement avant diffusion.

    Args:
        fiche_md:  Contenu Markdown de la fiche.
        theme:     Nom du thème (ex: "embolie_pulmonaire").
        specialty: Nom de la spécialité (ex: "scanner").

    Returns:
        str: URL de la page Notion créée, ou None si non configuré.
    """
    token    = os.getenv("NOTION_TOKEN")
    db_id    = os.getenv("NOTION_DATABASE_ID")

    if not token or not db_id:
        print(
            "  [Notion] Variables d'environnement manquantes.\n"
            "  Définir NOTION_TOKEN et NOTION_DATABASE_ID pour activer l'export."
        )
        return None

    try:
        from notion_client import Client
    except ImportError:
        print("  [Notion] notion-client requis : pip install notion-client")
        return None

    notion = Client(auth=token)

    # Titre de la page : "Scanner — Embolie pulmonaire"
    titre = f"{specialty.title()} — {theme.replace('_', ' ').title()}"

    # Blocs de contenu
    blocks = [
        _callout("⚠️ Ce document est un brouillon généré automatiquement. Valider avant publication."),
    ]
    blocks += _md_to_notion_blocks(fiche_md)

    # Propriétés de la page dans la base Notion
    # Adapter les noms selon la structure de votre base de données
    properties: dict = {
        "Name": {
            "title": [{"type": "text", "text": {"content": titre}}]
        },
    }

    # Propriétés optionnelles (à adapter selon votre base Notion)
    _add_optional_property(properties, "Spécialité", "select", specialty.title())
    _add_optional_property(properties, "Thème",      "rich_text", theme.replace("_", " "))
    _add_optional_property(properties, "Statut",     "select", "Brouillon — À valider")
    _add_optional_property(properties, "Date",       "date", date.today().isoformat())

    try:
        response = notion.pages.create(
            parent={"database_id": db_id},
            properties=properties,
            children=blocks[:100],  # Notion limite à 100 blocs par requête
        )
        page_url: str = response.get("url", "")
        page_id: str  = response.get("id", "")

        # Si la fiche dépasse 100 blocs, ajouter le reste en patchs successifs
        if len(blocks) > 100:
            for chunk_start in range(100, len(blocks), 100):
                notion.blocks.children.append(
                    block_id=page_id,
                    children=blocks[chunk_start:chunk_start + 100],
                )

        return page_url

    except Exception as exc:
        print(f"  [Notion] Erreur lors de la création de la page : {exc}")
        return None


def _add_optional_property(
    props: dict, name: str, prop_type: str, value: str
) -> None:
    """
    Ajoute une propriété Notion si le type est supporté.
    Ne lève pas d'exception si la propriété n'existe pas dans la base.
    """
    if prop_type == "select":
        props[name] = {"select": {"name": value}}
    elif prop_type == "rich_text":
        props[name] = {"rich_text": [{"type": "text", "text": {"content": value}}]}
    elif prop_type == "date":
        props[name] = {"date": {"start": value}}
