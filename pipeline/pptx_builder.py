"""
pptx_builder.py
===============
Génération automatique d'un PowerPoint professionnel 16:9 depuis une fiche
pédagogique Markdown, avec intégration des schémas médicaux générés par IA.

Structure des slides :
    Slide 1  — Page de titre (fond bleu marine, titre, spécialité, badge validation)
    Slide 2  — Objectif pédagogique
    Slide 3  — Notions clés  [+ schéma anatomie si disponible]
    Slide 4+ — Explication structurée  (1 slide par sous-section H3)
               [+ schéma protocole sur la dernière slide explication]
    Slide N  — Point terrain MERM  (fond orange doux)
    Slide N+1— Erreurs fréquentes  (icônes ❌ / ✅)
    Slide N+2— Mini quiz
    Slide N+3— Résumé final  [+ schéma résumé si disponible]
    Slide fin — Slide de clôture Xpermanip

Usage :
    from pipeline.pptx_builder import build_pptx

    pptx_path = build_pptx(
        fiche_md="...",
        theme="irm_feminin",
        specialty="irm",
        images={"anatomie": Path("..."), "protocole": Path("..."), "resume": Path("...")}
    )
    # Sauvegardé dans outputs/pptx/<specialty>/<theme>.pptx
"""

import re
from datetime import date
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

PPTX_DIR = Path(__file__).resolve().parent.parent / "outputs" / "pptx"

# ---------------------------------------------------------------------------
# Palette de couleurs Xpermanip
# ---------------------------------------------------------------------------

C = {
    "primary":    RGBColor(0x1A, 0x3A, 0x5C),   # Bleu marine
    "accent":     RGBColor(0x2E, 0x86, 0xAB),   # Bleu clair
    "highlight":  RGBColor(0xF1, 0x8F, 0x01),   # Orange terrain
    "error_red":  RGBColor(0xC0, 0x39, 0x2B),   # Rouge erreur
    "success":    RGBColor(0x27, 0xAE, 0x60),   # Vert correction
    "bg_light":   RGBColor(0xF5, 0xF8, 0xFB),   # Fond gris bleuté
    "white":      RGBColor(0xFF, 0xFF, 0xFF),
    "text":       RGBColor(0x1C, 0x1C, 0x1E),
    "text_light": RGBColor(0x6C, 0x75, 0x7D),
}

# Taille 16:9
SLIDE_W = Inches(13.33)
SLIDE_H = Inches(7.5)


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
    Génère le fichier PowerPoint complet.

    Args:
        fiche_md:  Contenu Markdown de la fiche.
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

    sections = _extract_sections(fiche_md)
    theme_label = theme.replace("_", " ").title()

    # --- Slides ---
    _slide_title(prs, sections, theme_label, specialty)
    _slide_objectif(prs, sections)
    _slide_notions(prs, sections, images.get("anatomie"))
    _slides_explication(prs, sections, images.get("protocole"))
    _slide_terrain(prs, sections)
    _slide_erreurs(prs, sections)
    _slide_quiz(prs, sections)
    _slide_resume(prs, sections, images.get("resume"))
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
# Helpers de mise en forme
# ---------------------------------------------------------------------------

def _blank_slide(prs: Presentation) -> object:
    """Ajoute un slide vierge (layout 6 = blank)."""
    blank_layout = prs.slide_layouts[6]
    return prs.slides.add_slide(blank_layout)


def _fill_bg(slide, color: RGBColor) -> None:
    """Remplit le fond du slide avec une couleur unie."""
    from pptx.oxml.ns import qn
    from lxml import etree
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_textbox(
    slide,
    left: float, top: float, width: float, height: float,
    text: str,
    font_size: int = 18,
    bold: bool = False,
    color: RGBColor | None = None,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    wrap: bool = True,
) -> object:
    """Ajoute un textbox simple sur le slide."""
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
    if color:
        run.font.color.rgb = color
    return txBox


