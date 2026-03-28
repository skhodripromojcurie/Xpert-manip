"""
canva_image_pusher.py
=====================
Génération d'images médicales contextualisées via Claude + DALL-E,
puis envoi direct vers Canva (assets uploadés via l'API Connect).

Flux en 3 étapes :
    1. Claude (claude-opus-4-6, adaptive thinking) analyse les sections
       de la fiche pédagogique et génère des prompts DALL-E 3 médicalement
       précis, adaptés au thème, à la spécialité et au rôle MERM.
    2. DALL-E 3 (OpenAI) génère les 3 images à partir de ces prompts.
    3. Les images sont uploadées directement vers Canva via l'API Connect
       et les asset IDs sont retournés pour être injectés dans le template.

Prérequis :
    pip install anthropic openai requests
    export ANTHROPIC_API_KEY=sk-ant-...
    export OPENAI_API_KEY=sk-...
    export CANVA_API_TOKEN=...

Usage :
    from pipeline.canva_image_pusher import push_images_to_canva

    asset_ids = push_images_to_canva(
        fiche_sections={"titre": "...", "explication": "...", ...},
        theme="irm_feminin",
        specialty="irm",
    )
    # asset_ids = {"anatomie": "ABI...", "protocole": "ABI...", "resume": "ABI..."}
    # Chaque clé est absente si l'étape correspondante a échoué.
"""

import json
import os
import re
import time
from pathlib import Path

IMAGES_DIR = Path(__file__).resolve().parent.parent / "outputs" / "images"

# Noms des 3 types de schémas produits
_SCHEMA_NAMES = ("anatomie", "protocole", "resume")


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def push_images_to_canva(
    fiche_sections: dict[str, str],
    theme: str,
    specialty: str,
    *,
    canva_token: str | None = None,
    verbose: bool = True,
) -> dict[str, str]:
    """
    Génère 3 images médicales via Claude + DALL-E et les uploade dans Canva.

    Étapes :
        1. Claude génère des prompts DALL-E contextualisés à la fiche.
        2. DALL-E 3 génère les images (avec cache local).
        3. Chaque image est uploadée comme asset Canva.

    Args:
        fiche_sections: Sections de la fiche {"titre": ..., "explication": ..., ...}
        theme:          Nom du thème (ex: "irm_feminin")
        specialty:      Spécialité médicale (ex: "irm")
        canva_token:    Token API Canva (si None, lit CANVA_API_TOKEN)
        verbose:        Affiche les logs si True.

    Returns:
        dict: Clés présentes = assets uploadés avec succès.
              {"anatomie": asset_id, "protocole": asset_id, "resume": asset_id}
    """
    # ── Vérifications des clés API ───────────────────────────────────────────
    token = canva_token or os.environ.get("CANVA_API_TOKEN")
    if not token:
        print(
            "  [ImagePusher] CANVA_API_TOKEN manquant.\n"
            "  Canva > Paramètres > Sécurité > Tokens d'accès."
        )
        return {}

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print(
            "  [ImagePusher] ANTHROPIC_API_KEY manquante.\n"
            "  export ANTHROPIC_API_KEY=sk-ant-..."
        )
        return {}

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        print(
            "  [ImagePusher] OPENAI_API_KEY manquante.\n"
            "  export OPENAI_API_KEY=sk-..."
        )
        return {}

    canva_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # ── Étape 1 : Génération des prompts via Claude ──────────────────────────
    if verbose:
        print("  [ImagePusher] Étape 1/3 — Claude génère les prompts image...")

    prompts = _generate_prompts_with_claude(
        fiche_sections, theme, specialty, anthropic_key, verbose=verbose
    )
    if not prompts:
        print("  [ImagePusher] ⚠ Aucun prompt généré — arrêt.")
        return {}

    # ── Étapes 2 & 3 : Génération DALL-E + Upload Canva ─────────────────────
    try:
        from openai import OpenAI
    except ImportError:
        print("  [ImagePusher] Module manquant : pip install openai")
        return {}

    openai_client = OpenAI(api_key=openai_key)
    out_dir = IMAGES_DIR / specialty / theme
    out_dir.mkdir(parents=True, exist_ok=True)

    asset_ids: dict[str, str] = {}

    for schema_name in _SCHEMA_NAMES:
        prompt = prompts.get(schema_name)
        if not prompt:
            print(f"  [ImagePusher] ⚠ Prompt manquant pour '{schema_name}' — ignoré.")
            continue

        img_path = out_dir / f"schema_{schema_name}.png"

        # Étape 2 : Génération DALL-E
        if verbose:
            print(f"  [ImagePusher] Étape 2/3 — DALL-E génère '{schema_name}'...")

        ok = _generate_image(openai_client, prompt, img_path, schema_name)
        if not ok:
            continue

        # Étape 3 : Upload Canva
        if verbose:
            print(f"  [ImagePusher] Étape 3/3 — Upload Canva '{schema_name}'...")

        from pipeline.canva_connector import _upload_asset
        asset_id = _upload_asset(canva_headers, img_path, f"{theme}_{schema_name}")
        if asset_id:
            asset_ids[schema_name] = asset_id
            if verbose:
                print(f"  [ImagePusher] ✓ '{schema_name}' → asset Canva : {asset_id}")

        time.sleep(1)   # pause rate-limit DALL-E entre chaque image

    if verbose:
        print(
            f"  [ImagePusher] {'─' * 40}\n"
            f"  [ImagePusher] Résultat : {len(asset_ids)}/{len(_SCHEMA_NAMES)} "
            f"images uploadées sur Canva."
        )

    return asset_ids


