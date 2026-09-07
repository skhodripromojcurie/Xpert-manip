#!/usr/bin/env python3
"""Contrôles de outils/vacations.py.

Les chiffres attendus sont calculés à la main sur les fac-similés de
`outils/exemples/`, qui n'ont rien de personnel. Ce sont eux qui protègent les
règles fragiles : un titre-horaire qui vaut par jour et non par bloc, une nuit
qui bascule d'un jour à l'autre, une astreinte qui ne pèse pas sur le plafond.

    python3 outils/tests_vacations.py
"""
import json
import re
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

import rapport_html
import vacations as v

EXEMPLES = Path(__file__).resolve().parent / "exemples"


class LectureTitre(unittest.TestCase):
    def test_plages_francaises(self):
        for titre, attendu in (("8-19h", (8, 0, 19, 0)),
                               ("8h30-12h30", (8, 30, 12, 30)),
                               ("21h-7h", (21, 0, 7, 0)),
                               ("14-19h", (14, 0, 19, 0)),
                               ("de 8h à 12h30", (8, 0, 12, 30)),
                               ("Alta 15h-19h", (15, 0, 19, 0))):
            self.assertEqual(v.lire_plage(titre)[0], attendu, titre)

    def test_une_date_n_est_pas_un_horaire(self):
        """Sans « h » ni « : », « 2026-09-02 » se lirait comme 9h→2h."""
        self.assertIsNone(v.lire_plage("réunion 2026-09-02")[0])
        self.assertIsNone(v.lire_plage("Encombrants")[0])

    def test_une_heure_seule_n_est_pas_une_plage(self):
        self.assertIsNone(v.lire_plage("Rentrée 9h30")[0])

    def test_titre_horaire_seul(self):
        self.assertTrue(v.titre_horaire_seul("8-19h"))
        self.assertFalse(v.titre_horaire_seul("Rigel 21h-7h"))
        self.assertFalse(v.titre_horaire_seul("Rentrée 9h30"))

    def test_creneau_coupe(self):
        self.assertEqual(len(v.lire_plages("9h-13h, 14h-18h")), 2)

    def test_mot_cle_duree(self):
        self.assertEqual(v.mot_cle_duree("Vega aprèm"), "apres_midi")
        self.assertEqual(v.mot_cle_duree("Vega journée"), "journee")
        self.assertIsNone(v.mot_cle_duree("Vega"))

    def test_date_dans_une_note(self):
        self.assertEqual(v.lire_date_fr("commence le 15 septembre 2026"),
                         date(2026, 9, 15))


class LectureGrille(unittest.TestCase):
    def test_mot_cle_avec_commentaire(self):
        """« Altair (…, ex: Alta) » : la valeur, pas le commentaire."""
        mots = v._mots_cles({"mot_cle": "Altair (peut apparaitre tronque, ex: Alta)"})
        self.assertEqual(mots, ["alta"])   # « alta » couvre déjà « altair »

    def test_placeholder_n_est_pas_un_mot_cle(self):
        self.assertEqual(v._mots_cles({"mot_cle": "a confirmer - aucune vacation"}), [])

    def test_duree_par_defaut_deduite_de_la_prose(self):
        self.assertEqual(
            v._defaut_duree({"duree_par_defaut": "journee entiere si rien precise"}),
            "journee")
        self.assertEqual(
            v._defaut_duree({"duree_par_defaut": "samedi matin par defaut, matin/journee"}),
            "matin")
        self.assertIsNone(v._defaut_duree({"duree_par_defaut": "a definir"}))


class Decoupage(unittest.TestCase):
    def test_nuit_a_cheval_sur_deux_jours(self):
        debut, fin = v.poser(date(2026, 9, 17), (21, 0, 7, 0))
        self.assertEqual(v.heures(debut, fin), 10.0)
        morceaux = v.decouper(debut, fin)
        self.assertEqual([m[0].date() for m in morceaux],
                         [date(2026, 9, 17), date(2026, 9, 18)])

    def test_heures_de_nuit(self):
        debut, fin = v.poser(date(2026, 9, 17), (21, 0, 7, 0))
        cat = {}
        for a, b in v.decouper(debut, fin):
            for nom, h in v.classer(a, b, (21, 0, 7, 0), set()):
                cat[nom] = cat.get(nom, 0) + h
        self.assertEqual(cat, {"nuit": 10.0})

    def test_dimanche_prime_sur_la_nuit(self):
        debut, fin = v.poser(date(2026, 9, 20), (21, 0, 7, 0))  # dimanche → lundi
        cat = {}
        for a, b in v.decouper(debut, fin):
            for nom, h in v.classer(a, b, (21, 0, 7, 0), set()):
                cat[nom] = cat.get(nom, 0) + h
        self.assertEqual(cat, {"dimanche_ferie": 3.0, "nuit": 7.0})


