"""
canva_exporter.py
=================
Export de la fiche pédagogique dans un format utilisable dans Canva.

Deux sorties sont produites dans outputs/canva/<specialty>/<theme>/ :

1. <theme>.html  — Page HTML stylée, prête à être ouverte dans un navigateur
                   et imprimée / glissée dans Canva comme image.

2. <theme>.json  — Données structurées compatibles avec le "Bulk Create"
                   de Canva (remplissage automatique de templates).

Usage :
    from pipeline.canva_exporter import export_to_canva

    path = export_to_canva(fiche_md, theme="embolie_pulmonaire", specialty="scanner")
"""

import json
import re
from pathlib import Path

ROOT       = Path(__file__).resolve().parent.parent
CANVA_DIR  = ROOT / "outputs" / "canva"

# Palette de couleurs Xpermanip (modifiable dans config.yaml à terme)
COLORS = {
    "primary":    "#1A3A5C",   # Bleu marine médical
    "accent":     "#2E86AB",   # Bleu clair
    "highlight":  "#F18F01",   # Orange (attention / terrain)
    "background": "#F5F8FB",   # Gris bleuté très clair
    "text":       "#1C1C1E",   # Quasi-noir
    "border":     "#D0DCE8",   # Gris bleuté
}


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def export_to_canva(fiche_md: str, theme: str, specialty: str) -> Path:
    """
    Génère les exports HTML et JSON Canva pour une fiche Markdown.

    Args:
        fiche_md: Contenu Markdown de la fiche (issu de fiche_generator).
        theme:    Nom du thème (ex: "embolie_pulmonaire").
        specialty: Nom de la spécialité (ex: "scanner").

    Returns:
        Path: Dossier contenant les fichiers exportés.
    """
    out_dir = CANVA_DIR / specialty
    out_dir.mkdir(parents=True, exist_ok=True)

    sections = _extract_sections(fiche_md)

    # Export 1 : HTML visuel
    html_path = out_dir / f"{theme}.html"
    html_path.write_text(_render_html(sections, theme, specialty), encoding="utf-8")

    # Export 2 : JSON Canva Bulk Create
    json_path = out_dir / f"{theme}.json"
    json_path.write_text(
        json.dumps(_render_bulk_create(sections, theme, specialty), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return out_dir


# ---------------------------------------------------------------------------
# Extraction des sections depuis le Markdown
# ---------------------------------------------------------------------------

def _extract_sections(fiche_md: str) -> dict[str, str]:
    """
    Parse le Markdown de la fiche et extrait chaque section nommée.

    Returns:
        dict: {nom_section: contenu_markdown}
    """
    # Titres des sections à extraire (ordre important)
    section_titles = [
        ("titre",         r"^#\s+(.+)$"),
        ("objectif",      r"^##\s+Objectif pédagogique"),
        ("notions_cles",  r"^##\s+Notions clés"),
        ("explication",   r"^##\s+Explication structurée"),
        ("point_terrain", r"^##\s+Point terrain manipulateur"),
        ("erreurs",       r"^##\s+Erreurs fréquentes"),
        ("quiz",          r"^##\s+Mini quiz"),
        ("resume",        r"^##\s+Résumé final"),
    ]

    sections: dict[str, str] = {}
    lines = fiche_md.splitlines()

    # Titre principal (ligne H1)
    for line in lines:
        m = re.match(r"^#\s+(.+)$", line)
        if m:
            sections["titre"] = m.group(1).strip()
            break

    # Sections H2
    current_key: str | None = None
    current_lines: list[str] = []

    for line in lines:
        matched_key = None
        for key, pattern in section_titles[1:]:  # skip titre
            if re.match(pattern, line, re.IGNORECASE):
                matched_key = key
                break

        if matched_key:
            if current_key and current_lines:
                sections[current_key] = _md_to_plain_text(
                    "\n".join(current_lines).strip()
                )
            current_key = matched_key
            current_lines = []
        elif current_key and not line.startswith("---") and not line.startswith(">"):
            current_lines.append(line)

    # Dernière section
    if current_key and current_lines:
        sections[current_key] = _md_to_plain_text("\n".join(current_lines).strip())

    return sections


def _md_to_plain_text(md: str) -> str:
    """Simplifie le Markdown en texte lisible (garde puces et structure)."""
    # Supprimer les balises Markdown mais garder la structure
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", md)   # gras
    text = re.sub(r"\*(.*?)\*",   r"\1", text)    # italique
    text = re.sub(r"`(.*?)`",     r"\1", text)    # code inline
    text = re.sub(r"^#+\s+",      "",    text, flags=re.MULTILINE)  # titres H3+
    text = re.sub(r"^>\s*",       "",    text, flags=re.MULTILINE)  # citations
    return text.strip()


# ---------------------------------------------------------------------------
# Rendu HTML
# ---------------------------------------------------------------------------

def _render_html(sections: dict[str, str], theme: str, specialty: str) -> str:
    """Génère un fichier HTML stylé, prêt à être capturé ou imprimé."""
    c = COLORS
    titre       = sections.get("titre", theme.replace("_", " ").title())
    objectif    = sections.get("objectif", "")
    notions     = sections.get("notions_cles", "")
    explication = sections.get("explication", "")
    terrain     = sections.get("point_terrain", "")
    erreurs     = sections.get("erreurs", "")
    quiz        = sections.get("quiz", "")
    resume      = sections.get("resume", "")

    def section_html(icon: str, title: str, body: str, accent_color: str = "") -> str:
        color = accent_color or c["primary"]
        body_html = _text_to_html(body)
        return f"""
        <div class="section">
          <h2 style="color:{color}; border-left:4px solid {color}; padding-left:10px;">
            {icon} {title}
          </h2>
          <div class="section-body">{body_html}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <title>Xpermanip — {titre}</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', sans-serif;
      background: {c["background"]};
      color: {c["text"]};
      padding: 40px 20px;
    }}
    .card {{
      max-width: 900px;
      margin: 0 auto;
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.08);
      overflow: hidden;
    }}
    .header {{
      background: {c["primary"]};
      color: #fff;
      padding: 36px 40px;
    }}
    .header .specialty {{
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 2px;
      opacity: 0.7;
      margin-bottom: 8px;
    }}
    .header h1 {{
      font-size: 26px;
      font-weight: 700;
      line-height: 1.3;
    }}
    .header .badge {{
      display: inline-block;
      margin-top: 12px;
      padding: 4px 12px;
      border-radius: 20px;
      background: rgba(255,255,255,0.2);
      font-size: 12px;
    }}
    .content {{ padding: 32px 40px; }}
    .section {{ margin-bottom: 28px; }}
    .section h2 {{
      font-size: 15px;
      font-weight: 700;
      margin-bottom: 10px;
      padding-bottom: 6px;
    }}
    .section-body {{
      font-size: 14px;
      line-height: 1.7;
      color: #333;
    }}
    .section-body ul {{ padding-left: 18px; }}
    .section-body li {{ margin-bottom: 4px; }}
    .section-body p {{ margin-bottom: 8px; }}
    .section-body strong {{ color: {c["primary"]}; }}
    .highlight-box {{
      background: #FFF7ED;
      border-left: 4px solid {c["highlight"]};
      border-radius: 8px;
      padding: 14px 16px;
    }}
    .quiz-block {{
      background: #F0F7FF;
      border-left: 4px solid {c["accent"]};
      border-radius: 8px;
      padding: 14px 16px;
    }}
    .footer {{
      border-top: 1px solid {c["border"]};
      padding: 16px 40px;
      font-size: 11px;
      color: #888;
      display: flex;
      justify-content: space-between;
    }}
    .warning {{ color: {c["highlight"]}; font-weight: 600; }}
    hr {{ border: none; border-top: 1px solid {c["border"]}; margin: 20px 0; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="specialty">{specialty.upper()} · Fiche pédagogique MERM</div>
      <h1>{titre}</h1>
      <span class="badge">⚠️ À valider avant publication</span>
    </div>
    <div class="content">
      {section_html("🎯", "Objectif pédagogique", objectif)}
      <hr>
      {section_html("🔑", "Notions clés", notions)}
      <hr>
      {section_html("📖", "Explication structurée", explication)}
      <hr>
      <div class="highlight-box">
        {section_html("🏥", "Point terrain manipulateur", terrain, c["highlight"])}
      </div>
      <hr>
      {section_html("⚠️", "Erreurs fréquentes", erreurs)}
      <hr>
      <div class="quiz-block">
        {section_html("❓", "Mini quiz", quiz, c["accent"])}
      </div>
      <hr>
      {section_html("📝", "Résumé final", resume)}
    </div>
    <div class="footer">
      <span>Xpermanip Content Engine — Généré automatiquement</span>
      <span class="warning">⚠️ Validation humaine requise avant diffusion</span>
    </div>
  </div>
</body>
</html>"""


def _text_to_html(text: str) -> str:
    """Convertit le texte (avec puces) en HTML basique."""
    lines = text.strip().splitlines()
    html_parts: list[str] = []
    in_list = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue

        if stripped.startswith(("- ", "* ", "• ")):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            item = stripped.lstrip("-*• ").strip()
            item = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", item)
            html_parts.append(f"<li>{item}</li>")
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            para = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", stripped)
            html_parts.append(f"<p>{para}</p>")

    if in_list:
        html_parts.append("</ul>")

    return "\n".join(html_parts)


# ---------------------------------------------------------------------------
# Rendu JSON Canva Bulk Create
# ---------------------------------------------------------------------------

def _render_bulk_create(
    sections: dict[str, str], theme: str, specialty: str
) -> dict:
    """
    Génère la structure JSON pour le Bulk Create de Canva.

    Format : tableau de données avec des clés correspondant aux
    champs d'un template Canva (à créer manuellement dans Canva).

    Doc Canva Bulk Create : https://www.canva.com/help/bulk-create/
    """
    from datetime import date

    return {
        "canva_bulk_create": {
            "version": "1.0",
            "template_hint": (
                "Créer un template Canva avec les champs de données "
                "correspondant aux clés ci-dessous, puis importer ce JSON "
                "via Apps > Bulk Create."
            ),
            "data": [
                {
                    "TITRE":          sections.get("titre", theme),
                    "SPECIALITE":     specialty.upper(),
                    "OBJECTIF":       sections.get("objectif", ""),
                    "NOTIONS_CLES":   sections.get("notions_cles", ""),
                    "EXPLICATION":    sections.get("explication", "")[:500] + "…",
                    "TERRAIN":        sections.get("point_terrain", ""),
                    "ERREURS":        sections.get("erreurs", ""),
                    "QUIZ":           sections.get("quiz", ""),
                    "RESUME":         sections.get("resume", ""),
                    "DATE":           date.today().isoformat(),
                    "VALIDATION":     "⚠️ À valider avant publication",
                }
            ],
        }
    }