# ---------------------------------------------------------------------------
# Étape 1 : Génération des prompts via Claude
# ---------------------------------------------------------------------------

_CLAUDE_SYSTEM = """\
Tu es un expert en imagerie médicale et en illustration scientifique pédagogique,
spécialisé dans la formation des MERM (Manipulateurs En Électroradiologie Médicale).

Tu génères des prompts DALL-E 3 ultra-précis, médicalement corrects et pédagogiquement
pertinents pour créer des schémas illustrant des fiches de cours MERM.

Règles :
- Chaque prompt est en anglais, très détaillé, commence par le style visuel.
- Inclut toujours : fond blanc, style médical professionnel, labels en français.
- Adapte la précision anatomique / technique au thème fourni.
- Réponds UNIQUEMENT avec le JSON demandé, sans texte avant ou après.\
"""


def _generate_prompts_with_claude(
    sections: dict[str, str],
    theme: str,
    specialty: str,
    api_key: str,
    *,
    verbose: bool = True,
) -> dict[str, str]:
    """
    Appelle Claude (claude-opus-4-6, adaptive thinking, streaming) pour obtenir
    3 prompts DALL-E 3 contextualisés à la fiche.

    Returns:
        dict: {"anatomie": "...", "protocole": "...", "resume": "..."}
              Retourne des prompts génériques en cas d'échec de parsing.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    # Contexte extrait de la fiche (limité pour rester dans les tokens)
    ctx = _build_context(sections)

    user_msg = f"""\
Thème médical : "{theme.replace('_', ' ')}"  |  Spécialité : {specialty.upper()}

Contenu de la fiche pédagogique (extrait) :
{ctx}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Génère 3 prompts DALL-E 3 pour illustrer cette fiche.

1. "anatomie"
   → Schéma anatomique précis des structures clés du thème.
   → Labels anatomiques en français, fond blanc, palette bleu/gris,
     style manuel médical haute qualité, précision maximale.
   → Inclure : vues pertinentes (coupes, schémas 3D), structures nommées.

2. "protocole"
   → Organigramme complet du protocole d'examen MERM pour ce thème.
   → Étapes : préparation patient → positionnement → paramètres
     d'acquisition → séquences/phases → post-traitement.
   → Fond blanc, palette bleu/orange, flèches directionnelles,
     style infographie professionnelle, labels en français.

3. "resume"
   → Infographie de synthèse visuelle des points clés de la fiche.
   → Critères diagnostiques, signes pathologiques caractéristiques,
     paramètres techniques importants, points d'attention MERM.
   → Fond blanc, palette médicale bleue, icônes médicaux,
     style fiche de révision, labels en français.