class SurLesExemples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        grille = json.loads((EXEMPLES / "grille.exemple.json").read_text(encoding="utf-8"))
        evenements = v.charger_evenements(EXEMPLES / "evenements.exemple.json",
                                          grille.get("couleur_agenda_par_defaut"))
        cls.a = v.analyser(grille, evenements, 2026, 9)
        cls.par_titre = {}
        for vac in cls.a["vacations"]:
            cls.par_titre.setdefault(vac["evenement"].titre, []).append(vac)

    def test_evenement_annule_ignore(self):
        self.assertNotIn("Réunion annulée",
                         [e.titre for e in self.a["autres"]] + list(self.par_titre))

    def test_evenements_prives_non_identifies(self):
        titres = {e.titre for e in self.a["autres"]}
        self.assertEqual(titres, {"Congés Nord", "Rentrée 9h30", "Dentiste"})

    def test_couleur_heritee_de_l_agenda(self):
        """Sans colorId, l'événement prend la couleur de l'agenda — ici semaine A."""
        vac = self.par_titre["8-19h"][0]
        self.assertEqual(vac["regle"].libelle, "Centre Orion")
        self.assertIn("héritée de l'agenda", vac["motif"])

    def test_bloc_multi_jours_compte_par_jour(self):
        """« 8-19h » du 7 au 9 vaut trois jours, moins une heure de pause chacun."""
        vac = self.par_titre["8-19h"][0]
        self.assertEqual(vac["jours"], [date(2026, 9, i) for i in (7, 8, 9)])
        self.assertEqual(vac["pause"], 3.0)
        self.assertEqual(vac["heures"], 30.0)   # 3 × (11 h − 1 h)

    def test_mot_cle_prime_sur_la_couleur(self):
        """« Altair » n'a pas de colorId : sans priorité au texte, il passerait Orion."""
        self.assertEqual(self.par_titre["Altair"][0]["regle"].libelle, "Clinique Altair")

    def test_revenu_par_employeur(self):
        montants = {nom: round(b["montant"], 2)
                    for nom, b in self.a["par_employeur"].items()}
        self.assertEqual(montants, {
            "Cabinet Vega": 900.0,        # 36 h × 25
            "Clinique Altair": 216.0,     # 8 h × 27
            "Centre Orion": 2552.73,      # 4000 € × 78 % × 18/22 jours ouvrés
            "Centre Rigel": 529.0,        # 10 h nuit + 3 h dimanche + 7 h nuit
            "Groupe Sirius astreinte": 400.0,   # forfait du bloc, pas par jour
        })

    def test_capacite_restante(self):
        s38 = self.a["semaines"][(2026, 38)]
        self.assertEqual(s38["heures"], 51.0)
        self.assertEqual(s38["reste"], -3.0)      # trois heures au-dessus
        self.assertEqual(self.a["semaines"][(2026, 36)]["reste"], 32.0)

    def test_agregat_par_jour(self):
        """La grille du mois se lit sur cet agrégat."""
        self.assertEqual(self.a["par_jour"][date(2026, 9, 2)], {"Cabinet Vega": 8.0})
        self.assertEqual(self.a["par_jour"][date(2026, 9, 10)],
                         {"Cabinet Vega": 8.0, "Clinique Altair": 4.0})
        self.assertNotIn(date(2026, 9, 13), self.a["par_jour"])   # un jour libre

    def test_plafond_hebdomadaire(self):
        semaines = {num: round(s["heures"], 2)
                    for (_, num), s in self.a["semaines"].items()}
        self.assertEqual(semaines[37], 42.0)   # 30 h Orion + 8 h Vega + 4 h Altair
        self.assertEqual(semaines[38], 51.0)
        depassees = [num for (_, num), s in self.a["semaines"].items() if s["depassement"]]
        self.assertEqual(depassees, [38])

    def test_astreinte_hors_plafond(self):
        s39 = self.a["semaines"][(2026, 39)]
        self.assertEqual(s39["heures"], 15.0)         # la nuit Rigel du lundi + Vega
        self.assertEqual(s39["hors_plafond"], 18.0)   # l'astreinte du week-end

    def test_chevauchement(self):
        conflits = self.a["chevauchements"]["entre_vacations"]
        self.assertEqual(len(conflits), 1)
        c = conflits[0]
        self.assertEqual(c["heures"], 3.0)
        self.assertEqual(c["debut"], datetime(2026, 9, 10, 15, 0))
        self.assertEqual({c["a"]["evenement"].titre, c["b"]["evenement"].titre},
                         {"Alta 15h-19h", "Vega journée"})

    def test_vacation_pendant_un_conge(self):
        """Un congé de trois jours qui couvre deux vacations compte deux jours."""
        avec = self.a["chevauchements"]["avec_autres"]
        self.assertEqual({c["evenement"].titre for c in avec}, {"Congés Nord"})
        self.assertEqual(sorted(c["debut"].date() for c in avec),
                         [date(2026, 9, 2), date(2026, 9, 3)])

    def test_hors_mois_compte_dans_la_semaine_pas_dans_le_revenu(self):
        octobre = self.par_titre["Vega journée"][-1]
        self.assertEqual(octobre["jours"], [date(2026, 10, 1)])
        self.assertEqual(octobre["heures_mois"], 0.0)
        self.assertEqual(round(self.a["par_employeur"]["Cabinet Vega"]["heures"], 2), 36.0)

    def test_jour_hors_grille_signale(self):
        self.assertTrue(any("n'est pas prévu le jeudi" in x for x in self.a["alertes"]))

    def test_rapports_ne_plantent_pas(self):
        self.assertIn("Revenu net projeté", v.rapport_texte(self.a))
        self.assertEqual(v.rapport_json(self.a)["total_net"], 4597.73)


