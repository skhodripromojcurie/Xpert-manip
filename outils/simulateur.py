#!/usr/bin/env python3
"""Choisit où poser des vacations en plus, et ce que ça coûte vraiment.

Le planning Résonance est fixe : il se lit dans l'agenda, comme le fait déjà
`vacations.py`. Ce qui se décide, ce sont les créneaux qu'on ajoute par-dessus,
sur les jours restés libres. Ce module les énumère, les chiffre, et répond aux
trois questions qui ne donnent pas la même réponse :

  · le revenu net le plus haut ;
  · le meilleur rendement, une fois le trajet compté dans le temps passé ;
  · la cible atteinte en y passant le moins de temps possible.

Aucune n'est « la bonne » — elles sont présentées côte à côte.

Rien du calcul de paie n'est réécrit : le simulateur fabrique des événements
d'agenda et les fait passer par `vacations.analyser`. C'est la même
identification, le même tarif, le même plafond, le même repos de 11 h. Un
scénario dit donc exactement ce que dira le mois une fois les créneaux posés.

Ce que le simulateur ajoute, c'est le coût du déplacement — carburant,
stationnement, repas — et le temps de trajet, qui ne se voient nulle part sur
une fiche de paie et qui changent le classement des sites.

    python3 outils/simulateur.py --mois 2026-11 --rentabilite
    python3 outils/simulateur.py --mois 2026-11 --optimiser --cible 5500
"""
import argparse
import itertools
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import vacations as v

RACINE = Path(__file__).resolve().parent.parent
TRAJETS = RACINE / "donnees" / "trajets.json"

# Les types de séance qu'on sait poser, et le mot qui les désigne dans un titre
# d'agenda. L'ordre est celui du tri d'affichage.
TYPES = ("matin", "apres_midi", "journee", "nuit")
MOT_DU_TYPE = {"matin": "matin", "apres_midi": "aprèm", "journee": "journée",
               "nuit": "nuit"}


# --------------------------------------------------------------------------
# Les lieux et ce qu'ils coûtent
# --------------------------------------------------------------------------

# D'où sort une durée de trajet. Le rapport le dit, parce qu'un temps mesuré et
# un temps extrapolé ne se lisent pas de la même façon.
MESUREE, EXTRAPOLEE, THEORIQUE = "mesurée", "extrapolée", "théorique"


def _fiabilite(note):
    """Déduit d'où sort une durée, d'après la note qui l'accompagne.

    On ne se fie qu'à des marqueurs positifs — « temps réel », « constaté ». Le
    mot « mesure » seul ne dit rien : il apparaît aussi bien dans « pas une
    mesure » que dans « aucun des deux n'est mesuré », où le lire comme une
    confirmation inverse le sens.
    """
    plat = v.normaliser(note)
    if "temps reel" in plat or "constate" in plat:
        return MESUREE
    if "extrapol" in plat or "ratio" in plat:
        return EXTRAPOLEE
    return THEORIQUE


@dataclass
class Site:
    employeur: str
    site: str
    adresse: str
    stationnement: str
    km_aller: float = None
    # Le trafic n'est pas le même le samedi et en semaine : deux durées, deux
    # fiabilités. Un site qui n'en donne qu'une la porte dans les deux cases.
    minutes: dict = field(default_factory=dict)
    fiabilite: dict = field(default_factory=dict)
    stationnement_eur: float = None
    stationnement_incertain: bool = False
    stationnement_approx: str = ""
    note_duree: str = ""
    # Renseigné sur un site moyen : les sites réels qu'il résume.
    sites_couverts: list = field(default_factory=list)

    @property
    def libelle(self):
        return f"{self.employeur} — {self.site}" if self.site else self.employeur

    @property
    def trajet_connu(self):
        return self.km_aller is not None

    @staticmethod
    def _regime(jour):
        return "samedi" if jour is not None and jour.weekday() >= 5 else "semaine"

    def minutes_aller(self, jour=None):
        return self.minutes.get(self._regime(jour))

    def fiabilite_duree(self, jour=None):
        return self.fiabilite.get(self._regime(jour), THEORIQUE)

    def heures_trajet(self, jour=None):
        """Aller-retour, en heures. None tant que la durée n'est pas renseignée."""
        minutes = self.minutes_aller(jour)
        return None if minutes is None else 2 * minutes / 60.0


def site_moyen(sites, employeur):
    """Un site fictif, moyenne de plusieurs, pour une affectation qu'on subit.

    Quand c'est l'employeur qui décide sur quel site on travaille, chiffrer un
    créneau sur le meilleur des siens revient à promettre un optimum dont on
    n'a pas la main. La moyenne est le chiffre honnête ; l'écart entre le pire
    et le meilleur site dit de combien le réel s'en écartera.
    """
    connus = [s for s in sites if s.trajet_connu]
    if not connus:
        return None
    if len(connus) == 1:
        return connus[0]

    def _moyenne(valeurs):
        valeurs = [x for x in valeurs if x is not None]
        return sum(valeurs) / len(valeurs) if valeurs else None

    minutes, fiabilite = {}, {}
    for regime in ("samedi", "semaine"):
        minutes[regime] = _moyenne([s.minutes.get(regime) for s in connus])
        vues = {s.fiabilite.get(regime, THEORIQUE) for s in connus}
        # La moyenne ne vaut pas mieux que le moins sûr de ses termes.
        fiabilite[regime] = (MESUREE if vues == {MESUREE}
                             else THEORIQUE if THEORIQUE in vues else EXTRAPOLEE)
    stationnements = [s.stationnement_eur for s in connus]
    moyen = Site(
        employeur=employeur, site=f"moyenne des {len(connus)} sites",
        adresse="", stationnement="moyenne des sites",
        km_aller=_moyenne([s.km_aller for s in connus]),
        minutes=minutes, fiabilite=fiabilite,
        stationnement_eur=(None if any(x is None for x in stationnements)
                           else _moyenne(stationnements)),
        stationnement_incertain=any(s.stationnement_incertain for s in connus))
    moyen.sites_couverts = connus
    return moyen


