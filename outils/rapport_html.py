#!/usr/bin/env python3
"""Met le rapport de vacations en page, pour être lu plutôt que déroulé.

`vacations.py` sort du texte de terminal : très bien pour vérifier un chiffre,
mauvais pour voir d'un coup si le mois tient debout. Ce script produit la même
analyse en une page autonome — un fichier HTML sans dépendance, qui s'ouvre
depuis un téléphone et s'imprime.

Il ne recalcule rien : il lit `analyser()` et le met en forme. Les chiffres du
terminal et ceux de la page sortent du même endroit, sinon ils finiraient par
diverger.

    python3 outils/rapport_html.py --exemple --sortie /tmp/rapport.html
    python3 outils/rapport_html.py --mois 2026-09 --sortie ~/vacations.html
"""
import argparse
import html
import json
from datetime import date
from pathlib import Path

import vacations as v

# Palette catégorielle de référence, dans son ordre : c'est l'ordre lui-même qui
# garantit la séparation des couleurs voisines, y compris en vision daltonienne.
# On ne le réarrange pas, et un neuvième employeur passe en gris plutôt que
# d'inventer une teinte.
SERIES = 8

STYLE = """
:root {
  --plane:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e;
  --muted:#898781; --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
  --warn:#fab219; --warn-ink:#8a5d00; --warn-bg:#fdf6e6;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --s5:#e87ba4; --s6:#008300; --s7:#4a3aa7; --s8:#e34948;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --warn:#fab219; --warn-ink:#fab219; --warn-bg:#2a2410;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
} }
:root[data-theme="dark"] {
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --warn:#fab219; --warn-ink:#fab219; --warn-bg:#2a2410;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
}
* { box-sizing:border-box; }
body { background:var(--plane); color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;
  margin:0; padding:28px 20px 64px; }
.page { max-width:940px; margin:0 auto; }
h1 { font-size:1.5rem; margin:0 0 4px; letter-spacing:-.01em; }
h2 { font-size:.82rem; text-transform:uppercase; letter-spacing:.07em;
  color:var(--muted); font-weight:600; margin:40px 0 14px; }
.sous { color:var(--ink-2); margin:0 0 28px; font-size:.9rem; }
.carte { background:var(--surface); border:1px solid var(--ring);
  border-radius:12px; padding:20px 22px; }
.tuiles { display:grid; gap:12px; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); }
.tuile .k { color:var(--muted); font-size:.78rem; text-transform:uppercase;
  letter-spacing:.06em; }
.tuile .v { font-size:1.9rem; font-weight:650; margin-top:6px; letter-spacing:-.02em; }
.tuile .n { color:var(--ink-2); font-size:.84rem; margin-top:4px; }
.tuile.alerte { border-color:var(--warn); background:var(--warn-bg); }
.tuile.alerte .v, .tuile.alerte .n { color:var(--warn-ink); }

.legende { display:flex; flex-wrap:wrap; gap:16px; margin:0 0 18px;
  font-size:.85rem; color:var(--ink-2); }
.pastille { width:11px; height:11px; border-radius:3px; display:inline-block;
  margin-right:6px; vertical-align:-1px; }
.graph { position:relative; }
.seuil { position:absolute; top:0; bottom:26px; width:0; border-left:2px dashed var(--warn); }
.seuil span { position:absolute; top:-19px; transform:translateX(-50%);
  font-size:.72rem; color:var(--warn-ink); white-space:nowrap; font-weight:600; }
.ligne { display:grid; grid-template-columns:112px 1fr 76px; align-items:center;
  gap:12px; margin-bottom:9px; }
.ligne .sem { font-size:.83rem; color:var(--ink-2); font-variant-numeric:tabular-nums; }
.ligne .tot { font-size:.86rem; font-weight:600; text-align:right;
  font-variant-numeric:tabular-nums; }
.barre { display:flex; gap:2px; height:26px; }
.seg { position:relative; height:100%; min-width:2px; display:flex;
  align-items:center; justify-content:flex-end; padding-right:6px;
  font-size:.75rem; color:#fff; font-weight:600; overflow:hidden; }
.barre .seg:last-child { border-radius:0 4px 4px 0; }
.seg:hover::after { content:attr(data-tip); position:absolute; right:0; bottom:calc(100% + 6px);
  background:var(--ink); color:var(--surface); padding:5px 8px; border-radius:6px;
  font-size:.75rem; font-weight:500; white-space:nowrap; z-index:5; }
.axe { display:flex; justify-content:space-between; border-top:1px solid var(--axis);
  padding-top:5px; margin-left:124px; margin-right:88px; font-size:.72rem; color:var(--muted);
  font-variant-numeric:tabular-nums; }
.depasse .sem, .depasse .tot { color:var(--warn-ink); font-weight:650; }

table { width:100%; border-collapse:collapse; font-size:.88rem; }
th { text-align:left; font-weight:600; color:var(--muted); font-size:.76rem;
  text-transform:uppercase; letter-spacing:.05em; padding:0 10px 8px 0;
  border-bottom:1px solid var(--grid); }
td { padding:9px 10px 9px 0; border-bottom:1px solid var(--grid); vertical-align:top; }
td:first-child { white-space:nowrap; }
tr:last-child td { border-bottom:0; }
td.n, th.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
tfoot td { font-weight:650; border-top:2px solid var(--axis); border-bottom:0; padding-top:11px; }
.hors td { color:var(--muted); }
.petit { color:var(--muted); font-size:.8rem; }
.titre-ev { color:var(--ink-2); }
ul.pts { margin:0; padding-left:18px; }
ul.pts li { margin-bottom:9px; }
.rappel { margin-top:40px; padding-top:18px; border-top:1px solid var(--grid);
  color:var(--muted); font-size:.8rem; }
@media (max-width:620px) {
  .ligne { grid-template-columns:82px 1fr 62px; gap:8px; }
  .axe { margin-left:90px; margin-right:70px; }
  .seg { font-size:0; }
}
@media print { body { background:#fff; padding:0; } .carte { break-inside:avoid; } }
"""