class PauseNonPayee(unittest.TestCase):
    """Une pause non payée n'est pas du travail effectif : ni salaire, ni plafond."""

    EMP = {"pause_non_payee_heures": 1, "pause_a_partir_de_heures": 6}

    def test_seuil(self):
        self.assertEqual(v.pause_non_payee(self.EMP, 11.0), 1.0)
        self.assertEqual(v.pause_non_payee(self.EMP, 5.0), 0.0)
        self.assertEqual(v.pause_non_payee(self.EMP, 6.0), 0.0)

    def test_employeur_sans_regle_de_pause(self):
        self.assertEqual(v.pause_non_payee({"taux_net_heure": 28}, 11.0), 0.0)
        self.assertEqual(v.pause_non_payee(None, 11.0), 0.0)

    def test_la_pause_se_repartit_entre_jour_et_nuit(self):
        """Sans savoir à quelle heure elle tombe, elle se retire au prorata."""
        grille = {
            "employeurs": [{"nom": "N", "taux_net_estime_heure_jour": 10,
                            "taux_net_estime_heure_nuit": 20,
                            "pause_non_payee_heures": 1,
                            "pause_a_partir_de_heures": 6}],
            "identification_agenda_google": {
                "n": {"methode": "texte", "mot_cle": "N"}},
        }
        # 20h-8h un jeudi : 2 h de jour (20-21h et 7-8h), 10 h de nuit,
        # le tout ramené de 12 h à 11 h par la pause.
        ev = [v.Evenement("1", "N 20h-8h", datetime(2026, 9, 17),
                          datetime(2026, 9, 18), True, None, False)]
        a = v.analyser(grille, ev, 2026, 9)
        vac = a["vacations"][0]
        self.assertEqual(round(vac["heures"], 6), 11.0)
        self.assertEqual(vac["pause"], 1.0)
        cat = {}
        for seg in vac["segments"]:
            cat[seg["categorie"]] = cat.get(seg["categorie"], 0) + seg["heures"]
        self.assertEqual({k: round(h, 4) for k, h in cat.items()},
                         {"jour": round(2 * 11 / 12, 4), "nuit": round(10 * 11 / 12, 4)})


