#!/usr/bin/env python3
"""Lit un mois d'agenda et en sort les heures, le revenu net et les conflits.

Le planning de vacations vit dans l'agenda, pas dans un tableur : un créneau est
un événement, reconnu soit à sa couleur (roulements de semaine A / semaine B),
soit à un mot-clé dans son titre. Ce script relit le mois et répond aux
quatre questions qui décident d'accepter, ou non, une vacation de plus :

  1. combien d'heures, créneau par créneau ;
  2. combien d'heures par semaine — le plafond de 48 h alerte, il ne bloque pas ;
  3. combien net à la fin du mois, employeur par employeur ;
  4. deux créneaux se marchent-ils dessus.

Aucune donnée personnelle n'entre dans ce dépôt : la grille tarifaire et
l'export d'agenda sont attendus dans `donnees/`, que `.gitignore` couvre.
`outils/exemples/` ne contient que des fac-similés inventés, de même forme, qui
font tourner l'outil et ses tests.

    python3 outils/vacations.py --exemple          # sur les fac-similés
    python3 outils/vacations.py --mois 2026-09     # sur donnees/
    python3 outils/vacations.py --mois 2026-09 --json
"""
import argparse
import calendar
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover — Python < 3.9
    ZoneInfo = None

RACINE = Path(__file__).resolve().parent.parent
GRILLE = RACINE / "donnees" / "grille_tarifaire.json"
EVENEMENTS = RACINE / "donnees" / "evenements.json"
EXEMPLES = RACINE / "outils" / "exemples"

# Google numérote deux palettes distinctes, toutes deux à partir de 1 : celle
# des événements (11 couleurs) et celle des agendas (24). Un événement sans
# `colorId` n'est pas incolore — il prend la couleur de son agenda, qui relève
# donc de la seconde table. « Glycine » n'existe que là : une couleur d'agenda
# ne se lit jamais dans le `colorId` d'un événement, elle se déduit de son
# absence. D'où `--couleur-agenda`.
COULEURS_EVENEMENT = {
    "1": "lavande", "2": "sauge", "3": "raisin", "4": "flamant rose",
    "5": "banane", "6": "mandarine", "7": "paon", "8": "graphite",
    "9": "myrtille", "10": "basilic", "11": "tomate",
}
COULEURS_AGENDA = {
    "1": "cacao", "2": "flamant rose", "3": "tomate", "4": "mandarine",
    "5": "potiron", "6": "mangue", "7": "eucalyptus", "8": "basilic",
    "9": "pistache", "10": "avocat", "11": "citron", "12": "banane",
    "13": "sauge", "14": "paon", "15": "cobalt", "16": "myrtille",
    "17": "lavande", "18": "glycine", "19": "graphite", "20": "bouleau",
    "21": "radicchio", "22": "fleur de cerisier", "23": "raisin",
    "24": "amethyste",
}

PLAFOND_DEFAUT = 48.0
PLAGE_NUIT_DEFAUT = "21h-7h"

# Ce que vaut « une journée » ou « un après-midi » n'est écrit nulle part dans
# la grille : ces valeurs sont des hypothèses, pas des faits. Elles sont
# affichées dans le rapport et se remplacent par `creneaux_par_defaut` dans le
# JSON, employeur par employeur.
CRENEAUX_DEFAUT = {
    "matin": "9h-13h",
    "apres_midi": "14h-18h",
    "journee": "9h-13h, 14h-18h",
    "nuit": "21h-7h",
}

MOTS_DUREE = (
    ("journee", ("journee entiere", "journee", "jour entier", "full")),
    ("apres_midi", ("apres-midi", "apres midi", "aprem", "apm", "pm")),
    ("matin", ("matinee", "matin", "am")),
    ("nuit", ("nuit", "garde de nuit")),
)

PLACEHOLDERS = ("a confirmer", "a definir", "a preciser", "non defini", "inconnu")

JOURS_FR = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS_FR = ("janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
           "aout", "septembre", "octobre", "novembre", "decembre")
MOIS_AFFICHES = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
                 "août", "septembre", "octobre", "novembre", "décembre")


# --------------------------------------------------------------------------
# Petits outils de texte, d'heures et de dates
# --------------------------------------------------------------------------

def normaliser(txt):
    """Minuscules, sans accent, espaces resserrés — pour comparer du texte saisi."""
    if not txt:
        return ""
    plat = unicodedata.normalize("NFKD", str(txt))
    plat = "".join(c for c in plat if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plat).strip().lower()


def est_placeholder(txt):
    """La grille dit parfois « à confirmer » : ce n'est pas une valeur."""
    plat = normaliser(txt)
    return any(p in plat for p in PLACEHOLDERS)


# Notation française : « 8-19h », « 8h30-12h30 », « 21h-7h », « de 8h à 12h30 ».
# Le `h` (ou le `:`) est obligatoire quelque part dans la plage, sinon un titre
# contenant une date (« 2026-09-02 ») se lirait comme un horaire.
_HEURE = r"(?<!\d)(\d{1,2})(?:\s*[hH:]\s*(\d{2})(?!\d)|\s*[hH](?!\d))?"
_PLAGE = re.compile(_HEURE + r"\s*(?:[-–—]|à|a)\s*" + _HEURE)


def lire_plage(txt):
    """Extrait la première plage horaire d'un texte. Renvoie (h1, m1, h2, m2)."""
    for m in _PLAGE.finditer(txt or ""):
        if not re.search(r"[hH:]", m.group(0)):
            continue
        h1, m1, h2, m2 = (int(g) if g else 0 for g in m.groups())
        if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59:
            continue
        return (h1, m1, h2, m2), m.span()
    return None, None


def lire_plages(txt):
    """Un créneau peut être coupé : « 9h-13h, 14h-18h » vaut deux plages."""
    plages = []
    for morceau in re.split(r"[;,]| et ", txt or ""):
        plage, _ = lire_plage(morceau)
        if plage:
            plages.append(plage)
    return plages