def _add_section_header(slide, title: str, color: RGBColor) -> None:
    """Ajoute un bandeau titre de section en haut du slide."""
    # Barre colorée gauche
    bar = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Inches(0), Inches(0),
        Inches(13.33), Inches(1.1),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = color
    bar.line.fill.background()

    # Titre
    txBox = slide.shapes.add_textbox(
        Inches(0.4), Inches(0.1),
        Inches(12.5), Inches(0.9),
    )
    tf = txBox.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = title
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = C["white"]


def _add_bullet_list(
    slide,
    bullets: list[str],
    left: float, top: float, width: float, height: float,
    font_size: int = 16,
    bullet_char: str = "▸",
    text_color: RGBColor | None = None,
) -> None:
    """Ajoute une liste à puces formatée sur le slide."""
    if not bullets:
        return
    text_color = text_color or C["text"]

    txBox = slide.shapes.add_textbox(
        Inches(left), Inches(top), Inches(width), Inches(height)
    )
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, bullet in enumerate(bullets):
        # Nettoyer le markdown résiduel
        bullet = re.sub(r"\*\*(.*?)\*\*", r"\1", bullet)
        bullet = re.sub(r"`(.*?)`", r"\1", bullet)

        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()

        p.space_before = Pt(4)
        run = p.add_run()
        run.text = f"{bullet_char}  {bullet}"
        run.font.size = Pt(font_size)
        run.font.color.rgb = text_color