class PrioriteDesMotsCles(unittest.TestCase):
    """La priorité se joue mot par mot, pas règle par règle."""

    GRILLE = {
        "employeurs": [{"nom": "Crystal", "taux_net_heure": 28},
                       {"nom": "Hopital", "taux_net_heure": 20}],
        "identification_agenda_google": {
            "crystal": {"methode": "texte", "mot_cle": "Crystal",
                        "duree_par_defaut": "journee"},
            # Un employeur reconnu à des mots courts et génériques, dont l'un
            # (« apres-midi ») est plus long que « crystal ».
            "hopital": {"methode": "texte",
                        "mots_cles": ["matin", "aprem", "apres-midi", "nuit"],
                        "duree_par_defaut": "matin"}},
    }

    def _qui(self, titre):
        regles = v.construire_regles(self.GRILLE)
        ev = v.Evenement("1", titre, datetime(2026, 9, 2), datetime(2026, 9, 3),
                         True, None, False)
        regle, _ = v.identifier(ev, regles)
        return regle.libelle if regle else None

    def test_le_mot_le_plus_precis_gagne(self):
        """« Crystal matin » est un créneau Crystal, pas un poste d'hôpital."""
        self.assertEqual(self._qui("Crystal matin"), "Crystal")
        self.assertEqual(self._qui("Crystal aprèm"), "Crystal")

    def test_les_titres_generiques_restent_a_l_hopital(self):
        self.assertEqual(self._qui("Matin"), "Hopital")
        self.assertEqual(self._qui("Week-end aprem"), "Hopital")
        self.assertEqual(self._qui("Nuit supp"), "Hopital")

    def test_un_repos_hebdomadaire_n_est_pas_un_poste(self):
        self.assertIsNone(self._qui("RH prévisionnelle"))

    def test_ordre_des_mots(self):
        mots = [m for m, _ in v.mots_cles_par_priorite(v.construire_regles(self.GRILLE))]
        self.assertEqual(mots, sorted(mots, key=len, reverse=True))


class NoteDeGrille(unittest.TestCase):
    """Une réserve attachée à un chiffre doit remonter dans le rapport."""

    def test_note_rapport_remonte(self):
        grille = {"employeurs": [{"nom": "H", "type": "salaire_mensuel",
                                  "net_mensuel": 3000,
                                  "note_rapport": "net relevé sur un mois chargé"}],
                  "identification_agenda_google": {}}
        a = v.analyser(grille, [], 2026, 9)
        self.assertEqual(a["par_employeur"]["H"]["montant"], 3000)
        self.assertIn("H : net relevé sur un mois chargé", a["alertes"])

    def test_pas_de_note_pour_un_employeur_absent_du_mois(self):
        grille = {"employeurs": [{"nom": "H", "taux_net_heure": 10,
                                  "note_rapport": "à vérifier"}],
                  "identification_agenda_google": {}}
        self.assertEqual(v.analyser(grille, [], 2026, 9)["alertes"], [])


class DureeAmbigueOuContrainte(unittest.TestCase):
    """Deux façons de se tromper de demi-journée, pour de l'argent réel."""

    def _analyser(self, titre, jour, employeur):
        grille = {"employeurs": [employeur],
                  "identification_agenda_google": {
                      "x": {"methode": "texte", "mot_cle": "X",
                            "duree_par_defaut": "journee entiere si rien precise"}}}
        ev = [v.Evenement("1", titre, datetime.combine(jour, datetime.min.time()),
                          datetime.combine(jour + timedelta(days=1), datetime.min.time()),
                          True, None, False)]
        return v.analyser(grille, ev, jour.year, jour.month)

    EMP = {"nom": "X", "taux_net_heure": 10,
           "jours_possibles": ["lundi", "mardi", "mercredi", "jeudi",
                               "vendredi", "samedi_matin"]}

    def test_am_n_est_pas_tranche(self):
        """« AM » se lit matin en anglais, après-midi en français : on ne choisit pas."""
        self.assertEqual(v.abreviation_ambigue("X AM"), "AM")
        self.assertEqual(v.abreviation_ambigue("X PM"), "PM")
        self.assertIsNone(v.abreviation_ambigue("X matin"))
        self.assertIsNone(v.abreviation_ambigue("Amiens"))   # pas un mot isolé
        a = self._analyser("X AM", date(2026, 9, 8), self.EMP)   # un mardi
        self.assertEqual(a["vacations"][0]["heures"], 8.0)       # la durée par défaut
        self.assertTrue(any("peut se lire matin ou après-midi" in x for x in a["alertes"]))

    def test_samedi_matin_limite_le_samedi(self):
        """« jours_possibles: [samedi_matin] » dit aussi que le samedi est un matin."""
        a = self._analyser("X", date(2026, 9, 12), self.EMP)     # un samedi
        self.assertEqual(a["vacations"][0]["heures"], 4.0)       # et non 8 h
        self.assertTrue(any("limite X au samedi matin" in x for x in a["alertes"]))

    def test_la_contrainte_ne_touche_pas_les_autres_jours(self):
        a = self._analyser("X", date(2026, 9, 10), self.EMP)     # un jeudi
        self.assertEqual(a["vacations"][0]["heures"], 8.0)

    def test_un_titre_explicite_prime_sur_la_contrainte(self):
        a = self._analyser("X journée", date(2026, 9, 12), self.EMP)
        self.assertEqual(a["vacations"][0]["heures"], 8.0)