def titre_horaire_seul(titre):
    """Le titre ne dit-il *que* l'horaire ? (« 8-19h » oui, « Vega 8-19h » non.)"""
    plage, bornes = lire_plage(titre)
    if not plage:
        return False
    reste = (titre[:bornes[0]] + titre[bornes[1]:])
    return not re.search(r"[a-zA-Zà-ÿ]", reste)


def poser(jour, plage):
    """Pose une plage horaire sur un jour. Une fin ≤ début franchit minuit."""
    h1, m1, h2, m2 = plage
    debut = datetime(jour.year, jour.month, jour.day, h1, m1)
    fin = datetime(jour.year, jour.month, jour.day, h2, m2)
    if fin <= debut:
        fin += timedelta(days=1)
    return debut, fin


def heures(debut, fin):
    return (fin - debut).total_seconds() / 3600.0


def format_heures(h):
    total = int(round(h * 60))
    hh, mm = divmod(total, 60)
    return f"{hh} h" if mm == 0 else f"{hh} h {mm:02d}"


def format_euros(v):
    return f"{v:,.2f}".replace(",", " ").replace(".", ",") + " €"


def format_jour(j):
    return f"{JOURS_FR[j.weekday()]} {j.day:02d}/{j.month:02d}"


def format_mois(annee, mois):
    return f"{MOIS_AFFICHES[mois - 1]} {annee}"


def lire_date_fr(txt):
    """« commence le 15 septembre 2026 » → date(2026, 9, 15)."""
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", normaliser(txt))
    if not m or m.group(2) not in MOIS_FR:
        return None
    return date(int(m.group(3)), MOIS_FR.index(m.group(2)) + 1, int(m.group(1)))


# --------------------------------------------------------------------------
# Lecture de l'export d'agenda
# --------------------------------------------------------------------------

@dataclass
class Evenement:
    identifiant: str
    titre: str
    debut: datetime
    fin: datetime
    journee_entiere: bool
    couleur: str
    couleur_explicite: bool

    @property
    def jours(self):
        """Les jours couverts. Sur un événement journée entière, la fin est exclue."""
        premier = self.debut.date()
        dernier = (self.fin - timedelta(seconds=1)).date()
        n = (dernier - premier).days + 1
        return [premier + timedelta(days=i) for i in range(max(n, 1))]


