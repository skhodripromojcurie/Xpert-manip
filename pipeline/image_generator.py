"""
image_generator.py
==================
Génération de schémas et illustrations médicales via DALL-E 3 (OpenAI).

Produit 3 images par fiche dans outputs/images/<specialty>/<theme>/ :
  1. schema_anatomie.png   — Vue anatomique illustrée du thème
  2. schema_protocole.png  — Flowchart du protocole d'examen MERM
  3. schema_resume.png     — Infographie de synthèse visuelle

Prérequis :
    pip install openai requests
    set OPENAI_API_KEY=sk-...    (Windows)
    export OPENAI_API_KEY=sk-... (Linux/Mac)

Usage :
    from pipeline.image_generator import generate_schemas

    images = generate_schemas(theme="irm_feminin", specialty="irm", fiche_sections={...})
    # Retourne {"anatomie": Path, "protocole": Path, "resume": Path}
    # Retourne {} si OPENAI_API_KEY est absente ou en cas d'erreur.
"""

import os
import time
from pathlib import Path

IMAGES_DIR = Path(__file__).resolve().parent.parent / "outputs" / "images"

# ---------------------------------------------------------------------------
# Prompts DALL-E par type de schéma (adaptés au contexte médical MERM)
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATES = {
    "anatomie": (
        "Professional medical anatomy diagram for '{theme}' in the field of '{specialty}' medical imaging. "
        "Clean white background, high-quality medical textbook illustration style, "
        "labeled anatomical structures in French, blue and grey color palette, "
        "educational poster format, no text errors, sharp lines, medical accuracy. "
        "Style: hospital medical education material."
    ),
    "protocole": (
        "Professional medical imaging protocol flowchart for '{theme}' ({specialty} exam). "
        "Step-by-step workflow diagram showing patient preparation, positioning, "
        "acquisition sequence, and post-processing steps. "
        "Clean white background, blue and orange color scheme, "
        "French labels, arrows between steps, professional infographic style, "
        "designed for MERM (medical imaging technologist) training."
    ),
    "resume": (
        "Visual summary infographic for '{theme}' medical imaging ({specialty}). "
        "Key clinical signs, diagnostic criteria, and important parameters "
        "arranged in a clear visual layout. "
        "White background, medical blue palette, icons and simple illustrations, "
        "French labels, educational poster style, no complex text, "
        "suitable for medical student revision card."
    ),
}


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def generate_schemas(
    theme: str,
    specialty: str,
    fiche_sections: dict | None = None,
) -> dict[str, Path]:
    """
    Génère 3 schémas médicaux illustrés via DALL-E 3.

    Args:
        theme:          Nom du thème (ex: "irm_feminin").
        specialty:      Nom de la spécialité (ex: "irm").
        fiche_sections: Sections de la fiche (non utilisé actuellement,
                        réservé pour personnalisation future des prompts).

    Returns:
        dict: {"anatomie": Path, "protocole": Path, "resume": Path}
              Dictionnaire vide si OPENAI_API_KEY est absent ou erreur fatale.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print(
            "  [Images] OPENAI_API_KEY manquante — génération de schémas désactivée.\n"
            "  Pour activer : set OPENAI_API_KEY=sk-..."
        )
        return {}

    try:
        from openai import OpenAI
        import requests as req
    except ImportError:
        print("  [Images] Modules manquants : pip install openai requests")
        return {}

    client = OpenAI(api_key=api_key)

    out_dir = IMAGES_DIR / specialty / theme
    out_dir.mkdir(parents=True, exist_ok=True)

    theme_label = theme.replace("_", " ")
    generated: dict[str, Path] = {}

    for schema_name, prompt_tpl in _PROMPT_TEMPLATES.items():
        img_path = out_dir / f"schema_{schema_name}.png"

        # Skip si déjà généré (cache)
        if img_path.exists():
            print(f"  [Images] Schéma '{schema_name}' déjà présent (cache) : {img_path.name}")
            generated[schema_name] = img_path
            continue

        prompt = prompt_tpl.format(theme=theme_label, specialty=specialty)

        try:
            print(f"  [Images] Génération '{schema_name}'...")
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1792x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url

            # Télécharger et sauvegarder
            img_data = req.get(image_url, timeout=30).content
            img_path.write_bytes(img_data)
            generated[schema_name] = img_path
            print(f"  [Images] ✓ Schéma '{schema_name}' sauvegardé : {img_path.name}")

        except Exception as exc:
            print(f"  [Images] ⚠ Échec génération '{schema_name}' : {exc}")
            # Continuer avec les autres schémas

        # Pause courte pour éviter le rate limit DALL-E
        time.sleep(1)

    return generated
