"""
pptx_builder.py
===============
Génération automatique d'un PowerPoint 16:9 depuis une fiche pédagogique
Markdown, avec un design calé sur le template Xpermanip fourni.

Design system (extrait du template templates/template.pptx) :
    - Couleur principale : Rouge #BF0000
    - Accent orange      : #E67E22  (slide terrain)
    - Accent bleu        : #2980B9  (slide quiz)
    - Accent vert        : #27AE60  (corrections)
    - Fond clair         : #F5F5F5 / blanc alterné
    - Header             : bandeau pleine largeur, 1.10" de haut
    - Footer             : barre rouge fine à y=7.18"
    - Lignes zébrées     : badge numéroté carré + texte
    - Cartes contenu     : fond #F5F5F5 + barre colorée gauche 0.20"

Structure des slides :
    Slide 1  — Titre (split gauche rouge / droite blanc)
    Slide 2  — Objectif pédagogique (grande carte)
    Slide 3  — Notions clés (lignes zébrées, image droit si dispo)
    Slide 4+ — Explication structurée (1 slide par ### sous-section)
    Slide N  — Point terrain MERM (orange, 2 colonnes)
    Slide N+1— Erreurs fréquentes (paires ❌/✅ en lignes zébrées)
    Slide N+2— Mini quiz (lignes alternées bleu/blanc)
    Slide N+3— Résumé final (lignes zébrées, image droit si dispo)
    Slide fin— Clôture Xpermanip (fond rouge sombre)

Usage :
    from pipeline.pptx_builder import build_pptx

    pptx_path = build_pptx(
        fiche_md="...",
        theme="irm_feminin",
        specialty="irm",
        images={"anatomie": Path("..."), "protocole": Path("..."), "resume": Path("...")}
    )
"""

import re
from datetime import date
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

PPTX_DIR     = Path(__file__).resolve().parent.parent / "outputs" / "pptx"
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "template.pptx"

# ---------------------------------------------------------------------------
# Palette de couleurs (calée sur le template fourni)
# ---------------------------------------------------------------------------

C = {
    "primary":      RGBColor(0xBF, 0x00, 0x00),   # Rouge principal
    "primary_dark": RGBColor(0xA5, 0x00, 0x00),   # Rouge sombre (closing)
    "orange":       RGBColor(0xE6, 0x7E, 0x22),   # Orange (terrain MERM)
    "blue":         RGBColor(0x29, 0x80, 0xB9),   # Bleu (quiz)
    "green":        RGBColor(0x27, 0xAE, 0x60),   # Vert (corrections)
    "navy":         RGBColor(0x2C, 0x3E, 0x50),   # Marine (badges neutres)
    "bg_light":     RGBColor(0xF5, 0xF5, 0xF5),   # Fond gris clair
    "bg_orange":    RGBColor(0xFF, 0xF3, 0xE0),   # Fond orange pâle
    "white":        RGBColor(0xFF, 0xFF, 0xFF),
    "text":         RGBColor(0x1A, 0x1A, 0x1A),
    "text_muted":   RGBColor(0x55, 0x55, 0x55),
    "light_pink":   RGBColor(0xFF, 0xCC, 0xCC),   # Texte léger sur rouge
    "light_pink2":  RGBColor(0xFF, 0xD0, 0xD0),   # Texte réponse quiz
    "light_orange": RGBColor(0xFF, 0xE0, 0xB2),   # Texte léger sur orange
}

# Taille 16:9
SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.50)