Réponds UNIQUEMENT avec ce JSON (3 clés exactes) :
{{
  "anatomie": "...",
  "protocole": "...",
  "resume": "..."
}}\
"""

    try:
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=2500,
            thinking={"type": "adaptive"},
            system=_CLAUDE_SYSTEM,
            messages=[{"role": "user", "content": user_msg}],
        ) as stream:
            response = stream.get_final_message()

        if verbose:
            usage = response.usage
            print(
                f"  [ImagePusher] Claude → {usage.input_tokens} in / "
                f"{usage.output_tokens} out tokens"
            )

        text = next(
            (b.text for b in response.content if b.type == "text"), ""
        )
        return _parse_prompts_json(text, theme, specialty)

    except Exception as exc:
        print(f"  [ImagePusher] ⚠ Erreur Claude : {exc}")
        return _fallback_prompts(theme, specialty)


def _build_context(sections: dict[str, str]) -> str:
    """Extrait les parties les plus pertinentes pour le contexte Claude."""
    parts = []
    if sections.get("titre"):
        parts.append(f"**Titre** : {sections['titre']}")
    if sections.get("objectif"):
        parts.append(f"**Objectif** : {sections['objectif'][:300]}")
    if sections.get("notions_cles"):
        parts.append(f"**Notions clés** :\n{sections['notions_cles'][:700]}")
    if sections.get("explication"):
        parts.append(f"**Explication** :\n{sections['explication'][:1000]}")
    if sections.get("point_terrain"):
        parts.append(f"**Point terrain** :\n{sections['point_terrain'][:400]}")
    return "\n\n".join(parts)


def _parse_prompts_json(text: str, theme: str, specialty: str) -> dict[str, str]:
    """Parse le JSON retourné par Claude. Fallback sur prompts génériques."""
    # Nettoyer les éventuels blocs de code Markdown
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
    text = re.sub(r"\n?```\s*$", "", text.strip())

    try:
        data = json.loads(text.strip())
        required = {"anatomie", "protocole", "resume"}
        if required.issubset(data.keys()):
            return {k: str(v) for k, v in data.items() if k in required}
    except (json.JSONDecodeError, ValueError):
        pass

    # Tentative de récupération via regex
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            required = {"anatomie", "protocole", "resume"}
            if required.issubset(data.keys()):
                return {k: str(v) for k, v in data.items() if k in required}
        except (json.JSONDecodeError, ValueError):
            pass

    print("  [ImagePusher] ⚠ Parse JSON échoué — prompts génériques utilisés.")
    return _fallback_prompts(theme, specialty)


def _fallback_prompts(theme: str, specialty: str) -> dict[str, str]:
    """Prompts génériques si Claude n'a pas pu générer de prompts spécifiques."""
    label = theme.replace("_", " ")
    return {
        "anatomie": (
            f"Professional medical anatomy diagram for '{label}' in {specialty} imaging. "
            "White background, labeled anatomical structures in French, blue and grey color palette, "
            "medical textbook illustration style, high educational quality, sharp lines."
        ),
        "protocole": (
            f"Medical imaging protocol flowchart for '{label}' ({specialty} exam). "
            "Step-by-step MERM workflow: patient preparation → positioning → acquisition → post-processing. "
            "White background, blue and orange color scheme, French labels, "
            "arrows between steps, professional infographic style."
        ),
        "resume": (
            f"Visual summary infographic for '{label}' medical imaging ({specialty}). "
            "Key clinical signs, diagnostic criteria, important technical parameters. "
            "White background, medical blue palette, French labels, "
            "educational revision card style, icons and simple illustrations."
        ),
    }


# ---------------------------------------------------------------------------
# Étape 2 : Génération d'image DALL-E 3
# ---------------------------------------------------------------------------

def _generate_image(openai_client, prompt: str, img_path: Path, name: str) -> bool:
    """
    Génère une image via DALL-E 3 et la sauvegarde localement.

    Returns:
        bool: True si l'image est disponible (générée ou déjà en cache).
    """
    if img_path.exists():
        print(f"  [ImagePusher] '{name}' en cache : {img_path.name}")
        return True

    try:
        import requests as req
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url
        img_data = req.get(url, timeout=30).content
        img_path.write_bytes(img_data)
        print(f"  [ImagePusher] ✓ Image '{name}' générée : {img_path.name}")
        return True

    except Exception as exc:
        print(f"  [ImagePusher] ⚠ Échec DALL-E '{name}' : {exc}")
        return False