@dataclass
class Trajets:
    sites: list
    cout_par_km: float
    repas_eur: float
    domicile: str = ""
    # Employeur normalisé -> site moyen, quand l'affectation ne se choisit pas.
    affectation_imposee: dict = field(default_factory=dict)
    alertes: list = field(default_factory=list)

    def site_a_simuler(self, site):
        """Le site à retenir pour chiffrer un créneau qu'on ne place pas soi-même."""
        return self.affectation_imposee.get(v.normaliser(site.employeur), site)

    def carburant(self, site):
        if not site.trajet_connu:
            return None
        return 2 * site.km_aller * self.cout_par_km


def charger_trajets(chemin):
    d = json.loads(Path(chemin).read_text(encoding="utf-8"))
    km = d.get("cout_kilometrique") or {}
    cout_km = km.get("cout_par_km_eur")
    if cout_km is None:
        cout_km = (km.get("consommation_l_100km", 0) / 100.0
                   * km.get("prix_litre_eur", 0))
    repas = d.get("repas", {}).get("montant_eur", 10.0)

    sites, alertes = [], []
    for brut in d.get("sites", []):
        stationnement = brut.get("stationnement") or "non précisé"
        plat = v.normaliser(stationnement)
        note = brut.get("note_duree") or ""
        # Une note peut couvrir deux régimes (« samedi … / en semaine … ») : on
        # la coupe pour ne pas prêter au samedi la fiabilité de la semaine.
        moities = v.normaliser(note).split("en semaine")
        commun = brut.get("duree_domicile_min_aller")
        minutes = {
            "samedi": brut.get("duree_domicile_min_aller_samedi", commun),
            "semaine": brut.get("duree_domicile_min_aller_semaine", commun),
        }
        explicite = brut.get("fiabilite_duree")
        fiabilite = {
            "samedi": explicite or _fiabilite(moities[0]),
            "semaine": explicite or _fiabilite(moities[-1]),
        }
        site = Site(
            employeur=brut.get("employeur", ""), site=brut.get("site") or "",
            adresse=brut.get("adresse", ""), stationnement=stationnement,
            km_aller=brut.get("distance_domicile_km_aller"),
            minutes=minutes, fiabilite=fiabilite, note_duree=note,
            stationnement_eur=brut.get("stationnement_eur"),
            stationnement_approx=brut.get("stationnement_note") or "")
        # Un montant donné vaut mieux qu'un adjectif : il lève l'incertitude.
        # Sans montant, « variable », « selon la place », « non précisé » ne se
        # chiffrent pas — le site est traité à part plutôt que crédité d'un zéro
        # qui fausserait son classement.
        if site.stationnement_eur is None:
            site.stationnement_incertain = any(
                mot in plat for mot in ("variable", "selon", "non precise",
                                        "incertain"))
            if "gratuit" in plat and not site.stationnement_incertain:
                site.stationnement_eur = 0.0
        sites.append(site)
        if not site.trajet_connu:
            alertes.append(f"{site.libelle} : distance domicile non renseignée — "
                           f"ni carburant ni rendement calculables pour ce site.")
        elif site.minutes_aller() is None:
            alertes.append(f"{site.libelle} : durée de trajet non renseignée — "
                           f"le revenu par heure passée n'est pas calculable.")
        if site.stationnement_eur is None and not site.stationnement_incertain:
            alertes.append(f"{site.libelle} : stationnement « {stationnement} », "
                           f"montant inconnu — non déduit.")
    # Par défaut, un employeur à plusieurs sites affecte lui-même : on ne
    # suppose pas que le créneau tombera sur le meilleur des siens. Un employeur
    # peut déclarer « affectation: choisie » pour reprendre la main.
    choisies = {v.normaliser(x) for x in d.get("employeurs_a_affectation_choisie", [])}
    moyens = {}
    par_employeur = {}
    for site in sites:
        par_employeur.setdefault(site.employeur, []).append(site)
    for employeur, liste in par_employeur.items():
        if len(liste) > 1 and v.normaliser(employeur) not in choisies:
            moyen = site_moyen(liste, employeur)
            if moyen is not None:
                moyens[v.normaliser(employeur)] = moyen
    return Trajets(sites=sites, cout_par_km=cout_km, repas_eur=repas,
                   domicile=(d.get("domicile") or {}).get("ville", ""),
                   affectation_imposee=moyens, alertes=alertes)


# --------------------------------------------------------------------------
# Une séance : une date, un site, un type de créneau
# --------------------------------------------------------------------------

@dataclass
class Seance:
    jour: date
    site: Site
    type_creneau: str
    gamelle: bool = True

    @property
    def titre(self):
        """Le titre que porterait l'événement d'agenda."""
        mot = MOT_DU_TYPE[self.type_creneau]
        return f"{self.mot_cle} {mot}"

    mot_cle: str = ""

    def evenement(self):
        return v.Evenement(
            identifiant=f"seance:{self.jour}:{self.site.libelle}:{self.type_creneau}",
            titre=self.titre,
            debut=datetime.combine(self.jour, datetime.min.time()),
            fin=datetime.combine(self.jour + timedelta(days=1), datetime.min.time()),
            journee_entiere=True, couleur=None, couleur_explicite=False)


def cout_seance(seance, trajets):
    """Renvoie (carburant, stationnement, repas, total, ce qui manque)."""
    site = seance.site
    carburant = trajets.carburant(site)
    stationnement = site.stationnement_eur
    repas = 0.0 if seance.gamelle else trajets.repas_eur
    manque = []
    if carburant is None:
        manque.append("distance")
    if stationnement is None:
        manque.append("stationnement variable" if site.stationnement_incertain
                      else "stationnement")
    total = (carburant or 0.0) + (stationnement or 0.0) + repas
    return carburant, stationnement, repas, total, manque