class ReposQuotidien(unittest.TestCase):
    """Onze heures entre deux journées : la règle que le cumul casse en premier."""

    def _vacations(self, *creneaux):
        return [{"creneaux": [(datetime(*d), datetime(*f))],
                 "regle": type("R", (), {"libelle": nom})()}
                for nom, d, f in creneaux]

    def test_une_pause_dejeuner_n_est_pas_un_repos(self):
        """Sinon chaque journée coupée passerait pour un repos manquant."""
        vac = self._vacations(("X", (2026, 9, 2, 8, 30), (2026, 9, 2, 12, 30)),
                              ("X", (2026, 9, 2, 13, 30), (2026, 9, 2, 18, 30)))
        self.assertEqual(len(v.periodes_de_travail(vac)), 1)
        self.assertEqual(v.repos_insuffisants(vac), [])

    def test_une_nuit_puis_un_matin(self):
        vac = self._vacations(("Hopital", (2026, 9, 2, 21, 0), (2026, 9, 3, 7, 0)),
                              ("Cabinet", (2026, 9, 3, 8, 30), (2026, 9, 3, 12, 30)))
        manques = v.repos_insuffisants(vac)
        self.assertEqual(len(manques), 1)
        self.assertEqual(manques[0]["heures"], 1.5)
        self.assertEqual(manques[0]["avant"], ["Hopital"])
        self.assertEqual(manques[0]["apres"], ["Cabinet"])

    def test_un_repos_suffisant_ne_dit_rien(self):
        vac = self._vacations(("X", (2026, 9, 2, 8, 0), (2026, 9, 2, 18, 0)),
                              ("X", (2026, 9, 3, 8, 0), (2026, 9, 3, 18, 0)))
        self.assertEqual(v.repos_insuffisants(vac), [])

    def test_l_amplitude_distingue_la_pause_du_repos(self):
        """8h30-12h30 puis 13h30-18h30 : une journée. 21h-7h puis 8h30 : deux."""
        journee = self._vacations(("X", (2026, 9, 2, 8, 30), (2026, 9, 2, 12, 30)),
                                  ("X", (2026, 9, 2, 13, 30), (2026, 9, 2, 18, 30)))
        self.assertEqual(len(v.periodes_de_travail(journee)), 1)   # amplitude 10 h
        nuit = self._vacations(("X", (2026, 9, 2, 21, 0), (2026, 9, 3, 7, 0)),
                               ("X", (2026, 9, 3, 8, 30), (2026, 9, 3, 12, 30)))
        self.assertEqual(len(v.periodes_de_travail(nuit)), 2)      # amplitude 15h30

    def test_le_minimum_est_reglable(self):
        vac = self._vacations(("X", (2026, 9, 2, 8, 0), (2026, 9, 2, 20, 0)),
                              ("X", (2026, 9, 3, 8, 0), (2026, 9, 3, 12, 0)))
        self.assertEqual(v.repos_insuffisants(vac, minimum=11.0), [])
        self.assertEqual(len(v.repos_insuffisants(vac, minimum=13.0)), 1)


