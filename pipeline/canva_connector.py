"""
canva_connector.py
==================
Intégration Canva Connect API pour comptes Pro.

Fonctionnalités :
  1. Upload d'images (assets) vers Canva
  2. Autofill d'un template Canva avec le contenu de la fiche
  3. Export du design résultant en PPTX

Prérequis :
    - Compte Canva Pro
    - Personal Access Token (PAT) :
        Canva > Paramètres > Sécurité > Tokens d'accès personnels
        Scopes requis : design:content:write, asset:write, export:write
    - Variables d'environnement :
        CANVA_API_TOKEN    = votre_token_personnel
        CANVA_TEMPLATE_ID  = ID du template (ex: DAFxxxxxxxxxxxxxxx)

Configuration du template Canva :
    Créer un template Canva de type Présentation avec les champs de données :
        TITRE, SPECIALITE, OBJECTIF, NOTIONS_CLES, EXPLICATION,
        TERRAIN, ERREURS, QUIZ, RESUME, DATE
        SCHEMA_ANATOMIE, SCHEMA_PROTOCOLE, SCHEMA_RESUME  (champs image)

    L'ID du template se trouve dans l'URL de Canva :
        https://www.canva.com/design/DAFxxxxxxx/edit → ID = DAFxxxxxxx

Usage :
    from pipeline.canva_connector import push_to_canva

    result = push_to_canva(
        fiche_sections={"titre": "...", "objectif": "...", ...},
        theme="irm_feminin",
        specialty="irm",
        images={"anatomie": Path("..."), "protocole": Path("...")}
    )
    # result = {"design_url": "...", "pptx_url": "..."} ou None
"""

import base64
import os
import time
from pathlib import Path

import requests

CANVA_API_BASE  = "https://api.canva.com/rest/v1"
PPTX_DIR        = Path(__file__).resolve().parent.parent / "outputs" / "pptx"
POLL_INTERVAL   = 3    # secondes entre chaque sondage
POLL_MAX_TRIES  = 20   # 20 × 3s = 60s max d'attente


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def push_to_canva(
    fiche_sections: dict[str, str],
    theme: str,
    specialty: str,
    images: dict[str, Path] | None = None,
) -> dict | None:
    """
    Envoie la fiche dans Canva via l'API Connect (compte Pro).

    Étapes :
        1. Upload des images générées comme assets Canva
        2. Autofill du template avec le texte + asset IDs
        3. Attente de la création du design
        4. Export en PPTX + téléchargement local

    Args:
        fiche_sections: Sections de la fiche {"titre": ..., "objectif": ..., ...}
        theme:          Nom du thème (ex: "irm_feminin")
        specialty:      Spécialité (ex: "irm")
        images:         Dict optionnel {"anatomie": Path, "protocole": Path, "resume": Path}

    Returns:
        dict: {"design_url": str, "pptx_path": Path} ou None si non configuré / erreur.
    """
    token       = os.environ.get("CANVA_API_TOKEN")
    template_id = os.environ.get("CANVA_TEMPLATE_ID")

    if not token:
        print(
            "  [Canva] CANVA_API_TOKEN manquant.\n"
            "  Obtenir un token : Canva > Paramètres > Sécurité > Tokens d'accès\n"
            "  set CANVA_API_TOKEN=votre_token"
        )
        return None

    if not template_id:
        print(
            "  [Canva] CANVA_TEMPLATE_ID manquant.\n"
            "  Créer un template dans Canva et renseigner son ID.\n"
            "  set CANVA_TEMPLATE_ID=DAFxxxxxxx"
        )
        return None

    if images is None:
        images = {}

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # 1. Upload des images → asset IDs
    asset_ids: dict[str, str] = {}
    for name, path in images.items():
        if path and path.exists():
            asset_id = _upload_asset(headers, path, f"{theme}_{name}")
            if asset_id:
                asset_ids[name] = asset_id

    # 2. Préparer les données d'autofill
    data_fields = _build_autofill_data(fiche_sections, theme, specialty, asset_ids)

    # 3. Lancer l'autofill
    print(f"  [Canva] Autofill du template {template_id}...")
    autofill_job_id = _start_autofill(headers, template_id, theme, data_fields)
    if not autofill_job_id:
        return None

    # 4. Attendre la création du design
    design_id = _wait_for_autofill(headers, template_id, autofill_job_id)
    if not design_id:
        return None

    design_url = f"https://www.canva.com/design/{design_id}/edit"
    print(f"  [Canva] ✓ Design créé : {design_url}")

    # 5. Exporter en PPTX
    pptx_path = _export_pptx(headers, design_id, theme, specialty)

    return {
        "design_url": design_url,
        "pptx_path":  pptx_path,
    }