# --------------------------------------------------------------------------
# Ce que vaut une séance, et ce qu'elle prend
# --------------------------------------------------------------------------

# « Imagerie », « Clinique », « Hôpital » ne distinguent personne : deux
# employeurs différents les partagent. Les retenir dans l'appariement faisait
# passer « Résonance Imagerie » pour « Crystal Imagerie ».
MOTS_GENERIQUES = {"imagerie", "clinique", "hopital", "groupe", "centre",
                   "cabinet", "des", "de", "la", "le", "du", "ap-hp"}


def _distinctifs(nom):
    return {mot for mot in v.normaliser(nom).split() if mot not in MOTS_GENERIQUES}


def _regle_du_site(site, regles):
    """Relie un site de `trajets.json` à un employeur de la grille."""
    for r in regles:
        if v.normaliser(r.cle_employeur) == v.normaliser(site.employeur):
            return r
    jetons = _distinctifs(site.employeur)
    if not jetons:
        return None
    meilleur, score = None, 0
    for r in regles:
        commun = len(jetons & _distinctifs(r.cle_employeur))
        if commun > score:
            meilleur, score = r, commun
    return meilleur


def types_possibles(site, regle, jour):
    """Les créneaux que la grille autorise pour ce site, ce jour-là."""
    emp = regle.employeur or {}
    nom_jour = v.JOURS_FR[jour.weekday()]
    autorises = emp.get("jours_possibles")
    if autorises:
        ouverts = {v.normaliser(x).replace("-", "_").split("_")[0] for x in autorises}
        if nom_jour not in ouverts:
            return []
    impose = regle.restrictions.get(nom_jour)
    if impose:
        return [impose] if impose in regle.creneaux else []
    if v.normaliser(emp.get("type")).startswith("vacation_nuit"):
        return ["nuit"]
    possibles = [t for t in TYPES if t in regle.creneaux and t != "nuit"]
    duree = emp.get("duree_type")
    if duree:
        garde = set()
        for d in duree:
            plat = v.normaliser(d)
            garde |= {"matin", "apres_midi"} if "demi" in plat else {"journee"}
        possibles = [t for t in possibles if t in garde]
    return possibles


def valeur_seance(seance, grille, regles, trajets, annee, mois):
    """Chiffre une séance seule : ce qu'elle rapporte, coûte et prend.

    Le revenu passe par `vacations.analyser` — même identification, même tarif —
    pour qu'une séance simulée vaille exactement ce qu'elle vaudra une fois posée.
    """
    a = v.analyser(grille, [seance.evenement()], annee, mois)
    if not a["vacations"]:
        return None
    vac = a["vacations"][0]
    carburant, stationnement, repas, cout, manque = cout_seance(seance, trajets)
    trajet_h = seance.site.heures_trajet(seance.jour)
    net = vac["montant"]
    return {
        "seance": seance, "vacation": vac,
        "heures": vac["heures"], "creneaux": vac["creneaux"],
        "net": net, "mensualise": vac["mode"] == "mensualisé",
        "carburant": carburant, "stationnement": stationnement, "repas": repas,
        "cout": cout, "manque": manque,
        "net_apres_cout": None if net is None else net - cout,
        "heures_trajet": trajet_h,
        "heures_passees": None if trajet_h is None else vac["heures"] + trajet_h,
    }


def rentabilite(grille, trajets, annee, mois, gamelle=True):
    """Une ligne par site et par type de séance, du plus rentable au moins."""
    regles = v.construire_regles(grille)
    lignes = []
    # Les jours de référence sont pris du lundi au dimanche : ainsi une nuit se
    # chiffre sur un jour ouvré, et non au tarif majoré d'un dimanche parce que
    # le mois commençait un dimanche.
    reperes = sorted((date(annee, mois, 1) + timedelta(days=i) for i in range(14)),
                     key=lambda d: (d.weekday(), d))
    for site in trajets.sites:
        regle = _regle_du_site(site, regles)
        if regle is None or v.est_mensualise(regle.employeur):
            continue
        vus = set()
        for jour in reperes:
            for type_creneau in types_possibles(site, regle, jour):
                if type_creneau in vus:
                    continue
                seance = Seance(jour, site, type_creneau, gamelle,
                                mot_cle=(regle.mots_cles or [""])[0])
                valeur = valeur_seance(seance, grille, regles, trajets, annee, mois)
                if valeur is None or valeur["net"] is None:
                    continue
                vus.add(type_creneau)
                lignes.append({
                    "site": site, "type": type_creneau, "regle": regle,
                    "heures": valeur["heures"], "net": valeur["net"],
                    "cout": valeur["cout"], "manque": valeur["manque"],
                    "carburant": valeur["carburant"],
                    "stationnement": valeur["stationnement"],
                    "repas": valeur["repas"],
                    "net_apres_cout": valeur["net_apres_cout"],
                    "heures_trajet": valeur["heures_trajet"],
                    "fiabilite": site.fiabilite_duree(seance.jour),
                    "par_heure_travaillee": valeur["net_apres_cout"] / valeur["heures"],
                    "par_heure_passee": (
                        None if valeur["heures_passees"] is None
                        else valeur["net_apres_cout"] / valeur["heures_passees"]),
                })
    # Les sites dont le trajet ou le stationnement est inconnu ne sont pas
    # comparables aux autres : ils sont classés à part, pas noyés dans le tri.
    surs = [x for x in lignes if not x["manque"]]
    incertains = [x for x in lignes if x["manque"]]
    surs.sort(key=lambda x: -x["par_heure_travaillee"])
    incertains.sort(key=lambda x: -x["par_heure_travaillee"])
    return surs, incertains


# --------------------------------------------------------------------------
# Ce que coûte le planning déjà posé
# --------------------------------------------------------------------------

MATIN = (8, 13)          # fenêtres de référence, pour dire si une demi-journée
APRES_MIDI = (13, 19)    # est prise — pas des horaires de travail