def _add_image_right(slide, img_path: Path, top_ratio: float = 0.15) -> None:
    """Insère une image sur la moitié droite du slide."""
    try:
        slide.shapes.add_picture(
            str(img_path),
            Inches(6.9), Inches(top_ratio * 7.5),
            Inches(6.0), Inches(4.2),
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
    """Slide 1 — Page de titre."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["primary"])

    titre = sections.get("titre", theme_label)

    # Bande accent en bas
    accent = slide.shapes.add_shape(
        1, Inches(0), Inches(6.3), Inches(13.33), Inches(1.2)
    )
    accent.fill.solid()
    accent.fill.fore_color.rgb = C["accent"]
    accent.line.fill.background()

    # Spécialité (petite étiquette)
    _add_textbox(
        slide, 0.8, 1.6, 11.5, 0.5,
        f"{specialty.upper()}  ·  Fiche pédagogique MERM",
        font_size=14, color=RGBColor(0xA8, 0xC8, 0xE8),
        align=PP_ALIGN.LEFT,
    )

    # Titre principal
    txBox = slide.shapes.add_textbox(
        Inches(0.8), Inches(2.1), Inches(11.5), Inches(2.5)
    )
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = titre
    run.font.size = Pt(36)
    run.font.bold = True
    run.font.color.rgb = C["white"]

    # Badge date + validation
    _add_textbox(
        slide, 0.8, 6.35, 8.0, 0.6,
        f"Généré le {date.today().strftime('%d/%m/%Y')}  ·  ⚠ À valider avant publication",
        font_size=13, color=C["white"], align=PP_ALIGN.LEFT,
    )

    # Logo Xpermanip
    _add_textbox(
        slide, 10.0, 6.35, 3.0, 0.6,
        "Xpermanip Engine",
        font_size=13, bold=True, color=C["white"], align=PP_ALIGN.RIGHT,
    )


def _slide_objectif(prs: Presentation, sections: dict) -> None:
    """Slide 2 — Objectif pédagogique."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["bg_light"])
    _add_section_header(slide, "🎯  Objectif pédagogique", C["primary"])

    text = sections.get("objectif", "")
    text_clean = re.sub(r"\*\*(.*?)\*\*", r"\1", text)

    _add_textbox(
        slide, 0.5, 1.3, 12.3, 5.5,
        text_clean,
        font_size=18, color=C["text"],
    )


def _slide_notions(
    prs: Presentation,
    sections: dict,
    img_path: Path | None,
) -> None:
    """Slide 3 — Notions clés (avec schéma anatomie si dispo)."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["bg_light"])
    _add_section_header(slide, "🔑  Notions clés", C["primary"])

    bullets = _extract_bullets(sections.get("notions_cles", ""), max_items=12)
    col_width = 6.0 if img_path and img_path.exists() else 12.5

    _add_bullet_list(slide, bullets, 0.5, 1.3, col_width, 5.8, font_size=15)

    if img_path and img_path.exists():
        _add_image_right(slide, img_path, top_ratio=0.17)


def _slides_explication(
    prs: Presentation,
    sections: dict,
    img_path: Path | None,
) -> None:
    """Slides explication — 1 slide par sous-section H3."""
    text = sections.get("explication", "")
    subsections = _extract_subsections(text)

    # Si pas de H3, faire une seule slide avec le contenu brut
    if not subsections:
        slide = _blank_slide(prs)
        _fill_bg(slide, C["bg_light"])
        _add_section_header(slide, "📖  Explication structurée", C["accent"])
        bullets = _extract_bullets(text, max_items=10)
        _add_bullet_list(slide, bullets, 0.5, 1.3, 12.5, 5.8, font_size=15)
        return

    for i, (sub_title, sub_content) in enumerate(subsections):
        slide = _blank_slide(prs)
        _fill_bg(slide, C["bg_light"])

        header_label = f"📖  {sub_title}"
        _add_section_header(slide, header_label, C["accent"])

        # Bullets du sous-contenu
        bullets = _extract_bullets(sub_content, max_items=8)
        if not bullets:
            # Texte libre (paragraphes)
            text_clean = re.sub(r"\*\*(.*?)\*\*", r"\1", sub_content)
            text_clean = re.sub(r"^#+\s+", "", text_clean, flags=re.MULTILINE)
            col_w = 6.0 if (img_path and img_path.exists() and i == len(subsections) - 1) else 12.5
            _add_textbox(slide, 0.5, 1.3, col_w, 5.8, text_clean[:800], font_size=15, color=C["text"])
        else:
            col_w = 6.0 if (img_path and img_path.exists() and i == len(subsections) - 1) else 12.5
            _add_bullet_list(slide, bullets, 0.5, 1.3, col_w, 5.8, font_size=15)

        # Schéma protocole sur la dernière slide d'explication
        if img_path and img_path.exists() and i == len(subsections) - 1:
            _add_image_right(slide, img_path, top_ratio=0.17)


def _slide_terrain(prs: Presentation, sections: dict) -> None:
    """Slide Point terrain MERM — fond orange doux."""
    slide = _blank_slide(prs)

    # Fond blanc avec barre orange
    _fill_bg(slide, C["white"])
    barre = slide.shapes.add_shape(
        1, Inches(0), Inches(0), Inches(0.18), Inches(7.5)
    )
    barre.fill.solid()
    barre.fill.fore_color.rgb = C["highlight"]
    barre.line.fill.background()

    _add_section_header(slide, "🏥  Point terrain manipulateur", C["highlight"])

    bullets = _extract_bullets(sections.get("point_terrain", ""), max_items=12)
    _add_bullet_list(slide, bullets, 0.5, 1.3, 12.5, 5.8, font_size=15, bullet_char="→")


def _slide_erreurs(prs: Presentation, sections: dict) -> None:
    """Slide Erreurs fréquentes."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["bg_light"])
    _add_section_header(slide, "⚠️  Erreurs fréquentes", C["error_red"])

    text = sections.get("erreurs", "")

    # Parser les paires ❌ / ✅ si présentes, sinon bullets normaux
    error_blocks = _parse_error_blocks(text)

    if error_blocks:
        txBox = slide.shapes.add_textbox(
            Inches(0.5), Inches(1.3), Inches(12.3), Inches(5.8)
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        first = True

        for err, fix in error_blocks[:6]:
            if first:
                p = tf.paragraphs[0]
                first = False
            else:
                p = tf.add_paragraph()
                p.space_before = Pt(6)

            r = p.add_run()
            r.text = f"❌  {err}"
            r.font.size = Pt(15)
            r.font.color.rgb = C["error_red"]

            if fix:
                p2 = tf.add_paragraph()
                p2.space_before = Pt(2)
                r2 = p2.add_run()
                r2.text = f"   ✅  {fix}"
                r2.font.size = Pt(14)
                r2.font.color.rgb = C["success"]
    else:
        bullets = _extract_bullets(text, max_items=8)
        _add_bullet_list(slide, bullets, 0.5, 1.3, 12.5, 5.8, font_size=15,
                         text_color=C["error_red"])


def _slide_quiz(prs: Presentation, sections: dict) -> None:
    """Slide Mini quiz — 2 slides si plus de 4 questions."""
    text = sections.get("quiz", "")
    qa_pairs = _parse_quiz(text)

    chunks = [qa_pairs[:4], qa_pairs[4:8]] if len(qa_pairs) > 4 else [qa_pairs]

    for chunk_idx, chunk in enumerate(chunks):
        if not chunk:
            continue
        slide = _blank_slide(prs)
        _fill_bg(slide, RGBColor(0xF0, 0xF7, 0xFF))
        title = "❓  Mini quiz" if chunk_idx == 0 else "❓  Mini quiz (suite)"
        _add_section_header(slide, title, C["accent"])

        txBox = slide.shapes.add_textbox(
            Inches(0.5), Inches(1.3), Inches(12.3), Inches(5.8)
        )
        tf = txBox.text_frame
        tf.word_wrap = True
        first = True

        for q_num, (question, reponse) in enumerate(chunk, start=1 + chunk_idx * 4):
            if first:
                p = tf.paragraphs[0]
                first = False
            else:
                p = tf.add_paragraph()
                p.space_before = Pt(8)

            r = p.add_run()
            r.text = f"Q{q_num}. {question}"
            r.font.size = Pt(15)
            r.font.bold = True
            r.font.color.rgb = C["primary"]

            if reponse:
                p2 = tf.add_paragraph()
                p2.space_before = Pt(2)
                r2 = p2.add_run()
                r2.text = f"    ▸ {reponse[:200]}"
                r2.font.size = Pt(13)
                r2.font.color.rgb = C["text_light"]


def _slide_resume(
    prs: Presentation,
    sections: dict,
    img_path: Path | None,
) -> None:
    """Slide Résumé final."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["bg_light"])
    _add_section_header(slide, "📝  Résumé final", C["primary"])

    bullets = _extract_bullets(sections.get("resume", ""), max_items=8)
    col_width = 6.0 if (img_path and img_path.exists()) else 12.5

    _add_bullet_list(slide, bullets, 0.5, 1.3, col_width, 5.8, font_size=16,
                     text_color=C["primary"])

    if img_path and img_path.exists():
        _add_image_right(slide, img_path, top_ratio=0.17)


def _slide_closing(prs: Presentation, specialty: str) -> None:
    """Slide de clôture."""
    slide = _blank_slide(prs)
    _fill_bg(slide, C["primary"])

    _add_textbox(
        slide, 0, 2.5, 13.33, 1.5,
        "Xpermanip Content Engine",
        font_size=32, bold=True, color=C["white"], align=PP_ALIGN.CENTER,
    )
    _add_textbox(
        slide, 0, 3.9, 13.33, 0.8,
        f"{specialty.upper()}  ·  ⚠ Fiche à valider avant publication",
        font_size=16, color=RGBColor(0xA8, 0xC8, 0xE8), align=PP_ALIGN.CENTER,
    )


# ---------------------------------------------------------------------------
# Parsers spécifiques
# ---------------------------------------------------------------------------

def _parse_error_blocks(text: str) -> list[tuple[str, str]]:
    """
    Tente de parser les blocs ❌ Erreur / ✅ Correction.
    Retourne [(erreur, correction), ...]
    """
    blocks = []
    lines = text.splitlines()
    current_err = ""
    current_fix = ""

    for line in lines:
        stripped = line.strip()
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
        clean = re.sub(r"\*\*(.*?)\*\*", r"\1", stripped)
        clean = re.sub(r"^>+\s*", "", clean)

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
