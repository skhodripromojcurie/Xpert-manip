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