def _occupe(creneaux, jour, fenetre):
    debut = datetime.combine(jour, datetime.min.time()).replace(hour=fenetre[0])
    fin = datetime.combine(jour, datetime.min.time()).replace(hour=fenetre[1])
    return any(min(f, fin) > max(d, debut) for d, f in creneaux)


# « sur », « seine », « la »… ne désignent aucun lieu à eux seuls.
MOTS_DE_LIAISON = {"sur", "sous", "la", "le", "les", "de", "du", "des", "en",
                   "seine", "saint", "st"}


def _jetons_de_site(site):
    return {m for m in re.split(r"[^a-z0-9]+", v.normaliser(site.site))
            if m and m not in MOTS_DE_LIAISON}


def site_du_titre(titre, sites):
    """Retrouve le site nommé dans un titre d'agenda — « Crystal Colombes ».

    Deux pièges : « Colombes » est contenu dans « La Garenne-Colombes », et
    « La Garenne » ne contient pas « Colombes ». On cherche donc d'abord les
    jetons qui ne désignent qu'un seul site (« garenne », « asnieres »), puis
    les jetons partagés — auquel cas c'est le site au nom le plus court qui
    l'emporte, celui dont c'est le nom entier.
    """
    plat = v.normaliser(titre)
    jetons = {s.libelle: _jetons_de_site(s) for s in sites}
    compte = {}
    for ensemble in jetons.values():
        for mot in ensemble:
            compte[mot] = compte.get(mot, 0) + 1

    for distinctifs in (True, False):
        trouves = []
        for site in sites:
            mots = [m for m in jetons[site.libelle]
                    if (compte[m] == 1) == distinctifs]
            for mot in mots:
                if re.search(rf"(?<![a-z0-9]){re.escape(mot)}(?![a-z0-9])", plat):
                    trouves.append((len(jetons[site.libelle]), -len(mot), site))
        if trouves:
            return min(trouves, key=lambda x: x[:2])[2]
    return None


def sites_par_employeur(trajets):
    par = {}
    for site in trajets.sites:
        par.setdefault(v.normaliser(site.employeur), []).append(site)
    return par


def couts_du_planning(analyse, trajets):
    """Un aller-retour par jour travaillé, au site de l'employeur du jour.

    Un employeur à plusieurs sites (Crystal) ne dit pas dans l'agenda lequel :
    le coût est alors donné en fourchette, et le fait est signalé.
    """
    par_employeur = sites_par_employeur(trajets)
    total, trajet_h, details, inconnus, imprecis = 0.0, 0.0, {}, [], []
    for vac in analyse["vacations"]:
        if not vac["heures_mois"]:
            continue
        nom = v.normaliser(vac["regle"].cle_employeur)
        candidats = par_employeur.get(nom)
        if not candidats:
            jetons = _distinctifs(nom)
            meilleur, score = None, 0
            for cle, liste in par_employeur.items():
                commun = len(jetons & _distinctifs(cle))
                if commun > score:
                    meilleur, score = liste, commun
            candidats = meilleur or []
        if not candidats:
            inconnus.append(vac["regle"].libelle)
            continue
        chiffrables = [s for s in candidats if s.trajet_connu]
        if not chiffrables:
            inconnus.append(candidats[0].libelle)
            continue
        # Le titre décide quand il nomme le site. Sinon on prend le plus proche,
        # ce qui est une hypothèse basse — et qui se dit.
        nomme = site_du_titre(vac["evenement"].titre, chiffrables)
        moyen = trajets.affectation_imposee.get(v.normaliser(chiffrables[0].employeur))
        if nomme is None and len(chiffrables) > 1:
            imprecis.append(vac["evenement"].titre)
        for jour in vac["jours"]:
            if not (analyse["debut_mois"] <= jour <= analyse["fin_mois"]):
                continue
            site = nomme or moyen or min(chiffrables, key=lambda s: s.km_aller)
            cout = trajets.carburant(site) + (site.stationnement_eur or 0.0)
            total += cout
            heures = site.heures_trajet(jour)
            if heures:
                trajet_h += heures
            bloc = details.setdefault(site.libelle, {"jours": 0, "cout": 0.0})
            bloc["jours"] += 1
            bloc["cout"] += cout
    return {"total": total, "heures_trajet": trajet_h, "par_site": details,
            "sites_inconnus": sorted(set(inconnus)),
            "titres_sans_site": sorted(set(imprecis))}


# --------------------------------------------------------------------------
# Les créneaux qu'il reste à prendre
# --------------------------------------------------------------------------

def jours_douteux(analyse, regles):
    """Les jours portant un événement qui ressemble à un créneau non lu.

    Un titre mal formé — « 8h19h » pour « 8-19h » — n'est reconnu par personne.
    Le jour paraît libre alors qu'il ne l'est pas, et le simulateur proposerait
    d'y poser une vacation par-dessus une autre. On l'écarte plutôt que de
    proposer un conflit.
    """
    couleurs = {c for r in regles for c in r.couleurs}
    douteux = {}
    for ev in analyse["autres"]:
        if (ev.couleur in couleurs and re.search(r"\d\s*[hH]", ev.titre)
                and not v.lire_plage(ev.titre)[0]):
            for jour in ev.jours:
                douteux[jour] = ev.titre
    return douteux


def creneaux_libres(analyse, douteux=()):
    """Pour chaque jour du mois, les demi-journées qu'aucun créneau n'occupe."""
    pris = [c for vac in analyse["vacations"] for c in vac["creneaux"]]
    libres = {}
    jour = analyse["debut_mois"]
    while jour <= analyse["fin_mois"]:
        etat = {"matin": not _occupe(pris, jour, MATIN) and jour not in douteux,
                "apres_midi": not _occupe(pris, jour, APRES_MIDI) and jour not in douteux}
        if etat["matin"] or etat["apres_midi"]:
            libres[jour] = etat
        jour += timedelta(days=1)
    return libres