# ---------------------------------------------------------------------------
# Upload d'asset
# ---------------------------------------------------------------------------

def _upload_asset(headers: dict, img_path: Path, name: str) -> str | None:
    """
    Upload une image vers Canva et retourne son asset_id.

    Processus en 3 étapes :
      a. Initier l'upload → obtenir l'URL d'upload pré-signée
      b. Envoyer le fichier binaire en PUT
      c. Sonder le statut jusqu'à "success"
    """
    print(f"  [Canva] Upload asset '{name}'...")

    # a. Initier
    name_b64 = base64.b64encode(img_path.name.encode()).decode()
    resp = requests.post(
        f"{CANVA_API_BASE}/asset-uploads",
        headers=headers,
        json={"name_base64": name_b64},
        timeout=15,
    )

    if not resp.ok:
        print(f"  [Canva] ⚠ Échec initiation upload '{name}' : {resp.status_code} {resp.text[:200]}")
        return None

    job = resp.json().get("job", {})
    job_id    = job.get("id")
    upload    = job.get("asset_upload", {})
    upload_url     = upload.get("upload_url")
    upload_headers = upload.get("upload_headers", {})

    if not upload_url:
        print(f"  [Canva] ⚠ upload_url absent pour '{name}'")
        return None

    # b. Envoyer le fichier
    with open(img_path, "rb") as f:
        put_resp = requests.put(
            upload_url,
            headers=upload_headers,
            data=f,
            timeout=60,
        )

    if not put_resp.ok:
        print(f"  [Canva] ⚠ Échec envoi fichier '{name}' : {put_resp.status_code}")
        return None

    # c. Sonder le statut
    for _ in range(POLL_MAX_TRIES):
        time.sleep(POLL_INTERVAL)
        poll = requests.get(
            f"{CANVA_API_BASE}/asset-uploads/{job_id}",
            headers=headers,
            timeout=15,
        )
        if not poll.ok:
            continue

        poll_job = poll.json().get("job", {})
        status   = poll_job.get("status")

        if status == "success":
            asset_id = poll_job.get("asset_upload", {}).get("asset", {}).get("id")
            print(f"  [Canva] ✓ Asset '{name}' uploadé : {asset_id}")
            return asset_id

        if status == "failed":
            print(f"  [Canva] ⚠ Upload échoué pour '{name}'")
            return None

    print(f"  [Canva] ⚠ Timeout upload '{name}'")
    return None


# ---------------------------------------------------------------------------
# Autofill
# ---------------------------------------------------------------------------

def _build_autofill_data(
    sections: dict[str, str],
    theme: str,
    specialty: str,
    asset_ids: dict[str, str],
) -> list[dict]:
    """Construit la liste de champs pour l'autofill Canva."""
    from datetime import date

    def _truncate(text: str, max_len: int = 500) -> str:
        text = text.strip()
        return text[:max_len] + "…" if len(text) > max_len else text

    fields: list[dict] = [
        {"type": "text", "name": "TITRE",       "text": sections.get("titre", theme.replace("_", " ").title())},
        {"type": "text", "name": "SPECIALITE",  "text": specialty.upper()},
        {"type": "text", "name": "OBJECTIF",    "text": _truncate(sections.get("objectif", ""), 600)},
        {"type": "text", "name": "NOTIONS_CLES","text": _truncate(sections.get("notions_cles", ""), 800)},
        {"type": "text", "name": "EXPLICATION", "text": _truncate(sections.get("explication", ""), 1000)},
        {"type": "text", "name": "TERRAIN",     "text": _truncate(sections.get("point_terrain", ""), 800)},
        {"type": "text", "name": "ERREURS",     "text": _truncate(sections.get("erreurs", ""), 700)},
        {"type": "text", "name": "QUIZ",        "text": _truncate(sections.get("quiz", ""), 700)},
        {"type": "text", "name": "RESUME",      "text": _truncate(sections.get("resume", ""), 600)},
        {"type": "text", "name": "DATE",        "text": date.today().strftime("%d/%m/%Y")},
    ]

    # Champs image (optionnels)
    for schema_name, field_name in [
        ("anatomie",  "SCHEMA_ANATOMIE"),
        ("protocole", "SCHEMA_PROTOCOLE"),
        ("resume",    "SCHEMA_RESUME"),
    ]:
        if schema_name in asset_ids:
            fields.append({
                "type":     "image",
                "name":     field_name,
                "asset_id": asset_ids[schema_name],
            })

    return fields