class SalarieMensualise(unittest.TestCase):
    """Un mensualisé touche son mois : ses heures ne se tarifent pas."""

    GRILLE = {"nom": "X", "type": "salaire_mensuel", "brut_mensuel": 3000,
              "taux_charges_salariales": 0.25, "heures_mensuelles": 151.67}

    def test_mois_complet(self):
        montant, detail = v.salaire_du_mois(self.GRILLE, 2026, 9)
        self.assertEqual(round(montant, 2), 2250.0)      # 3000 × 75 %
        self.assertTrue(detail["complet"])

    def test_prime_13e_mois_etalee_sur_douze(self):
        grille = dict(self.GRILLE, prime_13e_mois=True)
        montant, _ = v.salaire_du_mois(grille, 2026, 9)
        self.assertEqual(round(montant, 2), 2437.5)      # 3000 × 13/12 × 75 %

    def test_prorata_jours_ouvres(self):
        """Septembre 2026 : 22 jours ouvrés, dont 18 à partir du lundi 7."""
        grille = dict(self.GRILLE, date_debut="2026-09-07")
        montant, detail = v.salaire_du_mois(grille, 2026, 9)
        self.assertEqual(detail["methode"], "ouvres")
        self.assertEqual(round(detail["part"], 4), round(18 / 22, 4))
        self.assertEqual(round(montant, 2), round(2250 * 18 / 22, 2))

    def test_prorata_calendaire(self):
        grille = dict(self.GRILLE, date_debut="2026-09-16", prorata="calendaire")
        montant, detail = v.salaire_du_mois(grille, 2026, 9)
        self.assertEqual(round(detail["part"], 4), round(15 / 30, 4))
        self.assertEqual(round(montant, 2), 1125.0)

    def test_net_mensuel_direct_n_est_pas_une_estimation(self):
        montant, detail = v.salaire_du_mois(
            {"nom": "X", "type": "salaire_mensuel", "net_mensuel": 2000}, 2026, 9)
        self.assertEqual(montant, 2000.0)
        self.assertFalse(detail["estime"])

    def test_sans_taux_de_charges_on_ne_devine_pas(self):
        montant, detail = v.salaire_du_mois(
            {"nom": "X", "type": "salaire_mensuel", "brut_mensuel": 3000}, 2026, 9)
        self.assertIsNone(montant)
        self.assertIn("taux_charges_salariales", detail["manque"])

    def test_un_horaire_n_est_pas_mensualise(self):
        self.assertFalse(v.est_mensualise({"nom": "Y", "taux_net_heure": 28}))
        self.assertEqual(v.salaire_du_mois({"nom": "Y", "taux_net_heure": 28},
                                           2026, 9), (None, None))


class PerimetreDuMois(unittest.TestCase):
    """Un rapport mensuel ne parle que de son mois — bugs trouvés à l'usage."""

    GRILLE = {
        "employeurs": [
            {"nom": "Fini", "type": "salaire_mensuel", "net_mensuel": 2000,
             "date_fin": "2026-09-11", "note_rapport": "chiffre à confirmer"},
            {"nom": "Horaire", "taux_net_heure": 20}],
        "identification_agenda_google": {
            "fini": {"methode": "texte", "mot_cle": "Fini",
                     "duree_par_defaut": "journee"},
            "horaire": {"methode": "texte", "mot_cle": "Horaire",
                        "duree_par_defaut": "journee"}},
    }

    def _ev(self, titre, jour):
        return v.Evenement("1", titre, datetime(2026, 9, jour),
                           datetime(2026, 9, jour + 1), True, None, False)

    def test_la_note_ne_suit_pas_un_employeur_absent_du_mois(self):
        """Le contrat s'arrête le 11/09 : en octobre, sa note n'a plus lieu d'être."""
        a = v.analyser(self.GRILLE, [], 2026, 9)
        self.assertTrue(any("chiffre à confirmer" in x for x in a["alertes"]))
        self.assertNotIn("Fini", v.analyser(self.GRILLE, [], 2026, 10)["par_employeur"])
        self.assertEqual(v.analyser(self.GRILLE, [], 2026, 10)["alertes"], [])

    def test_les_remarques_d_un_evenement_hors_mois_restent_dehors(self):
        """Un bloc de septembre ne doit pas commenter le rapport d'octobre."""
        ev = [self._ev("Horaire", 7)]
        ev[0].fin = datetime(2026, 9, 10)          # trois jours : ça se signale
        self.assertTrue(any("couvre 3 jours" in x
                            for x in v.analyser(self.GRILLE, ev, 2026, 9)["alertes"]))
        self.assertEqual(v.analyser(self.GRILLE, ev, 2026, 10)["alertes"], [])

    def test_une_vacation_apres_la_fin_du_contrat_est_signalee(self):
        a = v.analyser(self.GRILLE, [self._ev("Fini", 20)], 2026, 9)
        self.assertTrue(any("suit la fin annoncée" in x for x in a["alertes"]))

    def test_un_libelle_d_affichage_ne_scinde_pas_l_employeur(self):
        """Le rattachement se fait sur le nom de l'employeur, pas sur l'affichage."""
        grille = json.loads(json.dumps(self.GRILLE))
        grille["identification_agenda_google"]["fini"]["libelle"] = "Contrat fini"
        a = v.analyser(grille, [self._ev("Fini", 2)], 2026, 9)
        self.assertEqual(sorted(a["par_employeur"]), ["Fini"])
        # Une seule ligne, qui porte à la fois les heures et le salaire — et non
        # deux lignes dont l'une aurait les heures et l'autre l'argent.
        bloc = a["par_employeur"]["Fini"]
        self.assertGreater(bloc["heures"], 0)
        # Contrat arrêté le 11/09 : 9 jours ouvrés sur les 22 de septembre.
        self.assertEqual(round(bloc["montant"], 2), round(2000 * 9 / 22, 2))