def candidats(grille, trajets, analyse, annee, mois, gamelle=True,
              respecter_repos=True):
    """Toutes les séances qu'on pourrait ajouter, chiffrées une par une.

    Une séance qui, à elle seule, laisse moins de onze heures de repos avec le
    planning déjà posé n'est pas une option : la proposer reviendrait à
    recommander quelque chose d'illégal. Elle est écartée, et comptée.
    """
    regles = v.construire_regles(grille)
    douteux = jours_douteux(analyse, regles)
    libres = creneaux_libres(analyse, douteux)
    _bidon = type("R", (), {"libelle": "planning"})()
    fixes = [{"creneaux": [c for vac in analyse["vacations"] for c in vac["creneaux"]],
              "regle": _bidon}]
    repos_de_base = len(v.repos_insuffisants(fixes, analyse["repos_minimum"]))
    ecartes = []
    trouves = []
    vus_par_jour = set()
    for jour, etat in libres.items():
        for brut in trajets.sites:
            site = trajets.site_a_simuler(brut)
            if (jour, site.libelle) in vus_par_jour and site.sites_couverts:
                continue
            vus_par_jour.add((jour, site.libelle))
            regle = _regle_du_site(site, regles)
            if regle is None or v.est_mensualise(regle.employeur):
                continue
            for type_creneau in types_possibles(site, regle, jour):
                if type_creneau == "journee" and not (etat["matin"] and etat["apres_midi"]):
                    continue
                if type_creneau == "matin" and not etat["matin"]:
                    continue
                if type_creneau == "apres_midi" and not etat["apres_midi"]:
                    continue
                seance = Seance(jour, site, type_creneau, gamelle,
                                mot_cle=(regle.mots_cles or [""])[0])
                valeur = valeur_seance(seance, grille, regles, trajets, annee, mois)
                if not (valeur and valeur["net"]):
                    continue
                if respecter_repos:
                    avec = fixes + [{"creneaux": valeur["creneaux"], "regle": _bidon}]
                    manques = v.repos_insuffisants(avec, analyse["repos_minimum"])
                    if len(manques) > repos_de_base:
                        ecartes.append((seance, min(m["heures"] for m in manques)))
                        continue
                valeur["jour"] = jour
                valeur["semaine"] = jour.isocalendar()[:2]
                trouves.append(valeur)
    return trouves, ecartes, douteux


def _pareto(valeurs):
    """Deux sites au même créneau : on garde ceux qu'aucun autre ne domine.

    Dominé = rapporte moins net *et* prend plus de temps. Le reste est un
    arbitrage réel, qu'on laisse à l'optimisation.
    """
    garde = []
    for x in valeurs:
        net_x = x["net_apres_cout"] or 0.0
        temps_x = x["heures_passees"] if x["heures_passees"] is not None else x["heures"]
        domine = False
        for y in valeurs:
            if y is x:
                continue
            net_y = y["net_apres_cout"] or 0.0
            temps_y = y["heures_passees"] if y["heures_passees"] is not None else y["heures"]
            if net_y >= net_x and temps_y <= temps_x and (net_y > net_x or temps_y < temps_x):
                domine = True
                break
        if not domine:
            garde.append(x)
    return garde


def combinaisons_par_semaine(candidats_, analyse, plafond=True, maximum=40000):
    """Les paquets de séances possibles, semaine par semaine.

    Découper par semaine tient l'énumération dans des tailles raisonnables : le
    plafond hebdomadaire est la seule contrainte qui lie des jours entre eux.
    """
    par_semaine = {}
    for x in candidats_:
        par_semaine.setdefault(x["semaine"], []).append(x)

    resultats = {}
    for semaine, valeurs in par_semaine.items():
        par_jour = {}
        for x in valeurs:
            par_jour.setdefault(x["jour"], []).append(x)
        # Un jour, un choix : rien, ou une des séances non dominées.
        options = []
        for jour in sorted(par_jour):
            options.append([None] + _pareto(par_jour[jour]))
        total = 1
        for o in options:
            total *= len(o)
        if total > maximum:                       # garde-fou, jamais atteint ici
            options = [o[:3] for o in options]
        base = analyse["semaines"].get(semaine, {"heures": 0.0})["heures"]
        paquets = []
        for choix in itertools.product(*options):
            retenues = [x for x in choix if x is not None]
            heures = sum(x["heures"] for x in retenues)
            if plafond and base + heures > analyse["plafond"]:
                continue
            paquets.append({
                "seances": retenues,
                "net": sum(x["net"] for x in retenues),
                "cout": sum(x["cout"] for x in retenues),
                "net_apres_cout": sum(x["net_apres_cout"] for x in retenues),
                "heures": heures,
                "temps": sum(x["heures_passees"] if x["heures_passees"] is not None
                             else x["heures"] for x in retenues),
                "heures_semaine": base + heures,
            })
        resultats[semaine] = paquets
    return resultats


# --------------------------------------------------------------------------
# Les trois optimisations
# --------------------------------------------------------------------------

def _assembler(paquets_par_semaine, choisir):
    """Combine un paquet par semaine — les semaines sont indépendantes."""
    retenu = {}
    for semaine, paquets in paquets_par_semaine.items():
        retenu[semaine] = choisir(paquets) if paquets else None
    return [x for x in retenu.values() if x]


def optimiser_revenu(paquets_par_semaine):
    """Le plus d'argent, sans regarder le temps."""
    return _assembler(paquets_par_semaine,
                      lambda p: max(p, key=lambda x: x["net_apres_cout"]))