def e(txt):
    return html.escape(str(txt))


def euros(x):
    return v.format_euros(x)


def _tuile(cle, valeur, note="", alerte=False):
    return (f'<div class="carte tuile{" alerte" if alerte else ""}">'
            f'<div class="k">{e(cle)}</div><div class="v">{e(valeur)}</div>'
            f'{f"<div class=n>{e(note)}</div>" if note else ""}</div>')


def _graphique(a, couleurs):
    semaines = [s for s in a["semaines"].values() if s["dans_le_mois"]]
    if not semaines:
        return "<p class=petit>Aucune heure sur le mois.</p>"
    plafond = a["plafond"]
    haut = max(plafond * 7 / 6, max(s["heures"] for s in semaines) * 1.08)
    lignes = []
    for (_, num), s in a["semaines"].items():
        if not s["dans_le_mois"]:
            continue
        segments = []
        for nom in sorted(s["par_employeur"]):
            h = s["par_employeur"][nom]
            large = h / haut > 0.11
            segments.append(
                f'<div class="seg" style="width:{h / haut * 100:.3f}%;'
                f'background:{couleurs[nom]}" data-tip="{e(nom)} · '
                f'{e(v.format_heures(h))}">{e(v.format_heures(h)) if large else ""}</div>')
        lignes.append(
            f'<div class="ligne{" depasse" if s["depassement"] else ""}">'
            f'<div class="sem">S{num} · {s["debut"]:%d/%m}</div>'
            f'<div class="barre">{"".join(segments)}</div>'
            f'<div class="tot">{e(v.format_heures(s["heures"]))}</div></div>')
    return (f'<div class="graph">'
            f'<div class="seuil" style="left:calc(124px + (100% - 212px) * {plafond / haut:.4f})">'
            f'<span>plafond {e(v.format_heures(plafond))}</span></div>'
            f'{"".join(lignes)}'
            f'<div class="axe"><span>0 h</span><span>{e(v.format_heures(haut))}</span></div></div>')