class EtSi(unittest.TestCase):
    """Ce que coûte, et ce que rapporte, une vacation de plus."""

    @classmethod
    def setUpClass(cls):
        cls.grille = json.loads(
            (EXEMPLES / "grille.exemple.json").read_text(encoding="utf-8"))
        cls.evenements = v.charger_evenements(
            EXEMPLES / "evenements.exemple.json",
            cls.grille.get("couleur_agenda_par_defaut"))

    def _sim(self, *textes):
        return v.simuler(self.grille, self.evenements, 2026, 9,
                         [v.lire_hypothese(t, 2026) for t in textes],
                         couleur_agenda=self.grille.get("couleur_agenda_par_defaut"))

    def test_lecture_des_formats(self):
        for texte, jour in (("24/09 Vega journée", date(2026, 9, 24)),
                            ("2026-09-24 Vega journée", date(2026, 9, 24)),
                            ("24-09 Vega journée", date(2026, 9, 24))):
            self.assertEqual(v.lire_hypothese(texte, 2026).debut.date(), jour)
        self.assertEqual(v.lire_hypothese("24/09 Vega", 2026).titre, "Vega")

    def test_une_plage_de_jours(self):
        ev = v.lire_hypothese("24/09 → 26/09 Vega journée", 2026)
        self.assertEqual(ev.jours, [date(2026, 9, j) for j in (24, 25, 26)])

    def test_hypothese_illisible(self):
        with self.assertRaises(SystemExit):
            v.lire_hypothese("demain une vacation", 2026)

    def test_le_gain_d_une_vacation_horaire(self):
        sim = self._sim("29/09 Vega journée")           # un mardi libre
        self.assertEqual(len(sim["ajouts"]), 1)
        self.assertEqual(sim["ajouts"][0]["heures"], 8.0)
        self.assertEqual(round(sim["net_apres"] - sim["net_avant"], 2), 200.0)
        self.assertEqual(sim["conflits"], [])

    def test_une_heure_de_plus_chez_un_mensualise_ne_rapporte_rien(self):
        sim = self._sim("29/09 8-19h")                  # Orion, salarié au mois
        self.assertEqual(sim["ajouts"][0]["mode"], "mensualisé")
        self.assertEqual(round(sim["net_apres"] - sim["net_avant"], 2), 0.0)
        self.assertGreater(sim["heures_apres"], sim["heures_avant"])

    def test_la_bascule_au_dessus_du_plafond_est_annoncee(self):
        sim = self._sim("11/09 Vega journée")           # semaine 37, déjà à 42 h
        s37 = next(s for s in sim["semaines"] if s["numero"] == 37)
        self.assertEqual((s37["avant"], s37["apres"]), (42.0, 50.0))
        self.assertTrue(s37["bascule"])

    def test_un_jour_deja_pris_ressort_en_conflit(self):
        sim = self._sim("02/09 Vega journée")           # Vega y travaille déjà
        # Une journée vaut deux créneaux : le recouvrement se compte deux fois,
        # matin et après-midi.
        self.assertEqual(len(sim["conflits"]), 2)
        self.assertEqual({c["debut"].date() for c in sim["conflits"]},
                         {date(2026, 9, 2)})

    def test_un_titre_non_rattachable_ne_simule_rien(self):
        sim = self._sim("29/09 Réunion syndicale")
        self.assertEqual(sim["ajouts"], [])
        self.assertEqual(sim["non_reconnus"], ["Réunion syndicale"])
        self.assertEqual(sim["net_apres"], sim["net_avant"])

    def test_le_mois_de_reference_n_est_pas_modifie(self):
        """La simulation ne doit rien laisser derrière elle."""
        avant = v.analyser(self.grille, self.evenements, 2026, 9)
        self._sim("29/09 Vega journée")
        apres = v.analyser(self.grille, self.evenements, 2026, 9)
        self.assertEqual(len(avant["vacations"]), len(apres["vacations"]))

    def test_le_rapport_texte_tient(self):
        texte = v.rapport_simulation(self._sim("29/09 Vega journée"))
        self.assertIn("Et si", texte)
        self.assertIn("200,00 €", texte)