def optimiser_rendement(paquets_par_semaine, base_net=0.0, base_temps=0.0,
                        iterations=24):
    """Le meilleur euro par heure passée, trajet compris.

    Maximiser un rapport de sommes ne se fait pas semaine par semaine : on passe
    par le paramètre λ (Dinkelbach). À λ fixé, maximiser net − λ·temps *est*
    séparable ; le λ qui annule ce maximum est le rendement optimal. Quelques
    itérations suffisent, et le résultat est exact — pas une heuristique.
    """
    lam = 0.0
    choix = []
    for _ in range(iterations):
        choix = _assembler(
            paquets_par_semaine,
            lambda p: max(p, key=lambda x: x["net_apres_cout"] - lam * x["temps"]))
        net = base_net + sum(x["net_apres_cout"] for x in choix)
        temps = base_temps + sum(x["temps"] for x in choix)
        nouveau = net / temps if temps else 0.0
        if abs(nouveau - lam) < 1e-9:
            break
        lam = nouveau
    return choix


def optimiser_cible(paquets_par_semaine, cible, base_net=0.0, pas=5.0):
    """Atteindre la cible en y passant le moins de temps possible.

    Sac à dos sur les semaines : pour chaque niveau de revenu atteignable, on
    retient le temps le plus court qui y mène. Le revenu est discrétisé au pas
    de quelques euros — assez fin pour que le classement ne bouge pas.
    """
    manquant = max(0.0, cible - base_net)
    etats = {0: (0.0, [])}                    # revenu arrondi -> (temps, choix)
    for semaine, paquets in paquets_par_semaine.items():
        if not paquets:
            continue
        suivant = {}
        for niveau, (temps, choix) in etats.items():
            for p in paquets:
                cle = niveau + int(round(p["net_apres_cout"] / pas))
                candidat = (temps + p["temps"], choix + [p])
                if cle not in suivant or candidat[0] < suivant[cle][0]:
                    suivant[cle] = candidat
        etats = suivant
    seuil = int(round(manquant / pas))
    atteints = [(niveau, temps, choix) for niveau, (temps, choix) in etats.items()
                if niveau >= seuil]
    if not atteints:
        return None
    return min(atteints, key=lambda x: (x[1], -x[0]))[2]


# --------------------------------------------------------------------------
# Évaluer un scénario pour de bon
# --------------------------------------------------------------------------

def fourchette_affectation(seances, trajets):
    """De combien le résultat s'écarterait si tous les créneaux tombaient sur le
    pire, puis sur le meilleur des sites de leur employeur."""
    pire = meilleur = 0.0
    concernees = 0
    for seance in seances:
        couverts = seance.site.sites_couverts
        if not couverts:
            continue
        concernees += 1
        base = trajets.carburant(seance.site) + (seance.site.stationnement_eur or 0.0)
        couts = [trajets.carburant(s) + (s.stationnement_eur or 0.0) for s in couverts]
        pire += base - max(couts)          # coût plus élevé : net plus bas
        meilleur += base - min(couts)
    return {"seances": concernees, "pire": pire, "meilleur": meilleur}


def evaluer(grille, evenements, trajets, annee, mois, seances=(), feries=()):
    """Le mois complet, planning fixe et séances ajoutées confondus.

    L'analyse repasse par `vacations.analyser` : c'est elle qui fait foi pour
    le revenu, le plafond et le repos. Le simulateur n'ajoute que l'argent et le
    temps du déplacement.
    """
    seances = list(seances)
    analyse = v.analyser(grille, list(evenements) + [s.evenement() for s in seances],
                         annee, mois, feries)
    couts = couts_du_planning(analyse, trajets)
    net = sum(b["montant"] for b in analyse["par_employeur"].values()
              if b["montant"] is not None)
    heures = sum(b["heures"] for b in analyse["par_employeur"].values())
    repas = sum(0.0 if s.gamelle else trajets.repas_eur for s in seances)
    temps = heures + couts["heures_trajet"]
    return {
        "analyse": analyse, "seances": seances,
        "net": net, "cout_deplacement": couts["total"], "cout_repas": repas,
        "cout": couts["total"] + repas,
        "net_apres_cout": net - couts["total"] - repas,
        "heures": heures, "heures_trajet": couts["heures_trajet"],
        "temps": temps,
        "par_heure_travaillee": (net - couts["total"] - repas) / heures if heures else 0.0,
        "par_heure_passee": (net - couts["total"] - repas) / temps if temps else 0.0,
        "couts_par_site": couts["par_site"], "sites_inconnus": couts["sites_inconnus"],
        "titres_sans_site": couts["titres_sans_site"],
        "fourchette": fourchette_affectation(seances, trajets),
        "depassements": [s for s in analyse["semaines"].values() if s["depassement"]],
        "repos": analyse["repos_insuffisants"],
        "conflits": analyse["chevauchements"]["entre_vacations"],
    }


def scenarios(grille, evenements, trajets, annee, mois, cible=None,
              gamelle=True, plafond=True, feries=()):
    """Le mois nu, puis les trois optimisations, prêts à être comparés."""
    nu = evaluer(grille, evenements, trajets, annee, mois, (), feries)
    liste, ecartes, douteux = candidats(grille, trajets, nu["analyse"], annee,
                                        mois, gamelle)
    paquets = combinaisons_par_semaine(liste, nu["analyse"], plafond)

    propositions = [("Planning nu", [], "le mois tel qu'il est aujourd'hui")]
    propositions.append(("Revenu maximal",
                         [p for p in optimiser_revenu(paquets)],
                         "le plus d'argent, sans regarder le temps"))
    propositions.append(("Rendement maximal",
                         optimiser_rendement(paquets, nu["net_apres_cout"], nu["temps"]),
                         "le meilleur euro par heure passée, trajet compris"))
    if cible is not None:
        choix = optimiser_cible(paquets, cible, nu["net_apres_cout"])
        propositions.append((
            f"Cible {v.format_euros(cible)}", choix,
            "la cible atteinte en y passant le moins de temps"
            if choix is not None else "hors d'atteinte avec les créneaux libres"))

    resultats = []
    for nom, paquets_choisis, note in propositions:
        seances = ([x["seance"] for p in paquets_choisis for x in p["seances"]]
                   if paquets_choisis else [])
        evaluation = evaluer(grille, evenements, trajets, annee, mois, seances, feries)
        evaluation.update({"nom": nom, "note": note,
                           "impossible": paquets_choisis is None})
        resultats.append(evaluation)
    return {"nu": nu, "candidats": liste, "scenarios": resultats,
            "ecartes_repos": ecartes, "jours_douteux": douteux, "cible": cible,
            "libres": creneaux_libres(nu["analyse"], douteux)}