# Zones fixes (en pouces)
HEADER_H    = 1.10   # Hauteur du bandeau titre
FOOTER_Y    = 7.18   # Début du pied de page
FOOTER_H    = 0.32   # Hauteur du pied de page
CONTENT_TOP = 1.20   # Début de la zone de contenu
CONTENT_H   = FOOTER_Y - CONTENT_TOP   # ~5.98" disponibles
ROW_H       = 0.56   # Hauteur d'une ligne zébrée


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def build_pptx(
    fiche_md: str,
    theme: str,
    specialty: str,
    images: dict[str, Path] | None = None,
) -> Path:
    """
    Génère le fichier PowerPoint complet avec le design Xpermanip.

    Args:
        fiche_md:  Contenu Markdown de la fiche pédagogique.
        theme:     Nom du thème (ex: "irm_feminin").
        specialty: Nom de la spécialité (ex: "irm").
        images:    Dict optionnel {"anatomie": Path, "protocole": Path, "resume": Path}.

    Returns:
        Path: chemin vers le .pptx généré.
    """
    if images is None:
        images = {}

    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H

    sections    = _extract_sections(fiche_md)
    theme_label = theme.replace("_", " ").title()
    footer_text = f"Xpermanip Content Engine  ·  {specialty.upper()} — {theme_label}"

    # Construction des slides
    _slide_title(prs, sections, theme_label, specialty)
    _slide_objectif(prs, sections, footer_text)
    _slide_notions(prs, sections, images.get("anatomie"), footer_text)
    _slides_explication(prs, sections, images.get("protocole"), footer_text)
    _slide_terrain(prs, sections, footer_text)
    _slide_erreurs(prs, sections, footer_text)
    _slide_quiz(prs, sections, footer_text)
    _slide_resume(prs, sections, images.get("resume"), footer_text)
    _slide_closing(prs, specialty)

    # Sauvegarde
    out_dir = PPTX_DIR / specialty
    out_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = out_dir / f"{theme}.pptx"
    prs.save(str(pptx_path))
    return pptx_path


# ---------------------------------------------------------------------------
# Extraction des sections depuis le Markdown
# ---------------------------------------------------------------------------