class MiseEnPage(unittest.TestCase):
    """La page HTML ne recalcule rien : elle doit dire ce que dit l'analyse."""

    @classmethod
    def setUpClass(cls):
        grille = json.loads((EXEMPLES / "grille.exemple.json").read_text(encoding="utf-8"))
        evenements = v.charger_evenements(EXEMPLES / "evenements.exemple.json",
                                          grille.get("couleur_agenda_par_defaut"))
        cls.page = rapport_html.construire(v.analyser(grille, evenements, 2026, 9))

    def test_page_autonome(self):
        self.assertTrue(self.page.startswith("<!doctype html>"))
        self.assertTrue(self.page.rstrip().endswith("</html>"))
        self.assertIn("<title>Vacations septembre 2026</title>", self.page)
        # Aucune ressource externe : la page doit s'ouvrir hors connexion.
        self.assertNotIn("http://", self.page)
        self.assertNotIn("https://", self.page)

    def test_les_chiffres_sont_ceux_de_l_analyse(self):
        # Les montants portent une espace fine insécable : on normalise avant
        # de comparer, plutôt que de la recopier dans le test.
        page = re.sub(r"\s+", " ", self.page)
        self.assertIn("4 597,73 €", page)          # total net
        self.assertIn("2 552,73 €", page)          # Orion, mensualisé
        self.assertIn("51 h", page)                # la semaine hors plafond

    def test_le_titre_d_un_evenement_est_echappe(self):
        """Un titre d'agenda est du texte saisi : il ne doit pas devenir du HTML."""
        grille = {"employeurs": [{"nom": "X", "taux_net_heure": 10}],
                  "identification_agenda_google": {"x": {"methode": "texte",
                                                         "mot_cle": "X",
                                                         "duree_par_defaut": "matin"}}}
        ev = [v.Evenement("1", "X <script>alert(1)</script>", datetime(2026, 9, 2),
                          datetime(2026, 9, 3), True, None, False)]
        page = rapport_html.construire(v.analyser(grille, ev, 2026, 9))
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)


class EmployeurAbsentDeLaGrille(unittest.TestCase):
    """Une entrée d'agenda sans employeur en face : heures oui, euros non."""

    def test_heures_comptees_revenu_non_chiffrable(self):
        grille = {
            "employeurs": [],
            "identification_agenda_google": {
                "orion": {"methode": "couleur", "couleur_semaine_A": "lavande",
                              "duree": "heures indiquees dans le titre"}},
        }
        evenements = [v.Evenement("1", "8-19h", datetime(2026, 9, 21),
                                  datetime(2026, 9, 22), True, "lavande", False)]
        a = v.analyser(grille, evenements, 2026, 9)
        self.assertEqual(a["vacations"][0]["heures"], 11.0)
        self.assertIsNone(a["vacations"][0]["montant"])
        self.assertTrue(any("revenu non calculable" in x for x in a["alertes"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