# --------------------------------------------------------------------------
# Rapport texte
# --------------------------------------------------------------------------

def _eur(x):
    return "—" if x is None else v.format_euros(x)


def rapport_rentabilite(surs, incertains, trajets):
    lignes = [v._titre("Rentabilité par site et par type de séance")]
    if not surs and not incertains:
        return "\n".join(lignes + ["  aucun site chiffrable."]) + "\n"

    colonnes = ("Site", "Séance", "Heures", "Net", "Coûts", "Net réel",
                "€/h trav.", "€/h passée")
    gabarit = "  {:<34}{:<11}{:>7}{:>10}{:>9}{:>10}{:>11}{:>12}"
    for titre, groupe in (("Chiffrables", surs),
                          ("Trajet ou stationnement inconnu", incertains)):
        if not groupe:
            continue
        lignes += [f"\n  {titre}", gabarit.format(*colonnes)]
        for x in groupe:
            passee = ("—" if x["par_heure_passee"] is None
                      else f"{x['par_heure_passee']:.2f} €".replace(".", ","))
            partiel = bool(x["manque"])
            lignes.append(gabarit.format(
                x["site"].libelle[:33], MOT_DU_TYPE[x["type"]],
                v.format_heures(x["heures"]), _eur(x["net"]),
                "—" if partiel else _eur(x["cout"]),
                "—" if partiel else _eur(x["net_apres_cout"]),
                ("—" if partiel else
                 f"{x['par_heure_travaillee']:.2f} €".replace(".", ",")), passee))
            if x["manque"]:
                lignes.append(f"  {'':<34}manque : {', '.join(x['manque'])}")
    if trajets.alertes:
        lignes.append("\n  À compléter :")
        for a in dict.fromkeys(trajets.alertes):
            lignes.append(f"    · {a}")
    return "\n".join(lignes) + "\n"