def _extract_sections(fiche_md: str) -> dict[str, str]:
    """Extrait chaque section nommée depuis le Markdown de la fiche."""
    section_patterns = [
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

    for line in lines:
        m = re.match(r"^#\s+(.+)$", line)
        if m and not line.startswith("##"):
            sections["titre"] = m.group(1).strip()
            break

    current_key: str | None = None
    current_lines: list[str] = []

    for line in lines:
        matched_key = None
        for key, pattern in section_patterns[1:]:
            if re.match(pattern, line, re.IGNORECASE):
                matched_key = key
                break

        if matched_key:
            if current_key and current_lines:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = matched_key
            current_lines = []
        elif current_key and not re.match(r"^-{3,}$", line.strip()) and not line.startswith(">"):
            current_lines.append(line)

    if current_key and current_lines:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _extract_bullets(text: str, max_items: int = 20) -> list[str]:
    """Extrait les puces d'un texte Markdown."""
    bullets = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[-*•]\s+", stripped):
            item = re.sub(r"^[-*•]\s+", "", stripped)
            item = re.sub(r"\*\*(.*?)\*\*", r"\1", item)
            bullets.append(item)
        if len(bullets) >= max_items:
            break
    return bullets


def _extract_subsections(text: str) -> list[tuple[str, str]]:
    """
    Extrait les sous-sections H3 (### Titre) avec leur contenu.
    Retourne [(titre, contenu), ...]
    """
    subsections = []
    current_title = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        m = re.match(r"^###\s+(.+)$", line.strip())
        if m:
            if current_title:
                subsections.append((current_title, "\n".join(current_lines).strip()))
            current_title = m.group(1).strip()
            current_lines = []
        elif current_title:
            current_lines.append(line)

    if current_title:
        subsections.append((current_title, "\n".join(current_lines).strip()))

    return subsections


# ---------------------------------------------------------------------------
# Helpers de base
# ---------------------------------------------------------------------------

def _blank_slide(prs: Presentation) -> object:
    """Ajoute un slide vierge (layout blank)."""
    return prs.slides.add_slide(prs.slide_layouts[6])


def _fill_bg(slide, color: RGBColor) -> None:
    """Remplit le fond du slide avec une couleur unie."""
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_rect(
    slide,
    left: float, top: float, width: float, height: float,
    fill_color: RGBColor,
    no_line: bool = True,
) -> object:
    """Ajoute un rectangle coloré (coordonnées en pouces)."""
    shape = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Inches(left), Inches(top), Inches(width), Inches(height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if no_line:
        shape.line.fill.background()
    return shape


def _add_textbox(
    slide,
    left: float, top: float, width: float, height: float,
    text: str,
    font_size: int = 16,
    bold: bool = False,
    italic: bool = False,
    color: RGBColor | None = None,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    wrap: bool = True,
) -> object:
    """Ajoute un textbox simple (coordonnées en pouces)."""
    txBox = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = txBox.text_frame
    tf.word_wrap = wrap
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color
    return txBox


# ---------------------------------------------------------------------------
# Helpers de mise en page (design template)
# ---------------------------------------------------------------------------

def _add_header(slide, title: str, color: RGBColor | None = None) -> None:
    """
    Bandeau titre pleine largeur (style template) + texte Xpermanip top-right.
    """
    color = color or C["primary"]
    # Bandeau coloré
    _add_rect(slide, 0, 0, 13.33, HEADER_H, color)
    # Titre
    _add_textbox(
        slide, 0.50, 0.00, 10.50, HEADER_H,
        title, font_size=28, bold=True, color=C["white"],
    )
    # Logo texte top-right (position calée sur le template : 11.60", 0.22")
    _add_textbox(
        slide, 11.20, 0.13, 1.95, 0.50,
        "Xpermanip", font_size=11, bold=True,
        color=C["white"], align=PP_ALIGN.RIGHT,
    )


def _add_footer(slide, text_left: str = "") -> None:
    """Barre de pied de page rouge fin (style template, y=7.18")."""
    _add_rect(slide, 0, FOOTER_Y, 13.33, FOOTER_H, C["primary"])
    if text_left:
        _add_textbox(
            slide, 0.40, FOOTER_Y + 0.01, 12.53, FOOTER_H - 0.02,
            text_left, font_size=9, color=C["white"],
        )


def _add_striped_rows(
    slide,
    items: list[str],
    left: float = 0.30,
    top: float = CONTENT_TOP,
    width: float = 12.73,
    badge_color: RGBColor | None = None,
) -> None:
    """
    Affiche une liste en lignes zébrées numérotées (style template slide 4).
    Badge carré coloré à gauche + texte à droite.
    Max 10 items.
    """
    badge_color = badge_color or C["primary"]
    badge_w = 0.55

    for i, item in enumerate(items[:10]):
        y = top + i * ROW_H
        fill = C["bg_light"] if i % 2 == 0 else C["white"]
        # Ligne alternée
        _add_rect(slide, left, y, width, ROW_H - 0.01, fill)
        # Badge numéroté
        _add_rect(slide, left, y, badge_w, ROW_H - 0.01, badge_color)
        _add_textbox(
            slide, left, y, badge_w, ROW_H - 0.01,
            f"{i + 1:02d}", font_size=11, bold=True,
            color=C["white"], align=PP_ALIGN.CENTER,
        )
        # Texte de la ligne (tronqué si trop long)
        clean = re.sub(r"\*\*(.*?)\*\*", r"\1", item)
        clean = re.sub(r"`(.*?)`", r"\1", clean)
        _add_textbox(
            slide, left + badge_w + 0.08, y + 0.06,
            width - badge_w - 0.12, ROW_H - 0.12,
            clean[:130], font_size=12, color=C["text"],
        )


def _add_content_card(
    slide,
    left: float, top: float, width: float, height: float,
    bar_color: RGBColor | None = None,
) -> None:
    """
    Fond de carte avec fine barre colorée à gauche (style template slides 6/7/8).
    """
    bar_color = bar_color or C["primary"]
    _add_rect(slide, left, top, width, height, C["white"])
    _add_rect(slide, left, top, 0.20, height, bar_color)


def _add_bullet_list(
    slide,
    bullets: list[str],
    left: float, top: float, width: float, height: float,
    font_size: int = 15,
    bullet_char: str = "▸",
    text_color: RGBColor | None = None,
) -> None:
    """Ajoute une liste à puces formatée."""
    if not bullets:
        return
    text_color = text_color or C["text"]

    txBox = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, bullet in enumerate(bullets):
        clean = re.sub(r"\*\*(.*?)\*\*", r"\1", bullet)
        clean = re.sub(r"`(.*?)`", r"\1", clean)

        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(4)
        run = p.add_run()
        run.text = f"{bullet_char}  {clean}"
        run.font.size = Pt(font_size)
        run.font.color.rgb = text_color


def _add_image_fitted(
    slide,
    img_path: Path,
    left: float, top: float, width: float, height: float,
) -> None:
    """Insère une image dans une zone donnée (coordonnées en pouces)."""
    try:
        slide.shapes.add_picture(
            str(img_path),
            Inches(left), Inches(top), Inches(width), Inches(height),
        )
    except Exception as exc:
        print(f"  [PPTX] ⚠ Image non insérée ({img_path.name}) : {exc}")


# ---------------------------------------------------------------------------
# Construction des slides
# ---------------------------------------------------------------------------

def _slide_title(
    prs: Presentation,
    sections: dict,
    theme_label: str,
    specialty: str,
) -> None:
    """
    Slide 1 — Page de titre.
    Layout split : panneau gauche rouge (titre) / panneau droit blanc (infos).
    (Calé sur le slide 1 du template fourni.)
    """
    slide = _blank_slide(prs)
    _fill_bg(slide, C["primary"])

    # Panneau droit blanc
    _add_rect(slide, 6.50, 0.01, 6.83, 7.49, C["white"])

    titre = sections.get("titre", theme_label)

    # ── Contenu panneau gauche ──────────────────────────────────────────────
    # Étiquette spécialité (rose clair)
    _add_textbox(
        slide, 0.55, 1.40, 5.70, 0.60,
        f"{specialty.upper()}  ·  Fiche pédagogique MERM",
        font_size=16, color=C["light_pink"],
    )
    # Titre principal (grand, blanc)
    txBox = slide.shapes.add_textbox(
        Inches(0.55), Inches(2.10), Inches(5.70), Inches(2.50)
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = titre
    run.font.size = Pt(38)
    run.font.bold = True
    run.font.color.rgb = C["white"]

    # Date générée
    _add_textbox(
        slide, 0.55, 4.80, 5.70, 0.55,
        date.today().strftime("%d/%m/%Y"),
        font_size=18, color=C["light_pink"],
    )
    # Signature bas-gauche
    _add_textbox(
        slide, 0.55, 6.78, 5.50, 0.38,
        "VOTRE PARTENAIRE EN FORMATION CONTINUE",
        font_size=9, color=RGBColor(0xFF, 0xAA, 0xAA),
    )

    # ── Contenu panneau droit ───────────────────────────────────────────────
    # Label "Formation continue MERM" en rouge
    _add_textbox(
        slide, 6.80, 1.50, 6.20, 0.45,
        "Formation continue MERM",
        font_size=15, bold=True, color=C["primary"],
    )
    # Lignes d'info alternées (style template slide 1)
    row_items = [
        f"📚  Spécialité : {specialty.upper()}",
        f"🏷  Thème : {theme_label}",
        "👨‍⚕️  Niveau : Étudiant MERM",
        "⚠️  À valider avant publication",
        f"📅  Généré le {date.today().strftime('%d/%m/%Y')}",
    ]
    for i, label in enumerate(row_items):
        y = 2.10 + i * 0.68
        fill = C["bg_light"] if i % 2 == 0 else C["white"]
        _add_rect(slide, 6.80, y, 5.90, 0.66, fill)
        _add_textbox(slide, 6.95, y + 0.05, 5.70, 0.56, label, font_size=13, color=C["text"])

    # Branding top-right (sur le panneau blanc)
    _add_textbox(
        slide, 9.20, 0.22, 3.80, 0.60,
        "Xpermanip Engine",
        font_size=13, bold=True, color=C["primary"], align=PP_ALIGN.RIGHT,
    )


def _slide_objectif(prs: Presentation, sections: dict, footer_text: str) -> None:
    """Slide 2 — Objectif pédagogique (grande carte avec barre rouge)."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["bg_light"])
    _add_header(slide, "🎯  Objectif pédagogique", C["primary"])
    _add_footer(slide, footer_text)

    text = sections.get("objectif", "")
    text_clean = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text_clean = re.sub(r"`(.*?)`", r"\1", text_clean)

    # Grande carte blanc avec barre rouge gauche
    card_h = CONTENT_H - 0.20
    _add_content_card(slide, 0.40, CONTENT_TOP, 12.53, card_h, C["primary"])
    _add_textbox(
        slide, 0.75, CONTENT_TOP + 0.20, 12.10, card_h - 0.40,
        text_clean, font_size=17, color=C["text"],
    )


def _slide_notions(
    prs: Presentation,
    sections: dict,
    img_path: Path | None,
    footer_text: str,
) -> None:
    """Slide 3 — Notions clés (lignes zébrées + schéma anatomie si dispo)."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["white"])
    _add_header(slide, "🔑  Notions clés", C["primary"])
    _add_footer(slide, footer_text)

    bullets   = _extract_bullets(sections.get("notions_cles", ""), max_items=10)
    has_image = img_path and img_path.exists()
    row_width = 6.00 if has_image else 12.73

    _add_striped_rows(slide, bullets, left=0.30, top=CONTENT_TOP, width=row_width)

    if has_image:
        _add_image_fitted(slide, img_path, 6.50, CONTENT_TOP, 6.50, CONTENT_H - 0.10)


def _slides_explication(
    prs: Presentation,
    sections: dict,
    img_path: Path | None,
    footer_text: str,
) -> None:
    """Slides explication structurée — 1 slide par sous-section H3."""
    text        = sections.get("explication", "")
    subsections = _extract_subsections(text)

    if not subsections:
        slide = _blank_slide(prs)
        _fill_bg(slide, C["bg_light"])
        _add_header(slide, "📖  Explication structurée", C["primary"])
        _add_footer(slide, footer_text)
        bullets = _extract_bullets(text, max_items=8)
        _add_content_card(slide, 0.40, CONTENT_TOP, 12.53, CONTENT_H - 0.15, C["primary"])
        _add_bullet_list(slide, bullets, 0.75, CONTENT_TOP + 0.15, 12.10, CONTENT_H - 0.35)
        return

    for i, (sub_title, sub_content) in enumerate(subsections):
        slide = _blank_slide(prs)
        _fill_bg(slide, C["bg_light"])
        _add_header(slide, f"📖  {sub_title}", C["primary"])
        _add_footer(slide, footer_text)

        is_last   = (i == len(subsections) - 1)
        has_image = img_path and img_path.exists() and is_last
        col_w     = 6.00 if has_image else 12.53

        # Carte contenu avec barre rouge gauche
        _add_content_card(slide, 0.40, CONTENT_TOP, col_w, CONTENT_H - 0.15, C["primary"])

        bullets = _extract_bullets(sub_content, max_items=8)
        if bullets:
            _add_bullet_list(
                slide, bullets,
                0.75, CONTENT_TOP + 0.15, col_w - 0.40, CONTENT_H - 0.35,
                font_size=15,
            )
        else:
            text_clean = re.sub(r"\*\*(.*?)\*\*", r"\1", sub_content)
            text_clean = re.sub(r"^#+\s+", "", text_clean, flags=re.MULTILINE)
            _add_textbox(
                slide, 0.75, CONTENT_TOP + 0.15, col_w - 0.40, CONTENT_H - 0.35,
                text_clean[:900], font_size=14, color=C["text"],
            )

        if has_image:
            _add_image_fitted(slide, img_path, 6.55, CONTENT_TOP, 6.45, CONTENT_H - 0.15)


def _slide_terrain(prs: Presentation, sections: dict, footer_text: str) -> None:
    """Slide Point terrain MERM (orange, 2 colonnes si ≥ 7 items)."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["bg_orange"])
    _add_header(slide, "🏥  Point terrain manipulateur", C["orange"])
    _add_footer(slide, footer_text)

    bullets = _extract_bullets(sections.get("point_terrain", ""), max_items=12)

    if len(bullets) > 6:
        mid = len(bullets) // 2
        left_bullets  = bullets[:mid]
        right_bullets = bullets[mid:]

        # Colonne gauche
        _add_content_card(slide, 0.30, CONTENT_TOP, 6.20, CONTENT_H - 0.10, C["orange"])
        _add_bullet_list(
            slide, left_bullets,
            0.65, CONTENT_TOP + 0.15, 5.75, CONTENT_H - 0.35,
            font_size=14, bullet_char="→", text_color=C["text"],
        )
        # Colonne droite
        _add_content_card(slide, 6.80, CONTENT_TOP, 6.20, CONTENT_H - 0.10, C["orange"])
        _add_bullet_list(
            slide, right_bullets,
            7.15, CONTENT_TOP + 0.15, 5.75, CONTENT_H - 0.35,
            font_size=14, bullet_char="→", text_color=C["text"],
        )
    else:
        _add_content_card(slide, 0.40, CONTENT_TOP, 12.53, CONTENT_H - 0.10, C["orange"])
        _add_bullet_list(
            slide, bullets,
            0.75, CONTENT_TOP + 0.15, 12.10, CONTENT_H - 0.35,
            font_size=15, bullet_char="→", text_color=C["text"],
        )


def _slide_erreurs(prs: Presentation, sections: dict, footer_text: str) -> None:
    """Slide Erreurs fréquentes (paires ❌/✅ en lignes zébrées)."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["bg_light"])
    _add_header(slide, "⚠️  Erreurs fréquentes", C["primary"])
    _add_footer(slide, footer_text)

    text         = sections.get("erreurs", "")
    error_blocks = _parse_error_blocks(text)

    if error_blocks:
        card_h = 0.88
        for i, (err, fix) in enumerate(error_blocks[:6]):
            y    = CONTENT_TOP + i * (card_h + 0.05)
            fill = C["bg_light"] if i % 2 == 0 else C["white"]
            _add_rect(slide, 0.30, y, 12.73, card_h, fill)
            _add_rect(slide, 0.30, y, 0.20, card_h, C["primary"])
            # Ligne erreur
            _add_textbox(
                slide, 0.60, y + 0.08, 12.00, 0.38,
                f"❌  {err[:120]}", font_size=13, bold=True, color=C["primary"],
            )
            if fix:
                _add_textbox(
                    slide, 0.60, y + 0.46, 12.00, card_h - 0.52,
                    f"✅  {fix[:150]}", font_size=12, color=C["green"],
                )
    else:
        bullets = _extract_bullets(text, max_items=8)
        _add_content_card(slide, 0.40, CONTENT_TOP, 12.53, CONTENT_H - 0.10, C["primary"])
        _add_bullet_list(
            slide, bullets,
            0.75, CONTENT_TOP + 0.15, 12.10, CONTENT_H - 0.35,
            font_size=15, text_color=C["primary"],
        )


def _slide_quiz(prs: Presentation, sections: dict, footer_text: str) -> None:
    """Slides Mini quiz (lignes alternées bleues, 2 slides si > 4 questions)."""
    text     = sections.get("quiz", "")
    qa_pairs = _parse_quiz(text)

    chunks = [qa_pairs[:4], qa_pairs[4:8]] if len(qa_pairs) > 4 else [qa_pairs]

    for chunk_idx, chunk in enumerate(chunks):
        if not chunk:
            continue

        slide = _blank_slide(prs)
        _fill_bg(slide, C["white"])
        title = "❓  Mini quiz" if chunk_idx == 0 else "❓  Mini quiz (suite)"
        _add_header(slide, title, C["blue"])
        _add_footer(slide, footer_text)

        # Hauteur de bloc adaptative
        block_h = min((CONTENT_H - 0.10) / max(len(chunk), 1) - 0.05, 1.35)

        for j, (question, reponse) in enumerate(chunk):
            num  = j + 1 + chunk_idx * 4
            y    = CONTENT_TOP + j * (block_h + 0.05)
            fill = C["bg_light"] if j % 2 == 0 else C["white"]

            # Ligne de fond
            _add_rect(slide, 0.30, y, 12.73, block_h, fill)
            # Badge bleu (numéro de question)
            _add_rect(slide, 0.30, y, 0.55, block_h, C["blue"])
            _add_textbox(
                slide, 0.30, y, 0.55, block_h,
                f"Q{num}", font_size=12, bold=True,
                color=C["white"], align=PP_ALIGN.CENTER,
            )
            # Question
            _add_textbox(
                slide, 0.95, y + 0.06, 12.00, 0.42,
                question[:120], font_size=13, bold=True, color=C["text"],
            )
            # Réponse
            if reponse:
                _add_textbox(
                    slide, 0.95, y + 0.48, 12.00, block_h - 0.52,
                    f"▸ {reponse[:200]}", font_size=12, color=C["text_muted"],
                )


def _slide_resume(
    prs: Presentation,
    sections: dict,
    img_path: Path | None,
    footer_text: str,
) -> None:
    """Slide Résumé final (lignes zébrées + schéma résumé si dispo)."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["white"])
    _add_header(slide, "📝  Résumé final", C["primary"])
    _add_footer(slide, footer_text)

    bullets   = _extract_bullets(sections.get("resume", ""), max_items=8)
    has_image = img_path and img_path.exists()
    row_width = 6.00 if has_image else 12.73

    _add_striped_rows(slide, bullets, left=0.30, top=CONTENT_TOP, width=row_width, badge_color=C["navy"])

    if has_image:
        _add_image_fitted(slide, img_path, 6.50, CONTENT_TOP, 6.50, CONTENT_H - 0.10)


def _slide_closing(prs: Presentation, specialty: str) -> None:
    """Slide de clôture (fond rouge sombre, texte blanc centré)."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["primary_dark"])

    _add_textbox(
        slide, 0, 2.80, 13.33, 1.20,
        "Xpermanip Content Engine",
        font_size=36, bold=True, color=C["white"], align=PP_ALIGN.CENTER,
    )
    _add_textbox(
        slide, 0, 4.10, 13.33, 0.60,
        f"{specialty.upper()}  ·  ⚠ Fiche à valider avant publication",
        font_size=17, color=C["light_pink"], align=PP_ALIGN.CENTER,
    )
    _add_textbox(
        slide, 0, 6.78, 13.33, 0.38,
        "Formation continue MERM — Xpermanip",
        font_size=10, color=RGBColor(0xFF, 0xAA, 0xAA), align=PP_ALIGN.CENTER,
    )


# ---------------------------------------------------------------------------
# Parsers spécifiques
# ---------------------------------------------------------------------------

def _parse_error_blocks(text: str) -> list[tuple[str, str]]:
    """
    Parse les blocs ❌ Erreur / ✅ Correction.
    Retourne [(erreur, correction), ...]
    """
    blocks = []
    lines = text.splitlines()
    current_err = ""
    current_fix = ""

    for line in lines:
        stripped       = line.strip()
        stripped_clean = re.sub(r"\*\*(.*?)\*\*", r"\1", stripped)

        if "❌" in stripped_clean or stripped_clean.lower().startswith("erreur"):
            if current_err:
                blocks.append((current_err, current_fix))
            current_err = stripped_clean.replace("❌", "").replace("Erreur :", "").strip()
            current_err = re.sub(r"^[-*•]\s*", "", current_err).strip()
            current_fix = ""
        elif "✅" in stripped_clean or "correction" in stripped_clean.lower():
            current_fix = stripped_clean.replace("✅", "").replace("Correction :", "").strip()
            current_fix = re.sub(r"^[-*•]\s*", "", current_fix).strip()

    if current_err:
        blocks.append((current_err, current_fix))

    return blocks


def _parse_quiz(text: str) -> list[tuple[str, str]]:
    """
    Parse les paires Q/R du quiz.
    Retourne [(question, reponse), ...]
    """
    pairs = []
    lines = text.splitlines()
    current_q = ""
    current_r = ""

    for line in lines:
        stripped = line.strip()
        clean    = re.sub(r"\*\*(.*?)\*\*", r"\1", stripped)
        clean    = re.sub(r"^>+\s*", "", clean)

        q_match = re.match(r"^Q(\d+)[.)]\s*(.+)", clean, re.IGNORECASE)
        r_match = re.match(r"^R[.)]\s*(.+)|^Rép[.)]\s*(.+)", clean, re.IGNORECASE)

        if q_match:
            if current_q:
                pairs.append((current_q, current_r))
            current_q = q_match.group(2).strip()
            current_r = ""
        elif r_match:
            current_r = (r_match.group(1) or r_match.group(2) or "").strip()

    if current_q:
        pairs.append((current_q, current_r))

    return pairs
