#!/usr/bin/env python3
"""Contrôles de outils/vacations.py.

Les chiffres attendus sont calculés à la main sur les fac-similés de
`outils/exemples/`, qui n'ont rien de personnel. Ce sont eux qui protègent les
règles fragiles : un titre-horaire qui vaut par jour et non par bloc, une nuit
qui bascule d'un jour à l'autre, une astreinte qui ne pèse pas sur le plafond.

    python3 outils/tests_vacations.py
"""
import json
import unittest
from datetime import date, datetime
from pathlib import Path

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
        """« 8-19h » du 7 au 9 vaut trois fois onze heures, pas onze."""
        self.assertEqual(self.par_titre["8-19h"][0]["heures"], 33.0)

    def test_mot_cle_prime_sur_la_couleur(self):
        """« Altair » n'a pas de colorId : sans priorité au texte, il passerait Orion."""
        self.assertEqual(self.par_titre["Altair"][0]["regle"].libelle, "Clinique Altair")

    def test_revenu_par_employeur(self):
        montants = {nom: round(b["montant"], 2)
                    for nom, b in self.a["par_employeur"].items()}
        self.assertEqual(montants, {
            "Cabinet Vega": 700.0,        # 28 h × 25
            "Clinique Altair": 216.0,     # 8 h × 27
            "Centre Orion": 1914.0,       # 66 h × 29
            "Centre Rigel": 529.0,        # 10 h nuit + 3 h dimanche + 7 h nuit
            "Groupe Sirius astreinte": 400.0,   # forfait du bloc, pas par jour
        })

    def test_plafond_hebdomadaire(self):
        semaines = {num: round(s["heures"], 2)
                    for (_, num), s in self.a["semaines"].items()}
        self.assertEqual(semaines[37], 45.0)
        self.assertEqual(semaines[38], 54.0)
        depassees = [num for (_, num), s in self.a["semaines"].items() if s["depassement"]]
        self.assertEqual(depassees, [38])

    def test_astreinte_hors_plafond(self):
        s39 = self.a["semaines"][(2026, 39)]
        self.assertEqual(s39["heures"], 7.0)          # la nuit Rigel du lundi
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
        pendant = {c["evenement"].titre
                   for c in self.a["chevauchements"]["avec_autres"]}
        self.assertEqual(pendant, {"Congés Nord"})

    def test_hors_mois_compte_dans_la_semaine_pas_dans_le_revenu(self):
        octobre = self.par_titre["Vega journée"][-1]
        self.assertEqual(octobre["jours"], [date(2026, 10, 1)])
        self.assertEqual(octobre["heures_mois"], 0.0)
        self.assertEqual(round(self.a["par_employeur"]["Cabinet Vega"]["heures"], 2), 28.0)

    def test_jour_hors_grille_signale(self):
        self.assertTrue(any("n'est pas prévu le jeudi" in x for x in self.a["alertes"]))

    def test_rapports_ne_plantent_pas(self):
        self.assertIn("Revenu net projeté", v.rapport_texte(self.a))
        self.assertEqual(v.rapport_json(self.a)["total_net"], 3759.0)


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