def construire(a):
    couleurs = {}
    for i, nom in enumerate(sorted(a["par_employeur"])):
        couleurs[nom] = f"var(--s{i + 1})" if i < SERIES else "var(--axis)"

    total = sum(b["montant"] for b in a["par_employeur"].values()
                if b["montant"] is not None)
    heures = sum(b["heures"] for b in a["par_employeur"].values())
    depasse = [s for s in a["semaines"].values() if s["depassement"]]
    estime = any(b["estime"] for b in a["par_employeur"].values())
    mois = v.format_mois(a["annee"], a["mois"])

    # Page autonome : elle doit s'ouvrir depuis un téléphone, sans serveur.
    out = ['<!doctype html><html lang="fr"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           f"<title>Vacations {e(mois)}</title><style>{STYLE}</style></head><body>",
           '<div class="page">', f"<h1>Vacations — {e(mois)}</h1>",
           f'<p class="sous">{len([x for x in a["vacations"] if x["heures_mois"]])} '
           f'vacations, {len(a["par_employeur"])} employeurs. '
           f'Établi le {date.today():%d/%m/%Y} depuis l\'agenda et la grille tarifaire.</p>']

    # --- Les trois chiffres qui décident -----------------------------------
    apres = (f"{euros(total * (1 - a['taux_pas']))} après impôt"
             if a["taux_pas"] is not None else "")
    out.append('<div class="tuiles">')
    out.append(_tuile("Net du mois", euros(total),
                      apres + (" · comprend une estimation" if estime else "")))
    out.append(_tuile("Heures travaillées", v.format_heures(heures),
                      f"sur {len([s for s in a['semaines'].values() if s['dans_le_mois']])} semaines"))
    out.append(_tuile(
        "Plafond hebdomadaire",
        f"{len(depasse)} semaine{'s' if len(depasse) > 1 else ''}" if depasse else "Respecté",
        (f"au-dessus de {v.format_heures(a['plafond'])} — alerte, pas un blocage"
         if depasse else f"aucune semaine au-dessus de {v.format_heures(a['plafond'])}"),
        alerte=bool(depasse)))
    out.append("</div>")

    # --- Les heures par semaine --------------------------------------------
    out.append("<h2>Heures par semaine, tous employeurs confondus</h2>")
    out.append('<div class="carte"><div class="legende">')
    for nom in sorted(a["par_employeur"]):
        out.append(f'<span><span class="pastille" style="background:{couleurs[nom]}"></span>'
                   f'{e(nom)}</span>')
    out.append("</div>" + _graphique(a, couleurs) + "</div>")

    # --- Le revenu ----------------------------------------------------------
    out.append("<h2>Revenu net par employeur</h2><div class=carte><table>"
               "<thead><tr><th>Employeur</th><th class=n>Heures</th>"
               "<th class=n>Net</th><th>Base</th></tr></thead><tbody>")
    for nom, b in sorted(a["par_employeur"].items()):
        salaire = b.get("salaire")
        if salaire:
            base = ("salaire mensualisé" if salaire["complet"] else
                    f"salaire mensualisé, prorata {salaire['part']:.0%} "
                    f"({salaire['debut']:%d/%m}→{salaire['fin']:%d/%m})")
        elif b["employeur"] and b["employeur"].get("taux_net_heure"):
            base = f"{b['employeur']['taux_net_heure']} €/h net"
        elif v.forfait(b["employeur"])[0] is not None:
            base = f"forfait de {euros(v.forfait(b['employeur'])[0])}"
        elif b["employeur"] and any(c.startswith("taux_net") for c in b["employeur"]):
            base = "taux horaire variable (jour / nuit / dimanche)"
        else:
            base = "—"
        if b["estime"]:
            base += " · estimation"
        montant = euros(b["montant"]) if b["montant"] is not None else "non chiffrable"
        heures_txt = v.format_heures(b["heures"]) + (" *" if salaire else "")
        out.append(f"<tr><td><span class=pastille style=background:{couleurs[nom]}></span>"
                   f"{e(nom)}</td><td class=n>{e(heures_txt)}</td>"
                   f"<td class=n>{e(montant)}</td><td class=petit>{e(base)}</td></tr>")
    out.append(f"</tbody><tfoot><tr><td>Total</td><td class=n>{e(v.format_heures(heures))}</td>"
               f"<td class=n>{e(euros(total))}</td><td class=petit>")
    if a["taux_pas"] is not None:
        out.append(f"{e(euros(total * (1 - a['taux_pas'])))} après prélèvement à la source "
                   f"({a['taux_pas']:.1%})")
    out.append("</td></tr></tfoot></table>")
    if any(b.get("salaire") for b in a["par_employeur"].values()):
        out.append('<p class="petit" style="margin:14px 0 0">* Heures indicatives : '
                   "un salarié mensualisé touche son mois, pas ses heures. Elles comptent "
                   "pour le plafond hebdomadaire, pas pour le montant.</p>")
    out.append("</div>")

    # --- Le détail ----------------------------------------------------------
    out.append("<h2>Détail des créneaux</h2><div class=carte><table>"
               "<thead><tr><th>Date</th><th>Employeur</th><th>Événement</th>"
               "<th class=n>Heures</th><th class=n>Net</th></tr></thead><tbody>")
    for vac in sorted(a["vacations"], key=lambda x: x["evenement"].debut):
        jours = vac["jours"]
        quand = (v.format_jour(jours[0]) if len(jours) == 1
                 else f"{v.format_jour(jours[0])} → {v.format_jour(jours[-1])}")
        montant = (euros(vac["montant"]) if vac["montant"] is not None
                   else "mensualisé" if vac["mode"] == "mensualisé" else "—")
        detail = vac["source"]
        out.append(f'<tr class="{"hors" if not vac["heures_mois"] else ""}">'
                   f"<td>{e(quand)}{'<br><span class=petit>hors mois</span>' if not vac['heures_mois'] else ''}</td>"
                   f"<td>{e(vac['regle'].libelle)}</td>"
                   f"<td class=titre-ev>{e(vac['evenement'].titre)}"
                   f"<br><span class=petit>{e(detail)}</span></td>"
                   f"<td class=n>{e(v.format_heures(vac['heures']))}</td>"
                   f"<td class=n>{e(montant)}</td></tr>")
    out.append("</tbody></table></div>")

    # --- Ce qui mérite un œil ----------------------------------------------
    ch = a["chevauchements"]
    points = []
    for c in ch["entre_vacations"]:
        points.append(f"<strong>Conflit</strong> le {e(v.format_jour(c['debut'].date()))} "
                      f"de {c['debut']:%H:%M} à {c['fin']:%H:%M} : "
                      f"« {e(c['a']['evenement'].titre)} » et "
                      f"« {e(c['b']['evenement'].titre)} ».")
    for s in a["semaines"].values():
        if s["depassement"]:
            points.append(f"<strong>{e(v.format_heures(s['heures']))}</strong> du "
                          f"{s['debut']:%d/%m} au {s['fin']:%d/%m}, au-dessus du plafond de "
                          f"{e(v.format_heures(a['plafond']))}.")
    if ch["avec_autres"]:
        par_ev = {}
        for c in ch["avec_autres"]:
            par_ev.setdefault(c["evenement"].titre, []).append(c["debut"].date())
        for titre, jours in par_ev.items():
            points.append(f"Vacation posée pendant « {e(titre)} » — "
                          f"{len(set(jours))} jour{'s' if len(set(jours)) > 1 else ''} : "
                          f"{', '.join(f'{j:%d/%m}' for j in sorted(set(jours)))}.")
    points += [e(x) for x in dict.fromkeys(a["alertes"])]
    if points:
        out.append("<h2>À regarder</h2><div class=carte><ul class=pts>"
                   + "".join(f"<li>{p}</li>" for p in points) + "</ul></div>")

    out.append('<p class="rappel">Les durées par défaut d\'une journée ou d\'une '
               'demi-journée ne figurent pas dans la grille : ce sont des hypothèses, '
               'corrigeables par <code>creneaux_par_defaut</code>. '
               'Un montant marqué « estimation » repose sur un taux de charges '
               'salariales, pas sur un bulletin de paie.</p></div></body></html>')
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--grille", type=Path, default=v.GRILLE)
    p.add_argument("--evenements", type=Path, default=v.EVENEMENTS)
    p.add_argument("--mois", default=None)
    p.add_argument("--couleur-agenda", default=None)
    p.add_argument("--feries", type=Path, default=None)
    p.add_argument("--exemple", action="store_true")
    p.add_argument("--sortie", type=Path, required=True)
    args = p.parse_args(argv)

    if args.exemple:
        args.grille = v.EXEMPLES / "grille.exemple.json"
        args.evenements = v.EXEMPLES / "evenements.exemple.json"
        args.mois = args.mois or "2026-09"
    args.mois = args.mois or date.today().strftime("%Y-%m")

    grille = json.loads(args.grille.read_text(encoding="utf-8"))
    couleur = args.couleur_agenda or grille.get("couleur_agenda_par_defaut")
    evenements = v.charger_evenements(args.evenements, couleur)
    feries = ([date.fromisoformat(d) for d in
               json.loads(args.feries.read_text(encoding="utf-8"))] if args.feries else [])
    annee, mois = (int(x) for x in args.mois.split("-"))

    args.sortie.write_text(
        construire(v.analyser(grille, evenements, annee, mois, feries)), encoding="utf-8")
    print(f"{args.sortie} écrit.")


if __name__ == "__main__":
    main()