def _instant(bloc, fuseau):
    """Renvoie (datetime naïf local, journée entière ?)."""
    if bloc.get("dateTime"):
        dt = datetime.fromisoformat(bloc["dateTime"].replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            if ZoneInfo is not None and fuseau:
                dt = dt.astimezone(ZoneInfo(fuseau))
            dt = dt.replace(tzinfo=None)
        return dt, False
    brut = bloc.get("date") or ""
    return datetime.strptime(brut[:10], "%Y-%m-%d"), True


def charger_evenements(chemin, couleur_agenda=None):
    """Accepte la réponse brute de l'API Google (`{"events": [...]}`) ou une liste."""
    donnees = json.loads(Path(chemin).read_text(encoding="utf-8"))
    if isinstance(donnees, dict):
        bruts = donnees.get("events") or donnees.get("items") or []
        fuseau = donnees.get("timeZone")
        couleur_agenda = couleur_agenda or COULEURS_AGENDA.get(
            str(donnees.get("colorId", "")))
    else:
        bruts, fuseau = donnees, None

    evenements = []
    for brut in bruts:
        if brut.get("status") == "cancelled":
            continue
        if brut.get("eventType") in ("BIRTHDAY", "WORKING_LOCATION"):
            continue
        debut, entiere = _instant(brut.get("start", {}), fuseau)
        fin, _ = _instant(brut.get("end", {}), fuseau)
        if fin <= debut:
            fin = debut + timedelta(days=1 if entiere else 0, hours=0 if entiere else 1)
        explicite = bool(brut.get("colorId"))
        couleur = (COULEURS_EVENEMENT.get(str(brut["colorId"]))
                   if explicite else normaliser(couleur_agenda) or None)
        evenements.append(Evenement(
            identifiant=brut.get("id", ""),
            titre=brut.get("summary", "(sans titre)"),
            debut=debut, fin=fin, journee_entiere=entiere,
            couleur=couleur, couleur_explicite=explicite))
    evenements.sort(key=lambda e: (e.debut, e.titre))
    return evenements


# --------------------------------------------------------------------------
# Lecture de la grille tarifaire
# --------------------------------------------------------------------------

@dataclass
class Regle:
    cle: str
    libelle: str
    methode: str
    mots_cles: list = field(default_factory=list)
    couleurs: dict = field(default_factory=dict)   # couleur -> variante
    employeur: dict = None
    creneaux: dict = field(default_factory=dict)
    defaut: str = None
    exige_horaire: bool = False
    compte_plafond: bool = True
    date_debut: date = None
    alertes: list = field(default_factory=list)


def _mots_cles(bloc):
    """`mot_cle` mélange la valeur et le commentaire : « Altair (…, ex: Alta) ».

    On garde ce qui précède la parenthèse, plus les variantes annoncées par
    « ex: ». Une entrée déjà propre (`mots_cles: [...]`) court-circuite tout ça.
    """
    if bloc.get("mots_cles"):
        return [normaliser(m) for m in bloc["mots_cles"] if m]
    brut = bloc.get("mot_cle") or ""
    if est_placeholder(brut):
        return []
    mots = []
    tete = normaliser(brut.split("(")[0])
    if tete:
        mots.append(tete)
    for ex in re.findall(r"ex\s*:\s*([^,)]+)", normaliser(brut)):
        mots.append(normaliser(ex))
    # « alta » couvre déjà « altair » : on garde le préfixe le plus court.
    mots = sorted(set(mots), key=len)
    retenus = []
    for m in mots:
        if not any(m.startswith(r) for r in retenus):
            retenus.append(m)
    return retenus


def _defaut_duree(bloc):
    """« journee entiere si rien precise » → journee ; « samedi matin par defaut » → matin."""
    if bloc.get("duree_si_non_precise"):
        return normaliser(bloc["duree_si_non_precise"]).replace(" ", "_")
    texte = bloc.get("duree_par_defaut") or ""
    if est_placeholder(texte):
        return None
    tete = normaliser(texte).split(",")[0].split(" si ")[0]
    for cle, mots in MOTS_DUREE:
        if any(mot in tete for mot in mots):
            return cle
    return None


def mot_cle_duree(titre):
    """« Vega aprèm » → apres_midi. Renvoie None si le titre ne dit rien."""
    plat = normaliser(titre)
    for cle, mots in MOTS_DUREE:
        for mot in mots:
            if re.search(rf"(?<![a-z]){re.escape(mot)}(?![a-z])", plat):
                return cle
    return None


def _apparier_employeur(cle, employeurs):
    """Relie « cabinet_vega » à l'entrée « Cabinet Vega » de la grille."""
    jetons = set(normaliser(cle.replace("_", " ")).split())
    for emp in employeurs:
        noms = set(normaliser(emp.get("nom", "")).split())
        if jetons and jetons <= noms:
            return emp
    return None


def construire_regles(grille):
    employeurs = grille.get("employeurs", [])
    regles = []
    for cle, bloc in (grille.get("identification_agenda_google") or {}).items():
        if not isinstance(bloc, dict):
            continue
        emp = (next((e for e in employeurs
                     if normaliser(e.get("nom")) == normaliser(bloc.get("employeur")))
                    , None) if bloc.get("employeur") else None)
        emp = emp or _apparier_employeur(cle, employeurs)
        regle = Regle(
            cle=cle,
            libelle=bloc.get("libelle") or (emp or {}).get("nom") or cle.replace("_", " ").title(),
            methode=normaliser(bloc.get("methode")) or "texte",
            employeur=emp)

        regle.mots_cles = _mots_cles(bloc)
        for nom_champ, valeur in bloc.items():
            if nom_champ.startswith("couleur") and isinstance(valeur, str) and valeur:
                variante = nom_champ[len("couleur"):].strip("_").replace("_", " ")
                regle.couleurs[normaliser(valeur)] = variante or "couleur"

        # Ce que valent « matin », « journée »… pour cet employeur.
        regle.creneaux = dict(CRENEAUX_DEFAUT)
        regle.defaut = _defaut_duree(bloc)
        creneau_type = (emp or {}).get("creneau_type") or (emp or {}).get("creneau")
        if creneau_type is None:
            liste = (emp or {}).get("creneaux") or []
            creneau_type = liste[0] if liste else None
        if isinstance(creneau_type, str) and lire_plages(creneau_type) and regle.defaut:
            regle.creneaux[regle.defaut] = creneau_type
        regle.creneaux.update(bloc.get("creneaux_par_defaut") or {})

        # « heures indiquées directement dans le titre » : sans horaire au titre,
        # la couleur seule ne suffit pas à faire d'un événement une vacation.
        regle.exige_horaire = "titre" in normaliser(bloc.get("duree"))
        # Une astreinte est du temps de disponibilité, pas du travail effectif :
        # ses heures ne pèsent pas sur le plafond hebdomadaire, sauf mention
        # contraire dans la grille.
        regle.compte_plafond = bool((emp or {}).get(
            "compte_dans_plafond", "astreinte" not in normaliser((emp or {}).get("type"))))
        regle.date_debut = (
            date.fromisoformat(bloc["date_debut"]) if bloc.get("date_debut")
            else date.fromisoformat(emp["date_debut"]) if (emp or {}).get("date_debut")
            else lire_date_fr(bloc.get("note", "")) if "commence" in normaliser(bloc.get("note"))
            else None)

        if regle.methode == "texte" and not regle.mots_cles:
            regle.alertes.append(
                f"{regle.libelle} : aucun mot-clé exploitable dans la grille "
                f"(« {bloc.get('mot_cle', '')[:60]} ») — ses événements ne seront pas reconnus.")
        if regle.methode == "couleur" and not regle.couleurs:
            regle.alertes.append(f"{regle.libelle} : aucune couleur renseignée.")
        if emp is None:
            regle.alertes.append(
                f"{regle.libelle} n'a pas d'entrée dans « employeurs » : heures "
                f"comptées, revenu non calculable.")
        if regle.defaut is None and not regle.exige_horaire:
            regle.alertes.append(
                f"{regle.libelle} : durée par défaut indéterminée — un titre sans "
                f"horaire ne pourra pas être chiffré.")
        regles.append(regle)

    # Les mots-clés priment sur les couleurs : un événement sans `colorId` hérite
    # de la couleur de l'agenda, qui ne dit rien de l'employeur. Le mot-clé, si.
    regles.sort(key=lambda r: (r.methode != "texte", -max((len(m) for m in r.mots_cles), default=0)))
    return regles


# --------------------------------------------------------------------------
# Identification, créneaux, tarification
# --------------------------------------------------------------------------

def identifier(ev, regles):
    """Renvoie (regle, motif) ou (None, None)."""
    plat = normaliser(ev.titre)
    for regle in regles:
        for mot in regle.mots_cles:
            if mot and mot in plat:
                return regle, f"mot-clé « {mot} »"
    for regle in regles:
        if not regle.couleurs or ev.couleur not in regle.couleurs:
            continue
        variante = regle.couleurs[ev.couleur]
        # Couleur héritée = pas d'intention : on exige alors un titre purement horaire.
        if ev.couleur_explicite:
            if regle.exige_horaire and not lire_plage(ev.titre)[0] and ev.journee_entiere:
                continue
        elif not titre_horaire_seul(ev.titre):
            continue
        herite = "" if ev.couleur_explicite else ", héritée de l'agenda"
        return regle, f"couleur {ev.couleur} → {variante}{herite}"
    return None, None


def resoudre_creneaux(ev, regle):
    """Renvoie (liste de (début, fin), source, alertes).

    Un événement « journée entière » qui court sur plusieurs jours est un bloc de
    vacations, pas une seule : « 8-19h » du 14 au 16 vaut trois fois 8h-19h.
    """
    alertes = []
    if not ev.journee_entiere:
        return [(ev.debut, ev.fin)], "durée de l'événement", alertes

    jours = ev.jours
    plage, _ = lire_plage(ev.titre)
    if plage:
        source = f"horaire du titre ({plage[0]:02d}h{plage[1]:02d}–{plage[2]:02d}h{plage[3]:02d})"
        creneaux = [poser(j, plage) for j in jours]
    else:
        cle = mot_cle_duree(ev.titre) or regle.defaut
        gabarit = regle.creneaux.get(cle) if cle else None
        plages = lire_plages(gabarit) if gabarit else []
        if not plages:
            alertes.append(
                f"« {ev.titre} » : ni horaire au titre, ni durée par défaut "
                f"utilisable pour {regle.libelle} — non chiffré.")
            return [], "indéterminée", alertes
        explicite = mot_cle_duree(ev.titre) is not None
        source = (f"{cle.replace('_', ' ')} ({gabarit})" if explicite
                  else f"défaut {cle.replace('_', ' ')} ({gabarit})")
        creneaux = [poser(j, p) for j in jours for p in plages]

    if len(jours) > 1:
        alertes.append(
            f"« {ev.titre} » couvre {len(jours)} jours "
            f"({format_jour(jours[0])} → {format_jour(jours[-1])}) : le créneau est "
            f"compté une fois par jour.")
    return creneaux, source, alertes


def decouper(debut, fin):
    """Coupe un créneau aux minuits : les heures s'imputent au jour où elles tombent."""
    morceaux = []
    curseur = debut
    while curseur < fin:
        minuit = datetime.combine(curseur.date() + timedelta(days=1), datetime.min.time())
        borne = min(minuit, fin)
        morceaux.append((curseur, borne))
        curseur = borne
    return morceaux


def classer(debut, fin, plage_nuit, feries):
    """Ventile un morceau de journée en heures jour / nuit / dimanche-férié."""
    jour = debut.date()
    if jour.weekday() == 6 or jour in feries:
        return [("dimanche_ferie", heures(debut, fin))]
    h1, m1, h2, m2 = plage_nuit
    nuit_debut = datetime.combine(jour, datetime.min.time()).replace(hour=h1, minute=m1)
    nuit_fin = datetime.combine(jour, datetime.min.time()).replace(hour=h2, minute=m2)
    minuit = datetime.combine(jour, datetime.min.time())
    demain = minuit + timedelta(days=1)
    fenetres = ([(minuit, nuit_fin), (nuit_debut, demain)] if nuit_fin <= nuit_debut
                else [(nuit_debut, nuit_fin)])
    nuit = sum(max(0.0, heures(max(debut, a), min(fin, b)))
               for a, b in fenetres if min(fin, b) > max(debut, a))
    total = heures(debut, fin)
    ventile = []
    if nuit > 0:
        ventile.append(("nuit", nuit))
    if total - nuit > 1e-9:
        ventile.append(("jour", total - nuit))
    return ventile


def taux_net(employeur, categorie):
    """Renvoie (taux, estimé ?, motif d'absence)."""
    if not employeur:
        return None, False, "employeur absent de la grille"
    for cle, estime in ((f"taux_net_heure_{categorie}", False),
                        (f"taux_net_estime_heure_{categorie}", True),
                        ("taux_net_heure", False),
                        ("taux_net_estime_heure", True)):
        if employeur.get(cle) is not None:
            return float(employeur[cle]), estime, None
    if any(c.startswith("taux_brut") for c in employeur):
        return None, False, "taux brut seul, net non estimé dans la grille"
    return None, False, "aucun taux horaire dans la grille"


def pause_non_payee(employeur, duree):
    """Heures à retirer d'un créneau au titre de la pause.

    Une journée de 11 h dont une heure de pause n'est ni payée, ni du travail
    effectif : elle sort donc du salaire *et* du plafond hebdomadaire. Le seuil
    évite de l'appliquer à une demi-journée.
    """
    if not employeur:
        return 0.0
    pause = float(employeur.get("pause_non_payee_heures") or 0)
    if not pause:
        return 0.0
    seuil = float(employeur.get("pause_a_partir_de_heures") or 0)
    return pause if duree > seuil else 0.0


def est_mensualise(employeur):
    """Un salarié mensualisé touche son mois, pas ses heures."""
    if not employeur:
        return False
    return bool(employeur.get("brut_mensuel") or employeur.get("net_mensuel")
                or normaliser(employeur.get("type")).startswith("salaire_mensuel"))


def _jours_ouvres(debut, fin):
    n, jour = 0, debut
    while jour <= fin:
        if jour.weekday() < 5:
            n += 1
        jour += timedelta(days=1)
    return n


def salaire_du_mois(employeur, annee, mois, heures_du_mois=0.0):
    """Renvoie (montant net, détail) pour un employeur mensualisé, ou (None, None).

    Un mois partiel — une entrée en poste le 15 — est proratisé. La méthode
    change le résultat de plusieurs centaines d'euros : elle est donc affichée,
    et se choisit par « prorata » (ouvres, calendaire, heures).
    """
    if not est_mensualise(employeur):
        return None, None
    premier = date(annee, mois, 1)
    dernier = date(annee, mois, calendar.monthrange(annee, mois)[1])
    debut = max(premier, date.fromisoformat(employeur["date_debut"])
                if employeur.get("date_debut") else premier)
    fin = min(dernier, date.fromisoformat(employeur["date_fin"])
              if employeur.get("date_fin") else dernier)
    if debut > fin:
        return None, None

    methode = normaliser(employeur.get("prorata")) or "ouvres"
    mensuelles = float(employeur.get("heures_mensuelles") or 0) or None
    if methode == "calendaire":
        part = ((fin - debut).days + 1) / ((dernier - premier).days + 1)
    elif methode == "heures" and mensuelles:
        part = heures_du_mois / mensuelles
    else:
        methode, total = "ouvres", _jours_ouvres(premier, dernier)
        part = _jours_ouvres(debut, fin) / total if total else 1.0

    net_direct = employeur.get("net_mensuel")
    charges = employeur.get("taux_charges_salariales")
    if net_direct is not None:
        base, estime = float(net_direct), False
    else:
        brut = float(employeur["brut_mensuel"])
        if employeur.get("prime_13e_mois"):
            # Versée en douze mensualités : un treizième de plus chaque mois.
            brut += brut / 12
        if charges is None:
            return None, {"manque": "ni « net_mensuel » ni « taux_charges_salariales »"}
        base, estime = brut * (1 - float(charges)), True

    detail = {"part": part, "methode": methode, "estime": estime,
              "complet": debut == premier and fin == dernier,
              "debut": debut, "fin": fin,
              "prime_13e_mois": bool(employeur.get("prime_13e_mois"))}
    return base * part, detail


def forfait(employeur):
    if not employeur:
        return None, False
    if employeur.get("forfait_net") is not None:
        return float(employeur["forfait_net"]), False
    if employeur.get("forfait_net_estime") is not None:
        return float(employeur["forfait_net_estime"]), True
    return None, False


# --------------------------------------------------------------------------
# Analyse
# --------------------------------------------------------------------------

def _controler(ev, regle, jours):
    """Contrôles de cohérence entre le planning posé et ce que dit la grille."""
    alertes = []
    emp = regle.employeur or {}
    statut = normaliser(emp.get("statut"))
    if statut and not statut.startswith("actif"):
        alertes.append(f"« {ev.titre} » : {regle.libelle} est au statut « {emp['statut']} ».")
    possibles = emp.get("jours_possibles")
    if possibles:
        autorises = {normaliser(j).split("_")[0] for j in possibles}
        hors = sorted({JOURS_FR[j.weekday()] for j in jours} - autorises)
        if hors:
            alertes.append(
                f"« {ev.titre} » : {regle.libelle} n'est pas prévu le "
                f"{', '.join(hors)} (grille : {', '.join(possibles)}).")
    if regle.date_debut and jours[0] < regle.date_debut:
        alertes.append(
            f"« {ev.titre} » ({format_jour(jours[0])}) précède le démarrage annoncé "
            f"de {regle.libelle} ({regle.date_debut.isoformat()}).")
    return alertes


def analyser(grille, evenements, annee, mois, feries=()):
    regles = construire_regles(grille)
    plage_nuit = lire_plage(grille.get("plage_nuit") or PLAGE_NUIT_DEFAUT)[0]
    plafond = float((grille.get("contrainte_legale") or {}).get(
        "plafond_hebdomadaire_heures", PLAFOND_DEFAUT))
    feries = set(feries)

    alertes = [a for r in regles for a in r.alertes]
    vacations, autres = [], []

    for ev in evenements:
        regle, motif = identifier(ev, regles)
        if regle is None:
            autres.append(ev)
            continue
        creneaux, source, alertes_creneau = resoudre_creneaux(ev, regle)
        alertes += alertes_creneau
        jours = ev.jours
        alertes += _controler(ev, regle, jours)

        segments, pause_totale = [], 0.0
        for debut, fin in creneaux:
            brut = heures(debut, fin)
            pause = pause_non_payee(regle.employeur, brut)
            pause_totale += pause
            # Au prorata, pour que la pause se réparte comme le créneau entre
            # jour, nuit et dimanche sans qu'on ait à dire à quelle heure elle tombe.
            facteur = (brut - pause) / brut if brut > 0 else 1.0
            for a, b in decouper(debut, fin):
                for categorie, h in classer(a, b, plage_nuit, feries):
                    segments.append({"jour": a.date(), "categorie": categorie,
                                     "heures": h * facteur})
        if pause_totale:
            source += f", − {format_heures(pause_totale)} de pause non payée"

        montant, estime, manque = 0.0, False, None
        base, base_estimee = forfait(regle.employeur)
        if est_mensualise(regle.employeur):
            montant, mode = None, "mensualisé"
        elif base is not None:
            par_jour = bool((regle.employeur or {}).get("forfait_par_jour"))
            montant = base * (len(jours) if par_jour else 1)
            estime = base_estimee
            mode = "forfait par jour" if par_jour else "forfait"
        else:
            mode = "horaire"
            for seg in segments:
                t, est, raison = taux_net(regle.employeur, seg["categorie"])
                if t is None:
                    manque, montant = raison, None
                    break
                montant += t * seg["heures"]
                estime = estime or est
        vacations.append({
            "evenement": ev, "regle": regle, "motif": motif, "source": source,
            "creneaux": creneaux, "segments": segments, "jours": jours,
            "heures": sum(s["heures"] for s in segments), "pause": pause_totale,
            "montant": montant, "estime": estime, "manque": manque, "mode": mode,
        })

    debut_mois = date(annee, mois, 1)
    fin_mois = date(annee, mois, calendar.monthrange(annee, mois)[1])

    def dans_le_mois(seg):
        return debut_mois <= seg["jour"] <= fin_mois

    # Semaines ISO : le plafond se compte lundi-dimanche, tous employeurs
    # confondus, y compris les jours débordant du mois.
    semaines = {}
    for v in vacations:
        for seg in v["segments"]:
            cle = seg["jour"].isocalendar()[:2]
            s = semaines.setdefault(cle, {"heures": 0.0, "par_employeur": {},
                                          "hors_plafond": 0.0, "debut": None, "fin": None})
            if not v["regle"].compte_plafond:
                s["hors_plafond"] += seg["heures"]
                continue
            s["heures"] += seg["heures"]
            s["par_employeur"][v["regle"].libelle] = (
                s["par_employeur"].get(v["regle"].libelle, 0.0) + seg["heures"])
    for (an, num), s in semaines.items():
        s["debut"] = date.fromisocalendar(an, num, 1)
        s["fin"] = date.fromisocalendar(an, num, 7)
        s["dans_le_mois"] = not (s["fin"] < debut_mois or s["debut"] > fin_mois)
        s["complete"] = s["debut"] >= debut_mois and s["fin"] <= fin_mois
        s["depassement"] = s["heures"] > plafond

    # Revenu du mois : au prorata des heures tombant dans le mois, pour qu'un
    # bloc à cheval sur deux mois ne soit pas compté deux fois.
    par_employeur = {}
    for v in vacations:
        h_mois = sum(s["heures"] for s in v["segments"] if dans_le_mois(s))
        v["heures_mois"] = h_mois
        if h_mois <= 0:
            continue
        part = h_mois / v["heures"] if v["heures"] else 0.0
        bloc = par_employeur.setdefault(v["regle"].libelle, {
            "heures": 0.0, "montant": 0.0, "vacations": 0, "estime": False,
            "manque": None, "employeur": v["regle"].employeur})
        bloc["heures"] += h_mois
        bloc["vacations"] += 1
        bloc["estime"] = bloc["estime"] or v["estime"]
        bloc["mensualise"] = bloc.get("mensualise") or v["mode"] == "mensualisé"
        if v["montant"] is None:
            # Un mensualisé touche son mois : ses heures ne se tarifent pas, et
            # leur absence de montant n'est pas un trou dans la grille.
            if v["mode"] != "mensualisé":
                bloc["manque"], bloc["montant"] = v["manque"], None
        elif bloc["montant"] is not None:
            bloc["montant"] += v["montant"] * part

    for emp in grille.get("employeurs", []):
        nom = emp.get("nom", "")
        bloc = par_employeur.get(nom)
        montant, detail = salaire_du_mois(
            emp, annee, mois, bloc["heures"] if bloc else 0.0)
        if detail is None:
            continue
        bloc = par_employeur.setdefault(nom, {
            "heures": 0.0, "montant": 0.0, "vacations": 0, "estime": False,
            "manque": None, "employeur": emp, "mensualise": True})
        bloc["mensualise"] = True
        if montant is None:
            bloc["montant"], bloc["manque"] = None, detail["manque"]
            alertes.append(f"{nom} est mensualisé mais son net n'est pas calculable : "
                           f"{detail['manque']} dans la grille.")
            continue
        bloc["montant"], bloc["estime"] = montant, detail["estime"]
        bloc["salaire"] = detail

    return {
        "annee": annee, "mois": mois, "plafond": plafond,
        "taux_pas": (float(grille["taux_prelevement_source"])
                     if grille.get("taux_prelevement_source") is not None else None),
        "regles": regles, "vacations": vacations, "autres": autres,
        "semaines": dict(sorted(semaines.items())),
        "par_employeur": par_employeur,
        "chevauchements": chevauchements(vacations, autres),
        "alertes": alertes,
        "debut_mois": debut_mois, "fin_mois": fin_mois,
        "debut_lecture": min((e.debut.date() for e in evenements), default=debut_mois),
        "fin_lecture": max(((e.fin - timedelta(seconds=1)).date() for e in evenements),
                           default=fin_mois),
    }


def chevauchements(vacations, autres):
    """Deux créneaux qui se recouvrent, et les vacations prises dans un autre bloc."""
    entre_vacations, avec_autres = [], []
    plats = [(v, c) for v in vacations for c in v["creneaux"]]
    for i in range(len(plats)):
        for j in range(i + 1, len(plats)):
            (v1, (d1, f1)), (v2, (d2, f2)) = plats[i], plats[j]
            if v1 is v2:
                continue
            debut, fin = max(d1, d2), min(f1, f2)
            if fin > debut:
                entre_vacations.append({"a": v1, "b": v2, "debut": debut, "fin": fin,
                                        "heures": heures(debut, fin)})
    for v in vacations:
        for ev in autres:
            for debut, fin in v["creneaux"]:
                bas, haut = max(debut, ev.debut), min(fin, ev.fin)
                if haut > bas:
                    avec_autres.append({"vacation": v, "evenement": ev,
                                        "debut": bas, "fin": haut})
                    break
    return {"entre_vacations": entre_vacations, "avec_autres": avec_autres}


# --------------------------------------------------------------------------
# Rapports
# --------------------------------------------------------------------------

def _titre(txt):
    return f"\n{txt}\n{'─' * len(txt)}"


def rapport_texte(a):
    du_mois = [v for v in a["vacations"] if v["heures_mois"]]
    lignes = [f"Vacations — {format_mois(a['annee'], a['mois'])}",
              f"{len(du_mois)} vacations dans le mois, reconnues sur "
              f"{len(a['vacations']) + len(a['autres'])} événements lus "
              f"({a['debut_lecture']:%d/%m} → {a['fin_lecture']:%d/%m})."]

    lignes.append(_titre("Créneaux"))
    if not a["vacations"]:
        lignes.append("  aucune vacation reconnue.")
    for v in sorted(a["vacations"], key=lambda v: v["evenement"].debut):
        jours = v["jours"]
        etendue = (format_jour(jours[0]) if len(jours) == 1
                   else f"{format_jour(jours[0])} → {format_jour(jours[-1])}")
        montant = (format_euros(v["montant"]) if v["montant"] is not None
                   else "mensualisé" if v["mode"] == "mensualisé" else "non chiffrable")
        hors = "" if v["heures_mois"] else "   (hors mois, compté dans la semaine)"
        lignes.append(f"  {etendue:<30} {v['regle'].libelle:<24} "
                      f"{format_heures(v['heures']):>9}   {montant:>12}{hors}")
        lignes.append(f"  {'':<30} « {v['evenement'].titre} » — {v['motif']}, "
                      f"{v['source']}")

    lignes.append(_titre(f"Heures par semaine (plafond {format_heures(a['plafond'])}, "
                         f"alerte non bloquante)"))
    for (an, num), s in a["semaines"].items():
        if not s["dans_le_mois"]:
            continue
        marque = "  ⚠" if s["depassement"] else "   "
        bord = "" if s["complete"] else "   (semaine à cheval sur le mois voisin)"
        detail = ", ".join(f"{nom} {format_heures(h)}"
                           for nom, h in sorted(s["par_employeur"].items()))
        lignes.append(f"{marque} S{num} {s['debut'].strftime('%d/%m')}–"
                      f"{s['fin'].strftime('%d/%m')} : "
                      f"{format_heures(s['heures']):>9}{bord}")
        if detail:
            lignes.append(f"      {detail}")
        if s["hors_plafond"]:
            lignes.append(f"      + {format_heures(s['hors_plafond'])} d'astreinte, "
                          f"hors plafond (disponibilité, pas travail effectif)")
    depassements = [s for s in a["semaines"].values() if s["depassement"]]
    if depassements:
        n = len(depassements)
        lignes.append(f"  ⚠ {n} semaine{'s' if n > 1 else ''} au-dessus de "
                      f"{format_heures(a['plafond'])}, tous employeurs confondus"
                      f"{' — alerte, pas un blocage.' if n else '.'}")

    lignes.append(_titre("Revenu net projeté"))
    total, incomplet = 0.0, False
    for nom, bloc in sorted(a["par_employeur"].items()):
        if bloc["montant"] is None:
            incomplet = True
            lignes.append(f"  {nom:<28} {format_heures(bloc['heures']):>9}   "
                          f"non chiffrable — {bloc['manque']}")
            continue
        total += bloc["montant"]
        suffixe = "  (estimation)" if bloc["estime"] else ""
        heures = (f"{format_heures(bloc['heures'])} *" if bloc.get("mensualise")
                  else format_heures(bloc["heures"]))
        lignes.append(f"  {nom:<28} {heures:>9}   "
                      f"{format_euros(bloc['montant']):>12}{suffixe}")
        salaire = bloc.get("salaire")
        if salaire:
            assiette = "brut mensuel + 13e mois" if salaire["prime_13e_mois"] else "brut mensuel"
            if salaire["complet"]:
                lignes.append(f"  {'':<28} salaire mensualisé ({assiette}) — "
                              f"* heures indicatives, sans effet sur le montant")
            else:
                lignes.append(f"  {'':<28} salaire mensualisé ({assiette}), mois partiel "
                              f"{salaire['debut']:%d/%m}→{salaire['fin']:%d/%m} : prorata "
                              f"{salaire['part']:.1%} en jours {salaire['methode']}")
                lignes.append(f"  {'':<28} * heures indicatives, sans effet sur le montant")
        delai = (bloc["employeur"] or {}).get("delai_paiement_mois")
        if delai:
            mois_paie = a["mois"] + int(delai)
            annee_paie = a["annee"] + (mois_paie - 1) // 12
            lignes.append(f"  {'':<28} encaissement décalé de {delai} mois → "
                          f"{format_mois(annee_paie, (mois_paie - 1) % 12 + 1)}")
    lignes.append(f"  {'TOTAL NET':<28} "
                  f"{format_heures(sum(b['heures'] for b in a['par_employeur'].values())):>9}   "
                  f"{format_euros(total):>12}" + ("  (partiel)" if incomplet else ""))
    if a["taux_pas"] is not None:
        apres = total * (1 - a["taux_pas"])
        lignes.append(f"  {'après impôt sur le revenu':<28} {'':>9}   "
                      f"{format_euros(apres):>12}"
                      f"  (prélèvement à la source {a['taux_pas']:.1%})")

    lignes.append(_titre("Chevauchements"))
    ch = a["chevauchements"]
    if not ch["entre_vacations"]:
        lignes.append("  aucun conflit entre deux vacations.")
    for c in ch["entre_vacations"]:
        lignes.append(f"  ⚠ {format_jour(c['debut'].date())} "
                      f"{c['debut']:%H:%M}–{c['fin']:%H:%M} "
                      f"({format_heures(c['heures'])}) : "
                      f"« {c['a']['evenement'].titre} » ({c['a']['regle'].libelle}) "
                      f"et « {c['b']['evenement'].titre} » ({c['b']['regle'].libelle}).")
    if ch["avec_autres"]:
        lignes.append("  Vacations posées sur un autre événement de l'agenda :")
        for c in ch["avec_autres"]:
            lignes.append(f"    · {format_jour(c['debut'].date())} "
                          f"« {c['vacation']['evenement'].titre} » "
                          f"({c['vacation']['regle'].libelle}) "
                          f"pendant « {c['evenement'].titre} »")

    if a["alertes"]:
        lignes.append(_titre("À confirmer"))
        for texte in dict.fromkeys(a["alertes"]):
            lignes.append(f"  · {texte}")

    lignes.append(_titre("Hypothèses appliquées"))
    for regle in a["regles"]:
        gabarits = ", ".join(f"{k.replace('_', ' ')} = {v}"
                             for k, v in sorted(regle.creneaux.items()))
        defaut = regle.defaut.replace("_", " ") if regle.defaut else "aucune"
        lignes.append(f"  · {regle.libelle} — durée par défaut : {defaut} ; {gabarits}")
    lignes.append("  Ces durées ne viennent pas de la grille : elles se corrigent par "
                  "`creneaux_par_defaut`\n    et `duree_si_non_precise` dans le JSON.")
    return "\n".join(lignes) + "\n"


def rapport_json(a):
    def jour(d):
        return d.isoformat()
    return {
        "mois": f"{a['annee']:04d}-{a['mois']:02d}",
        "plafond_hebdomadaire": a["plafond"],
        "vacations": [{
            "titre": v["evenement"].titre,
            "employeur": v["regle"].libelle,
            "identification": v["motif"],
            "source_duree": v["source"],
            "jours": [jour(j) for j in v["jours"]],
            "creneaux": [[d.isoformat(), f.isoformat()] for d, f in v["creneaux"]],
            "heures": round(v["heures"], 2),
            "pause_non_payee": round(v["pause"], 2),
            "heures_dans_le_mois": round(v["heures_mois"], 2),
            "montant_net": None if v["montant"] is None else round(v["montant"], 2),
            "montant_estime": v["estime"],
            "motif_non_chiffrable": v["manque"],
        } for v in a["vacations"]],
        "semaines": [{
            "annee": an, "numero": num,
            "debut": jour(s["debut"]), "fin": jour(s["fin"]),
            "heures": round(s["heures"], 2),
            "par_employeur": {k: round(h, 2) for k, h in s["par_employeur"].items()},
            "heures_hors_plafond": round(s["hors_plafond"], 2),
            "depassement_plafond": s["depassement"],
            "semaine_complete_dans_le_mois": s["complete"],
        } for (an, num), s in a["semaines"].items() if s["dans_le_mois"]],
        "revenu_net": {nom: {
            "heures": round(b["heures"], 2),
            "montant": None if b["montant"] is None else round(b["montant"], 2),
            "estimation": b["estime"],
            "motif_non_chiffrable": b["manque"],
        } for nom, b in sorted(a["par_employeur"].items())},
        "total_net": round(sum(b["montant"] for b in a["par_employeur"].values()
                               if b["montant"] is not None), 2),
        "taux_prelevement_source": a["taux_pas"],
        "chevauchements": {
            "entre_vacations": [{
                "debut": c["debut"].isoformat(), "fin": c["fin"].isoformat(),
                "heures": round(c["heures"], 2),
                "a": c["a"]["evenement"].titre, "b": c["b"]["evenement"].titre,
            } for c in a["chevauchements"]["entre_vacations"]],
            "avec_autres": [{
                "jour": jour(c["debut"].date()),
                "vacation": c["vacation"]["evenement"].titre,
                "evenement": c["evenement"].titre,
            } for c in a["chevauchements"]["avec_autres"]],
        },
        "evenements_non_reconnus": [e.titre for e in a["autres"]],
        "alertes": list(dict.fromkeys(a["alertes"])),
    }


# --------------------------------------------------------------------------

def main(argv=None):
    aujourdhui = date.today()
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("--grille", type=Path, default=GRILLE)
    parseur.add_argument("--evenements", type=Path, default=EVENEMENTS)
    parseur.add_argument("--mois", default=None,
                         help="mois à analyser, au format AAAA-MM (défaut : mois en cours)")
    parseur.add_argument("--couleur-agenda", default=None,
                         help="couleur de l'agenda, dont héritent les événements sans "
                              "couleur propre (ex. glycine)")
    parseur.add_argument("--feries", type=Path, default=None,
                         help="fichier JSON : liste de dates AAAA-MM-JJ")
    parseur.add_argument("--exemple", action="store_true",
                         help="tourne sur les fac-similés de outils/exemples/")
    parseur.add_argument("--json", action="store_true")
    args = parseur.parse_args(argv)

    if args.exemple:
        args.grille = EXEMPLES / "grille.exemple.json"
        args.evenements = EXEMPLES / "evenements.exemple.json"
        args.mois = args.mois or "2026-09"
    args.mois = args.mois or aujourdhui.strftime("%Y-%m")

    for chemin in (args.grille, args.evenements):
        if not chemin.exists():
            raise SystemExit(
                f"Fichier introuvable : {chemin}\n"
                f"La grille tarifaire et l'export d'agenda ne sont pas versionnés "
                f"(données personnelles).\nVoir outils/vacations.md ; "
                f"`--exemple` tourne sur les fac-similés du dépôt.")

    annee, mois = (int(x) for x in args.mois.split("-"))
    grille = json.loads(args.grille.read_text(encoding="utf-8"))
    couleur = args.couleur_agenda or grille.get("couleur_agenda_par_defaut")
    evenements = charger_evenements(args.evenements, couleur)
    feries = ([date.fromisoformat(d) for d in
               json.loads(args.feries.read_text(encoding="utf-8"))]
              if args.feries else [])

    analyse = analyser(grille, evenements, annee, mois, feries)
    if not couleur and any(not e.couleur_explicite for e in evenements) and any(
            r.couleurs for r in analyse["regles"]):
        analyse["alertes"].insert(0,
            "Des événements n'ont pas de couleur propre : ils héritent de celle de "
            "l'agenda, que la grille ne dit pas. Passer --couleur-agenda "
            "(ou « couleur_agenda_par_defaut » dans le JSON), sinon les vacations "
            "identifiées par cette couleur sont invisibles.")

    if args.json:
        print(json.dumps(rapport_json(analyse), ensure_ascii=False, indent=2))
    else:
        sys.stdout.write(rapport_texte(analyse))


if __name__ == "__main__":
    main()