def _start_autofill(
    headers: dict,
    template_id: str,
    theme: str,
    data_fields: list[dict],
) -> str | None:
    """Lance le job d'autofill Canva. Retourne le job_id ou None."""
    resp = requests.post(
        f"{CANVA_API_BASE}/designs/{template_id}/autofill",
        headers=headers,
        json={
            "title": theme.replace("_", " ").title(),
            "data":  data_fields,
        },
        timeout=20,
    )

    if not resp.ok:
        print(f"  [Canva] ⚠ Autofill échoué : {resp.status_code} {resp.text[:300]}")
        return None

    job_id = resp.json().get("job", {}).get("id")
    return job_id


def _wait_for_autofill(
    headers: dict,
    template_id: str,
    job_id: str,
) -> str | None:
    """Attend la fin du job d'autofill. Retourne le design_id ou None."""
    for attempt in range(POLL_MAX_TRIES):
        time.sleep(POLL_INTERVAL)
        resp = requests.get(
            f"{CANVA_API_BASE}/designs/{template_id}/autofill/{job_id}",
            headers=headers,
            timeout=15,
        )

        if not resp.ok:
            continue

        job = resp.json().get("job", {})
        status = job.get("status")

        if status == "success":
            return job.get("design", {}).get("id")

        if status == "failed":
            error = job.get("error", {})
            print(f"  [Canva] ⚠ Autofill échoué : {error}")
            return None

        if attempt % 3 == 0:
            print(f"  [Canva] En attente du design... ({attempt * POLL_INTERVAL}s)")

    print("  [Canva] ⚠ Timeout autofill")
    return None


# ---------------------------------------------------------------------------
# Export PPTX
# ---------------------------------------------------------------------------

def _export_pptx(
    headers: dict,
    design_id: str,
    theme: str,
    specialty: str,
) -> Path | None:
    """Exporte le design Canva en PPTX et le télécharge localement."""
    print(f"  [Canva] Export PPTX du design {design_id}...")

    resp = requests.post(
        f"{CANVA_API_BASE}/exports",
        headers=headers,
        json={
            "design_id": design_id,
            "format":    {"type": "pptx"},
        },
        timeout=20,
    )

    if not resp.ok:
        print(f"  [Canva] ⚠ Export échoué : {resp.status_code} {resp.text[:200]}")
        return None

    export_id = resp.json().get("job", {}).get("id")
    if not export_id:
        return None

    # Sonder jusqu'à la fin de l'export
    for attempt in range(POLL_MAX_TRIES):
        time.sleep(POLL_INTERVAL)
        poll = requests.get(
            f"{CANVA_API_BASE}/exports/{export_id}",
            headers=headers,
            timeout=15,
        )

        if not poll.ok:
            continue

        job = poll.json().get("job", {})
        status = job.get("status")

        if status == "success":
            urls = job.get("urls", [])
            if not urls:
                print("  [Canva] ⚠ URL de téléchargement absente")
                return None

            download_url = urls[0]
            return _download_pptx(download_url, theme, specialty)

        if status == "failed":
            print(f"  [Canva] ⚠ Export PPTX échoué")
            return None

        if attempt % 3 == 0:
            print(f"  [Canva] Export en cours... ({attempt * POLL_INTERVAL}s)")

    print("  [Canva] ⚠ Timeout export")
    return None


def _download_pptx(url: str, theme: str, specialty: str) -> Path | None:
    """Télécharge le PPTX depuis l'URL Canva et le sauvegarde localement."""
    out_dir = PPTX_DIR / specialty
    out_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = out_dir / f"{theme}_canva.pptx"

    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        with open(pptx_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"  [Canva] ✓ PPTX Canva téléchargé : {pptx_path.name}")
        return pptx_path
    except Exception as exc:
        print(f"  [Canva] ⚠ Échec téléchargement PPTX : {exc}")
        return None
