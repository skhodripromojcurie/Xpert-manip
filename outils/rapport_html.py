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
from datetime import date, timedelta
from pathlib import Path

import simulateur as sim
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
  --warn:#fab219; --warn-ink:#8a5d00; --warn-bg:#fdf6e6; --crit:#d03b3b;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --s5:#e87ba4; --s6:#008300; --s7:#4a3aa7; --s8:#e34948;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --warn:#fab219; --warn-ink:#fab219; --warn-bg:#2a2410; --crit:#d03b3b;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
} }
:root[data-theme="dark"] {
  --plane:#0d0d0d; --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7;
  --muted:#898781; --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --warn:#fab219; --warn-ink:#fab219; --warn-bg:#2a2410; --crit:#d03b3b;
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

.cal { display:grid; grid-template-columns:repeat(7,1fr) 84px; gap:3px; }
.cal-t { font-size:.7rem; text-transform:uppercase; letter-spacing:.06em;
  color:var(--muted); padding:0 0 4px 3px; font-weight:600; }
.cal-j { border:1px solid var(--grid); border-radius:7px; padding:5px 6px 6px;
  min-height:62px; background:var(--surface); }
.cal-j.hors { opacity:.38; }
.cal-j.repos { border-color:var(--warn); }
.cal-j.illisible { border-color:var(--crit); border-style:dashed;
  background:repeating-linear-gradient(135deg, transparent, transparent 5px,
    var(--grid) 5px, var(--grid) 6px); }
.cal-j.illisible .num { color:var(--crit); font-weight:650; }
.cal-j .illis { display:block; margin-top:5px; font-size:.66rem; color:var(--crit);
  font-weight:600; line-height:1.25; }
.cal-j.conflit { border-color:var(--crit); border-width:2px; padding:4px 5px 5px; }
.cal-j .num { font-size:.72rem; color:var(--muted); font-variant-numeric:tabular-nums; }
.cal-j .jt { float:right; font-size:.72rem; font-weight:650;
  font-variant-numeric:tabular-nums; }
.puces { display:flex; flex-wrap:wrap; gap:2px; margin-top:5px; }
.puce { position:relative; font-size:.66rem; color:#fff; font-weight:600;
  border-radius:3px; padding:1px 4px; line-height:1.5; }
.puce:hover::after { content:attr(data-tip); position:absolute; left:0;
  bottom:calc(100% + 5px); background:var(--ink); color:var(--surface);
  padding:4px 7px; border-radius:5px; font-size:.72rem; font-weight:500;
  white-space:nowrap; z-index:6; }
.cal-s { border-radius:7px; padding:6px; display:flex; flex-direction:column;
  justify-content:center; align-items:flex-end; background:var(--plane);
  font-variant-numeric:tabular-nums; }
.cal-s b { font-size:.86rem; }
.cal-s span { font-size:.7rem; color:var(--muted); }
.cal-s.depasse { background:var(--warn-bg); }
.cal-s.depasse b, .cal-s.depasse span { color:var(--warn-ink); }
.cal-s.limite b { color:var(--warn-ink); }
.cal-s.partiel b { color:var(--crit); }
.cal-s.partiel span { color:var(--crit); }
.cal-leg { display:flex; flex-wrap:wrap; gap:14px; margin-top:14px;
  font-size:.78rem; color:var(--muted); }
.cal-leg i { display:inline-block; width:10px; height:10px; border-radius:3px;
  border:2px solid; vertical-align:-1px; margin-right:5px; font-style:normal; }
@media (max-width:620px) { .cal { grid-template-columns:repeat(7,1fr); }
  .cal-t:last-child, .cal-s { display:none; }
  .cal-j { min-height:46px; padding:3px 4px; } .puce { font-size:.6rem; } }

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
details.detail > summary { cursor:pointer; color:var(--ink-2); font-size:.86rem;
  padding:4px 0; list-style:none; display:flex; align-items:center; gap:7px; }
details.detail > summary::-webkit-details-marker { display:none; }
details.detail > summary::before { content:"▸"; color:var(--muted); font-size:.8rem; }
details.detail[open] > summary::before { content:"▾"; }
details.detail > summary:hover { color:var(--ink); }
details.detail > div { margin-top:14px; }

.pts-g { margin-bottom:20px; }
.pts-g:last-child { margin-bottom:0; }
.pts-g h3 { font-size:.78rem; margin:0 0 9px; font-weight:650;
  display:flex; align-items:center; gap:7px; }
.pts-g h3 b { font-weight:650; font-size:.72rem; padding:1px 7px; border-radius:20px; }
.g-crit h3 { color:var(--crit); } .g-crit h3 b { background:var(--crit); color:#fff; }
.g-warn h3 { color:var(--warn-ink); }
.g-warn h3 b { background:var(--warn); color:#3a2800; }
.g-info h3 { color:var(--muted); }
.g-info h3 b { background:var(--grid); color:var(--ink-2); }
ul.pts li strong { font-weight:650; }

.sim { border:2px solid var(--s1); background:var(--surface); }
.sim .k { color:var(--s1); }
.sim-l { display:flex; flex-wrap:wrap; gap:10px 26px; margin:2px 0 16px; }
.sim-l div { font-size:.86rem; }
.sim-l b { display:block; font-size:1.25rem; font-weight:650; margin-top:2px; }
.sim-d { color:var(--muted); font-size:.8rem; }

nav.som { position:sticky; top:0; z-index:20; background:var(--plane);
  border-bottom:1px solid var(--grid); margin:0 0 8px; padding:10px 0 9px;
  display:flex; flex-wrap:wrap; gap:6px 18px; font-size:.82rem; }
nav.som a { color:var(--ink-2); text-decoration:none; border-bottom:1px solid transparent; }
nav.som a:hover { color:var(--ink); border-bottom-color:var(--ink-2); }
h2 { scroll-margin-top:52px; }

.jauge { display:block; height:6px; border-radius:3px; background:var(--grid);
  position:relative; margin-top:4px; min-width:70px; }
.jauge i { position:absolute; left:0; top:0; bottom:0; border-radius:3px;
  background:var(--s3); }
.rang { color:var(--muted); font-variant-numeric:tabular-nums; }
tr.top td { font-weight:600; }

.sc { display:grid; gap:12px;
  grid-template-columns:repeat(auto-fit,minmax(215px,1fr)); }
.sc-c { border:1px solid var(--ring); border-radius:12px; padding:16px 18px;
  background:var(--surface); }
.sc-c.retenu { border-color:var(--s1); border-width:2px; padding:15px 17px; }
.sc-c h4 { margin:0 0 2px; font-size:.95rem; }
.sc-c .note { color:var(--muted); font-size:.78rem; margin:0 0 12px; }
.sc-c dl { margin:0; display:grid; grid-template-columns:auto auto; gap:5px 10px;
  font-size:.85rem; align-items:baseline; }
.sc-c dt { color:var(--ink-2); }
.sc-c dd { margin:0; text-align:right; font-variant-numeric:tabular-nums;
  font-weight:600; }
.sc-c .gros { font-size:1.45rem; font-weight:650; letter-spacing:-.02em;
  margin:0 0 2px; }
.sc-c .fourche { color:var(--muted); font-size:.78rem; margin:0 0 12px;
  font-variant-numeric:tabular-nums; }
.sc-l { margin:12px 0 0; padding:0; list-style:none; font-size:.8rem;
  color:var(--ink-2); border-top:1px solid var(--grid); padding-top:10px; }
.sc-l li { margin-bottom:3px; }

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


def _grille_du_mois(a, couleurs):
    """Le mois en cases : ce que le graphe hebdomadaire ne montre pas, c'est
    quels jours sont libres — et c'est la question qu'on se pose quand on
    accepte, ou non, une vacation de plus."""
    premier, dernier = a["debut_mois"], a["fin_mois"]
    depart = premier - timedelta(days=premier.weekday())
    arrivee = dernier + timedelta(days=6 - dernier.weekday())
    repos = {r["debut"].date() for r in a["repos_insuffisants"]}
    repos |= {r["fin"].date() for r in a["repos_insuffisants"]}
    conflits = {c["debut"].date() for c in a["chevauchements"]["entre_vacations"]}
    illisibles = a["jours_illisibles"]

    cases = ['<div class="cal">']
    for nom in ("lun", "mar", "mer", "jeu", "ven", "sam", "dim"):
        cases.append(f'<div class="cal-t">{nom}</div>')
    cases.append('<div class="cal-t">semaine</div>')

    jour = depart
    while jour <= arrivee:
        for _ in range(7):
            travail = a["par_jour"].get(jour, {})
            classes = ["cal-j"]
            if not (premier <= jour <= dernier):
                classes.append("hors")
            # Un jour sans heures parce que son titre ne se lit pas n'est pas un
            # jour libre : sans cette marque, la case vide dit le contraire du vrai.
            illisible = illisibles.get(jour)
            if illisible:
                classes.append("illisible")
            elif jour in conflits:
                classes.append("conflit")
            elif jour in repos:
                classes.append("repos")
            puces = "".join(
                f'<span class="puce" style="background:{couleurs.get(nom, "var(--axis)")}"'
                f' data-tip="{e(nom)} · {e(v.format_heures(h))}">'
                f'{e(v.format_heures(h))}</span>'
                for nom, h in sorted(travail.items(), key=lambda kv: -kv[1]))
            total = sum(travail.values())
            marque = (f'<span class=illis>« {e(illisible)} »<br>titre non lu</span>'
                      if illisible else "")
            cases.append(f'<div class="{" ".join(classes)}">'
                         f'<span class="num">{jour.day}</span>'
                         f'{f"<span class=jt>{e(v.format_heures(total))}</span>" if travail else ""}'
                         f'<div class="puces">{puces}</div>{marque}</div>')
            jour += timedelta(days=1)
        # Une semaine sans vacation n'a pas d'entrée dans l'analyse : elle vaut
        # zéro heure et tout le plafond disponible — l'information qu'on cherche
        # quand on se demande où caser une vacation de plus.
        semaine = a["semaines"].get((jour - timedelta(days=7)).isocalendar()[:2],
                                    {"heures": 0.0, "reste": a["plafond"],
                                     "depassement": False})
        # Une semaine qui contient un jour illisible est sous-comptée : son
        # total ne doit pas se lire comme un total.
        debut_semaine = jour - timedelta(days=7)
        partielle = any(debut_semaine + timedelta(days=i) in illisibles
                        for i in range(7))
        etat = ("partiel" if partielle
                else "depasse" if semaine["depassement"]
                else "limite" if semaine["reste"] == 0 else "")
        reste = ("total incomplet" if partielle
                 else f"reste {v.format_heures(semaine['reste'])}" if semaine["reste"] > 0
                 else "à la limite" if semaine["reste"] == 0
                 else f"+{v.format_heures(-semaine['reste'])}")
        cases.append(f'<div class="cal-s {etat}">'
                     f'<b>{"≥ " if partielle else ""}'
                     f'{e(v.format_heures(semaine["heures"]))}</b>'
                     f'<span>{e(reste)}</span></div>')
    cases.append("</div>")
    return "".join(cases)


def _bandeau_simulation(sim):
    """Ce que change la vacation envisagée, en tête de page : c'est la question
    qu'on est venu poser, elle ne doit pas se chercher."""
    gain = sim["net_apres"] - sim["net_avant"]
    heures = sim["heures_apres"] - sim["heures_avant"]
    ajouts = ", ".join(f"« {e(x['evenement'].titre)} » "
                       f"{e(v.format_jour(x['jours'][0]))}" for x in sim["ajouts"])
    bloc = ['<div class="carte tuile sim">',
            f'<div class="k">Et si — {ajouts or "hypothèse non rattachée"}</div>',
            '<div class="sim-l">',
            f'<div>Net du mois<b>{e(euros(sim["net_apres"]))}</b>'
            f'<span class="sim-d">{"+" if gain >= 0 else ""}{e(euros(gain))} '
            f'par rapport à {e(euros(sim["net_avant"]))}</span></div>',
            f'<div>Heures<b>{e(v.format_heures(sim["heures_apres"]))}</b>'
            f'<span class="sim-d">+{e(v.format_heures(heures))}</span></div>']
    for x in sim["ajouts"]:
        montant = (euros(x["montant"]) if x["montant"] is not None
                   else "0 €" if x["mode"] == "mensualisé" else "—")
        bloc.append(f'<div>{e(x["regle"].libelle)}<b>{e(montant)}</b>'
                    f'<span class="sim-d">{e(v.format_heures(x["heures"]))} · '
                    f'{"salarié au mois, aucun euro de plus" if x["mode"] == "mensualisé" else e(x["source"])}'
                    f'</span></div>')
    bloc.append("</div>")

    points = []
    for titre in sim["non_reconnus"]:
        points.append(f"<strong>« {e(titre)} »</strong> n'est rattaché à aucun "
                      f"employeur : ni mot-clé, ni horaire au titre. Rien n'a été simulé.")
    for x in sim["semaines"]:
        etat = ("<strong>fait basculer la semaine au-dessus du plafond</strong>"
                if x["bascule"] else "déjà au-dessus" if x["depassement"]
                else f"il resterait {e(v.format_heures(x['reste']))}")
        points.append(f"S{x['numero']} {x['debut']:%d/%m}–{x['fin']:%d/%m} : "
                      f"{e(v.format_heures(x['avant']))} → "
                      f"{e(v.format_heures(x['apres']))} — {etat}.")
    for c in sim["conflits"]:
        points.append(f"<strong>Nouveau chevauchement</strong> le "
                      f"{e(v.format_jour(c['debut'].date()))} de {c['debut']:%H:%M} "
                      f"à {c['fin']:%H:%M} avec « {e(c['b']['evenement'].titre)} ».")
    for r in sim["repos"]:
        points.append(f"<strong>Nouveau repos trop court</strong> : "
                      f"{e(v.format_heures(r['heures']))} avant "
                      f"{e(v.format_jour(r['debut'].date()))} {r['debut']:%H:%M}.")
    if not points:
        points.append("Rien ne bascule : ni chevauchement, ni repos trop court, "
                      "ni plafond franchi.")
    bloc.append("<ul class=pts>" + "".join(f"<li>{x}</li>" for x in points)
                + "</ul></div>")
    return "".join(bloc)


def _rentabilite(surs, incertains):
    """Une ligne par site réel : c'est là qu'on lit l'écart, même subi."""
    if not surs and not incertains:
        return ""
    haut = max((x["par_heure_passee"] or 0) for x in surs + incertains) or 1
    out = ["<h2 id=rentabilite>Rentabilité par site</h2><div class=carte><table>"
           "<thead><tr><th>Site</th><th>Séance</th><th class=n>Heures</th>"
           "<th class=n>Net</th><th class=n>Coûts</th>"
           "<th class=n>€/h travaillée</th><th>€/h passée</th></tr></thead><tbody>"]
    for groupe, titre in ((surs, None),
                          (incertains, "Trajet ou stationnement incertain")):
        if not groupe:
            continue
        if titre:
            out.append(f'<tr><td colspan=7 class=petit style="padding-top:14px">'
                       f'<strong>{e(titre)}</strong> — non comparables aux lignes '
                       f'ci-dessus</td></tr>')
        for i, x in enumerate(groupe):
            passee = x["par_heure_passee"]
            barre = ("" if passee is None else
                     f'<span class=jauge><i style="width:{passee / haut * 100:.1f}%">'
                     f'</i></span>')
            out.append(
                f'<tr class="{"top" if titre is None and i == 0 else ""}">'
                f'<td>{e(x["site"].libelle)}</td>'
                f'<td>{e(sim.MOT_DU_TYPE[x["type"]])}</td>'
                f'<td class=n>{e(v.format_heures(x["heures"]))}</td>'
                f'<td class=n>{e(euros(x["net"]))}</td>'
                f'<td class=n>{"—" if x["manque"] else e(euros(x["cout"]))}</td>'
                f'<td class=n>{"—" if x["manque"] else e(euros(x["par_heure_travaillee"]))}</td>'
                f'<td class=n>{"—" if passee is None else e(euros(passee))}{barre}</td>'
                f'</tr>')
    out.append("</tbody></table>"
               '<p class="petit" style="margin:14px 0 0">Le classement se renverse '
               "selon la colonne : une séance courte amortit mal son trajet. "
               "L'ordre suit le net par heure travaillée ; la barre montre le net "
               "par heure passée.</p></div>")
    return "".join(out)


def _semaines(sem):
    """Les semaines classées au rendement : où concentrer son énergie."""
    out = ["<h2 id=parsemaine>Semaine par semaine</h2><div class=carte><table>"
           "<thead><tr><th>Semaine</th><th class=n>Fixe</th><th class=n>Marge</th>"
           "<th>Meilleur ajout</th><th class=n>Net ajouté</th>"
           "<th class=n>€/h passée</th></tr></thead><tbody>"]
    haut = max((x["rendement"] for x in sem["semaines"]), default=1) or 1
    for rang, x in enumerate(sem["semaines"], 1):
        p = x["riche"]
        if p:
            ajout = "<br>".join(
                f'{e(v.format_jour(y["jour"]))} · '
                f'{e(sim.MOT_DU_TYPE[y["seance"].type_creneau])} '
                f'<span class=petit>{e(y["seance"].site.libelle)}</span>'
                for y in sorted(p["seances"], key=lambda y: y["jour"]))
            net, rendement = euros(p["net_apres_cout"]), euros(x["rendement"])
            barre = (f'<span class=jauge><i style="width:'
                     f'{x["rendement"] / haut * 100:.1f}%"></i></span>')
        else:
            ajout = ('<span class=petit>aucun créneau ajoutable — ni jour libre, '
                     'ni repos suffisant</span>')
            net = rendement = "—"
            barre = ""
        occasion = ""
        if x["nuits_possibles"]:
            occasion = (f'<br><span class=petit style="color:var(--s1)">Occasion : '
                        f'nuit Delafontaine le '
                        f'{", ".join(e(v.format_jour(j)) for j in x["nuits_possibles"])}'
                        f'</span>')
        autre = x["rentable"]
        if autre and p and autre is not p and autre["temps"]:
            occasion += (f'<br><span class=petit>variante : '
                         f'{e(euros(autre["net_apres_cout"]))} en '
                         f'{e(v.format_heures(autre["temps"]))}, soit '
                         f'{e(euros(autre["net_apres_cout"] / autre["temps"]))}/h</span>')
        bord = "" if x["complete"] else ' <span class=petit>(à cheval)</span>'
        out.append(
            f'<tr class="{"top" if rang == 1 else ""}">'
            f'<td><strong>{rang}.</strong> S{x["numero"]}<br>'
            f'<span class=petit>{x["debut"]:%d/%m}–{x["fin"]:%d/%m}{bord}</span></td>'
            f'<td class=n>{e(v.format_heures(x["fixe"]))}</td>'
            f'<td class=n>{e(v.format_heures(max(0, x["marge"])))}</td>'
            f'<td>{ajout}{occasion}</td>'
            f'<td class=n>{e(net)}</td>'
            f'<td class=n>{e(rendement)}{barre}</td></tr>')
    out.append("</tbody></table>"
               '<p class="petit" style="margin:14px 0 0">Classées au rendement '
               "marginal — l'euro net gagné par heure réellement passée, trajet "
               "compris — et non au revenu : une semaine peut rapporter beaucoup "
               "en coûtant cher.</p></div>")
    return "".join(out)


def _scenarios(resultat):
    """Les trois optimisations côte à côte, sans qu'aucune soit désignée."""
    out = ["<h2 id=scenarios>Scénarios</h2><div class=sc>"]
    meilleur = max(resultat["scenarios"], key=lambda s: s["net_apres_cout"])
    for s in resultat["scenarios"]:
        f = s["fourchette"]
        fourche = ""
        if f["seances"]:
            fourche = (f'<p class=fourche>de {e(euros(s["net_apres_cout"] + f["pire"]))} '
                       f'à {e(euros(s["net_apres_cout"] + f["meilleur"]))} '
                       f'selon l\'affectation</p>')
        elif not s["seances"]:
            fourche = '<p class=fourche>&nbsp;</p>'
        else:
            fourche = '<p class=fourche>montant ferme</p>'
        lignes = "".join(
            f"<li>{e(v.format_jour(x.jour))} — {e(x.site.libelle)} · "
            f"{e(sim.MOT_DU_TYPE[x.type_creneau])}</li>"
            for x in sorted(s["seances"], key=lambda x: x.jour))
        out.append(
            f'<div class="sc-c{" retenu" if s is meilleur else ""}">'
            f'<h4>{e(s["nom"])}</h4><p class=note>{e(s["note"])}</p>'
            f'<p class=gros>{e(euros(s["net_apres_cout"]))}</p>{fourche}'
            f"<dl>"
            f"<dt>Séances ajoutées</dt><dd>{len(s['seances'])}</dd>"
            f"<dt>Net encaissé</dt><dd>{e(euros(s['net']))}</dd>"
            f"<dt>Coûts</dt><dd>−{e(euros(s['cout']))}</dd>"
            f"<dt>Heures travaillées</dt><dd>{e(v.format_heures(s['heures']))}</dd>"
            f"<dt>Trajet</dt><dd>{e(v.format_heures(s['heures_trajet']))}</dd>"
            f"<dt>Temps total</dt><dd>{e(v.format_heures(s['temps']))}</dd>"
            f"<dt>€ / h passée</dt><dd>{e(euros(s['par_heure_passee']))}</dd>"
            f"<dt>Semaines &gt; 48 h</dt><dd>{len(s['depassements'])}</dd>"
            f"</dl>"
            + (f"<ul class=sc-l>{lignes}</ul>" if lignes else "")
            + "</div>")
    out.append("</div>")
    return "".join(out)


def construire(a, sim_resultat=None, rentab=None, simulation=None, sem=None):
    # Une couleur ne se dépense que pour un employeur qui apparaît dans le mois.
    # Un salarié mensualisé sans créneau touche son salaire sans occuper de case :
    # lui donner une teinte encombrerait la légende pour rien, et rapprocherait
    # deux teintes voisines de la palette sans nécessité.
    couleurs = {}
    presents = [nom for nom in sorted(a["par_employeur"])
                if a["par_employeur"][nom]["heures"] > 0]
    for i, nom in enumerate(presents):
        couleurs[nom] = f"var(--s{i + 1})" if i < SERIES else "var(--axis)"
    for nom in a["par_employeur"]:
        couleurs.setdefault(nom, "var(--axis)")

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
    liens = [("#mois", "Le mois"), ("#semaine", "Semaines"),
             ("#revenu", "Revenu")]
    if rentab:
        liens.append(("#rentabilite", "Rentabilité"))
    if sem:
        liens.append(("#parsemaine", "Par semaine"))
    if sim_resultat:
        liens.append(("#scenarios", "Scénarios"))
    liens += [("#regarder", "À regarder"), ("#detail", "Détail")]
    out.append('<nav class="som">'
               + "".join(f'<a href="{u}">{e(t)}</a>' for u, t in liens) + "</nav>")
    if simulation:
        out.append(_bandeau_simulation(simulation))
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
    if a["repos_insuffisants"]:
        n = len(a["repos_insuffisants"])
        out.append(_tuile(
            "Repos quotidien", f"{n} enchaînement{'s' if n > 1 else ''}",
            f"sous {v.format_heures(a['repos_minimum'])} entre deux journées",
            alerte=True))
    out.append("</div>")

    # --- Les heures par semaine --------------------------------------------
    legende = "".join(
        f'<span><span class="pastille" style="background:{couleurs[nom]}"></span>'
        f'{e(nom)}</span>' for nom in presents)

    out.append("<h2 id=mois>Le mois jour par jour</h2><div class=carte>")
    out.append(f'<div class="legende">{legende}</div>')
    out.append(_grille_du_mois(a, couleurs))
    out.append('<div class="cal-leg">'
               '<span><i style="border-color:var(--crit)"></i>deux vacations qui '
               'se chevauchent</span>'
               f'<span><i style="border-color:var(--warn)"></i>moins de '
               f'{e(v.format_heures(a["repos_minimum"]))} de repos avant ou après</span>'
               + (f'<span><i style="border-color:var(--crit);border-style:dashed">'
                  f'</i>titre non lu — le jour n\'est pas libre</span>'
                  if a["jours_illisibles"] else "")
               + '<span>Une case vide est un jour libre.</span></div></div>')

    out.append("<h2 id=semaine>Charge par semaine</h2>")
    out.append(f'<div class="carte"><div class="legende">{legende}</div>'
               + _graphique(a, couleurs) + "</div>")

    # --- Le revenu ----------------------------------------------------------
    if rentab:
        out.append(_rentabilite(*rentab))
    if sem:
        out.append(_semaines(sem))
    if sim_resultat:
        out.append(_scenarios(sim_resultat))
    out.append("<h2 id=revenu>Revenu net par employeur</h2><div class=carte><table>"
               "<thead><tr><th>Employeur</th><th class=n>Heures</th>"
               "<th class=n>Net</th><th class=n>1 h de plus</th>"
               "<th>Base</th></tr></thead><tbody>")
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
        # Ce que vaut une heure de plus : c'est le chiffre qui décide où
        # accepter un créneau, et il ne se lit pas dans le total.
        if salaire:
            marginal = "0 €"
        else:
            taux, _, _ = v.taux_net(b["employeur"], "jour")
            marginal = f"{taux:.2f} €".replace(".", ",") if taux else "—"
        out.append(f"<tr><td><span class=pastille style=background:{couleurs[nom]}></span>"
                   f"{e(nom)}</td><td class=n>{e(heures_txt)}</td>"
                   f"<td class=n>{e(montant)}</td>"
                   f"<td class=n>{e(marginal)}</td>"
                   f"<td class=petit>{e(base)}</td></tr>")
    out.append(f"</tbody><tfoot><tr><td>Total</td><td class=n>{e(v.format_heures(heures))}</td>"
               f"<td class=n>{e(euros(total))}</td><td></td><td class=petit>")
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
    out.append(f'<h2 id=detail>Détail des créneaux</h2><div class=carte>'
               f'<details class="detail"><summary>'
               f'{len(a["vacations"])} créneaux, jour par jour</summary><div>'
               "<table>"
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
    out.append("</tbody></table></div></details></div>")

    # --- Ce qui mérite un œil ----------------------------------------------
    ch = a["chevauchements"]
    # Trois gravités : ce qui est impossible, ce qui est illégal, ce qui est
    # seulement à vérifier. Tout au même niveau, la liste ne se lisait plus.
    graves, legaux, infos = [], [], []
    for c in ch["entre_vacations"]:
        graves.append(f"<strong>{e(v.format_jour(c['debut'].date()))}</strong> — deux "
                      f"vacations de {c['debut']:%H:%M} à {c['fin']:%H:%M} : "
                      f"« {e(c['a']['evenement'].titre)} » ({e(c['a']['regle'].libelle)}) "
                      f"et « {e(c['b']['evenement'].titre)} » "
                      f"({e(c['b']['regle'].libelle)}).")
    for sem in a["semaines"].values():
        if sem["depassement"]:
            legaux.append(f"<strong>{e(v.format_heures(sem['heures']))}</strong> du "
                          f"{sem['debut']:%d/%m} au {sem['fin']:%d/%m} — "
                          f"{e(v.format_heures(-sem['reste']))} au-dessus du plafond de "
                          f"{e(v.format_heures(a['plafond']))}.")
    for r in a["repos_insuffisants"]:
        legaux.append(f"<strong>{e(v.format_heures(r['heures']))} de repos</strong> entre "
                      f"{e(v.format_jour(r['fin'].date()))} {r['fin']:%H:%M} "
                      f"({e(', '.join(r['avant']))}) et "
                      f"{e(v.format_jour(r['debut'].date()))} {r['debut']:%H:%M} "
                      f"({e(', '.join(r['apres']))}) — le minimum est "
                      f"{e(v.format_heures(a['repos_minimum']))}.")
    if ch["avec_autres"]:
        par_ev = {}
        for c in ch["avec_autres"]:
            par_ev.setdefault(c["evenement"].titre, []).append(c["debut"].date())
        for titre, jours in par_ev.items():
            infos.append(f"Vacation posée pendant « {e(titre)} » — "
                         f"{len(set(jours))} jour{'s' if len(set(jours)) > 1 else ''} : "
                         f"{', '.join(f'{j:%d/%m}' for j in sorted(set(jours)))}.")
    infos += [e(x) for x in dict.fromkeys(a["alertes"])]

    groupes = [("g-crit", "Impossible en l'état", graves),
               ("g-warn", "Au-dessus des limites", legaux),
               ("g-info", "À vérifier", infos)]
    if any(p for _, _, p in groupes):
        out.append("<h2 id=regarder>À regarder</h2><div class=carte>")
        for classe, titre, points in groupes:
            if not points:
                continue
            out.append(f'<div class="pts-g {classe}"><h3>{e(titre)}'
                       f'<b>{len(points)}</b></h3><ul class=pts>'
                       + "".join(f"<li>{p}</li>" for p in points) + "</ul></div>")
        out.append("</div>")

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
    p.add_argument("--simuler", action="append", default=[], metavar="HYPOTHÈSE",
                   help="ajoute une vacation fictive et montre ce qu'elle change. "
                        "Ex : --simuler \"24/09 Crystal journée\". Répétable.")
    p.add_argument("--trajets", type=Path, default=None,
                   help="fichier de trajets : ajoute la rentabilité par site et "
                        "les scénarios à la page")
    p.add_argument("--cible", type=float, default=None,
                   help="revenu net visé, pour le scénario « cible »")
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

    hypotheses = [v.lire_hypothese(x, annee) for x in args.simuler]
    simulation = (v.simuler(grille, evenements, annee, mois, hypotheses, feries,
                            couleur) if hypotheses else None)
    analyse = (simulation["apres"] if simulation
               else v.analyser(grille, evenements, annee, mois, feries))

    rentab = resultat = sem = None
    if args.trajets:
        trajets = sim.charger_trajets(args.trajets)
        rentab = sim.rentabilite(grille, trajets, annee, mois)
        resultat = sim.scenarios(grille, evenements, trajets, annee, mois,
                                 args.cible, feries=feries)
        sem = sim.par_semaine(grille, evenements, trajets, annee, mois)
    args.sortie.write_text(
        construire(analyse, resultat, rentab, simulation,
                   sem if args.trajets else None), encoding="utf-8")
    print(f"{args.sortie} écrit.")


if __name__ == "__main__":
    main()