def rapport_scenarios(resultat, plafond):
    lignes = [v._titre("Scénarios")]
    colonnes = resultat["scenarios"]
    sans_trajet = not any(x["heures_trajet"] for x in colonnes)
    largeur = 21
    def ligne(intitule, valeurs):
        return (f"  {intitule:<22}"
                + "".join(f"{x:>{largeur}}" for x in valeurs))

    lignes.append(ligne("", [s["nom"][:largeur - 1] for s in colonnes]))
    lignes.append("  " + "─" * (22 + largeur * len(colonnes) - 2))
    lignes.append(ligne("Séances ajoutées", [str(len(s["seances"])) for s in colonnes]))
    lignes.append(ligne("Net encaissé", [_eur(s["net"]) for s in colonnes]))
    lignes.append(ligne("Coûts", [_eur(-s["cout"]) for s in colonnes]))
    lignes.append(ligne("Net après coûts", [_eur(s["net_apres_cout"]) for s in colonnes]))
    if any(s["fourchette"]["seances"] for s in colonnes):
        lignes.append(ligne("  selon l'affectation", [
            "—" if not s["fourchette"]["seances"] else
            f"{_eur(s['net_apres_cout'] + s['fourchette']['pire'])}"
            for s in colonnes]))
        lignes.append(ligne("  … à", [
            "—" if not s["fourchette"]["seances"] else
            f"{_eur(s['net_apres_cout'] + s['fourchette']['meilleur'])}"
            for s in colonnes]))
    lignes.append(ligne("Heures travaillées",
                        [v.format_heures(s["heures"]) for s in colonnes]))
    lignes.append(ligne("Heures de trajet",
                        [v.format_heures(s["heures_trajet"]) for s in colonnes]))
    lignes.append(ligne("Temps total", [v.format_heures(s["temps"]) for s in colonnes]))
    lignes.append(ligne("€ / h travaillée",
                        [f"{s['par_heure_travaillee']:.2f} €" for s in colonnes]))
    lignes.append(ligne("€ / h passée",
                        [f"{s['par_heure_passee']:.2f} €" for s in colonnes]))
    lignes.append(ligne(f"Semaines > {v.format_heures(plafond)}",
                        [str(len(s["depassements"])) for s in colonnes]))
    lignes.append(ligne("Repos < 11 h", [str(len(s["repos"])) for s in colonnes]))
    lignes.append(ligne("Chevauchements", [str(len(s["conflits"])) for s in colonnes]))

    for s in colonnes:
        if s.get("impossible"):
            lignes.append(f"\n  ⚠ {s['nom']} : hors d'atteinte. Le maximum que "
                          f"permettent les créneaux libres de ce mois est "
                          f"{_eur(max(x['net_apres_cout'] for x in colonnes))}, "
                          f"soit {_eur(resultat['cible'] - max(x['net_apres_cout'] for x in colonnes))} "
                          f"de moins que la cible. La colonne ci-dessus reprend "
                          f"donc le planning nu.")
            continue
        if not s["seances"]:
            continue
        lignes.append(f"\n  {s['nom']} — {s['note']}")
        for seance in sorted(s["seances"], key=lambda x: x.jour):
            lignes.append(f"    {v.format_jour(seance.jour)}  "
                          f"{seance.site.libelle} · {MOT_DU_TYPE[seance.type_creneau]}")

    lignes.append(v._titre("Ce qui pèse sur ces résultats"))
    if sans_trajet:
        lignes.append(
            "  ⚠ Aucune distance domicile-site n'est renseignée : le carburant, "
            "le stationnement\n    et le temps de trajet valent zéro. Les deux "
            "optimisations donnent donc le même\n    résultat, et le site retenu "
            "pour Crystal est arbitraire — c'est le premier de la\n    liste, pas "
            "le plus proche. Renseigner « distance_domicile_km_aller » et\n"
            "    « duree_domicile_min_aller » dans trajets.json les départagera.")
    imposees = {s.site.libelle for x in resultat["scenarios"]
                for s in x["seances"] if s.site.sites_couverts}
    if imposees:
        lignes.append(
            "  ⚠ Les créneaux d'un employeur qui affecte lui-même ses sites sont "
            "chiffrés\n    sur la MOYENNE de ses sites, pas sur le meilleur : "
            + ", ".join(sorted(imposees)) + ".\n"
            "    Les deux lignes « selon l'affectation » donnent ce que le mois "
            "vaudrait si tous\n    ces créneaux tombaient sur le site le plus "
            "coûteux, puis sur le moins coûteux.\n    L'écart ne dépend pas de "
            "toi.")
    sans_site = resultat["nu"]["titres_sans_site"]
    if sans_site:
        lignes.append(
            f"  ⚠ {len(sans_site)} titre(s) d'agenda ne nomment pas leur site alors "
            f"que l'employeur en a plusieurs :\n    "
            + ", ".join(f"« {t} »" for t in sans_site)
            + "\n    La moyenne des sites de l'employeur a été retenue. Écrire "
              "« Crystal Colombes\n    journée » plutôt que « Crystal journée » "
              "donnera le coût réel — utile a posteriori,\n    une fois "
              "l'affectation connue.")
    for jour, titre in sorted(resultat["jours_douteux"].items()):
        lignes.append(f"  ⚠ {v.format_jour(jour)} écarté des jours libres : "
                      f"« {titre} » ressemble à un créneau dont le titre est mal "
                      f"formé.\n    Corriger l'agenda rendra ce jour lisible.")
    if resultat["ecartes_repos"]:
        lignes.append(f"  · {len(resultat['ecartes_repos'])} séances possibles "
                      f"écartées : elles laissaient moins de 11 h de repos avec "
                      f"le planning déjà posé.")
        for seance, heures in sorted(resultat["ecartes_repos"],
                                     key=lambda x: x[0].jour)[:6]:
            lignes.append(f"    {v.format_jour(seance.jour)} "
                          f"{seance.site.libelle} · "
                          f"{MOT_DU_TYPE[seance.type_creneau]} "
                          f"({v.format_heures(heures)} de repos seulement)")
    libres = resultat["libres"]
    entiers = sorted(j for j, e in libres.items() if e["matin"] and e["apres_midi"])
    demis = sorted(j for j, e in libres.items() if e["matin"] != e["apres_midi"])
    lignes.append(f"  · {len(entiers)} jours entièrement libres : "
                  + ", ".join(f"{j:%d/%m}" for j in entiers))
    if demis:
        lignes.append(f"  · {len(demis)} demi-journées libres : "
                      + ", ".join(
                          f"{j:%d/%m} ({'matin' if libres[j]['matin'] else 'aprèm'})"
                          for j in demis))
    return "\n".join(lignes) + "\n"


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--grille", type=Path, default=v.GRILLE)
    p.add_argument("--evenements", type=Path, default=v.EVENEMENTS)
    p.add_argument("--trajets", type=Path, default=TRAJETS)
    p.add_argument("--mois", default=None)
    p.add_argument("--cible", type=float, default=None,
                   help="revenu net visé pour le mois, en euros")
    p.add_argument("--sans-gamelle", action="store_true",
                   help="compter un repas payé à chaque séance ajoutée")
    p.add_argument("--sans-plafond", action="store_true",
                   help="laisser les scénarios dépasser les 48 h hebdomadaires")
    p.add_argument("--rentabilite", action="store_true",
                   help="n'afficher que le classement des sites")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    args.mois = args.mois or date.today().strftime("%Y-%m")
    annee, mois = (int(x) for x in args.mois.split("-"))

    grille = json.loads(args.grille.read_text(encoding="utf-8"))
    trajets = charger_trajets(args.trajets)
    gamelle = not args.sans_gamelle

    surs, incertains = rentabilite(grille, trajets, annee, mois, gamelle)
    if args.rentabilite:
        print(rapport_rentabilite(surs, incertains, trajets))
        return

    evenements = v.charger_evenements(args.evenements,
                                      grille.get("couleur_agenda_par_defaut"))
    resultat = scenarios(grille, evenements, trajets, annee, mois, args.cible,
                         gamelle, not args.sans_plafond)
    if args.json:
        print(json.dumps({
            "mois": args.mois,
            "rentabilite": [{"site": x["site"].libelle, "type": x["type"],
                             "net_apres_cout": round(x["net_apres_cout"], 2),
                             "par_heure_travaillee": round(x["par_heure_travaillee"], 2),
                             "par_heure_passee": (None if x["par_heure_passee"] is None
                                                  else round(x["par_heure_passee"], 2)),
                             "manque": x["manque"]} for x in surs + incertains],
            "scenarios": [{
                "nom": s["nom"], "net": round(s["net"], 2),
                "cout": round(s["cout"], 2),
                "net_apres_cout": round(s["net_apres_cout"], 2),
                "heures": round(s["heures"], 2), "temps": round(s["temps"], 2),
                "par_heure_passee": round(s["par_heure_passee"], 2),
                "seances": [{"jour": x.jour.isoformat(), "site": x.site.libelle,
                             "type": x.type_creneau} for x in s["seances"]],
                "depassements": len(s["depassements"]),
            } for s in resultat["scenarios"]],
        }, ensure_ascii=False, indent=2))
        return

    print(rapport_rentabilite(surs, incertains, trajets))
    print(rapport_scenarios(resultat, resultat["nu"]["analyse"]["plafond"]))


if __name__ == "__main__":
    main()
