# À faire à la prochaine session

Deux demandes posées le 08/09/2026, à traiter ensemble.

## 1. Simuler octobre, novembre et décembre 2026 d'un coup

Aujourd'hui les outils travaillent mois par mois. Il faut les enchaîner sur les
trois mois restants de 2026 et donner un cumul : revenu net, heures, coûts, et
les semaines qui débordent d'un mois sur l'autre — une semaine ISO à cheval sur
octobre et novembre ne doit être comptée qu'une fois.

Points à ne pas rater :

- **Décembre est déjà partiellement posé** dans l'agenda (roulement Résonance
  jusqu'au 05/12 au moins) : le lire, ne pas le supposer.
- **Le 13e mois Résonance** est versé en douze mensualités, donc déjà dans le
  net mensuel. Vérifier qu'un éventuel versement de fin d'année ne le compte pas
  deux fois.
- **Les jours fériés** : le 1er novembre et le 11 novembre sont dans la période,
  Noël et le Jour de l'an aussi. `--feries` existe mais n'a jamais servi ; la
  question de savoir si Résonance majore un férié travaillé n'est pas tranchée.
- Le contrôle des **44 h en moyenne sur 12 semaines glissantes** devient
  calculable dès qu'on lit trois mois d'affilée. C'est le dernier plafond légal
  que l'outil ne surveille pas.

## 2. Un tableau de disponibilités à donner à Jessica

Sortir, à partir du scénario « tous les jours libres », la liste des créneaux à
proposer : une ligne par date, avec le type de séance et un format qui se
recopie ou s'envoie tel quel. C'est l'inverse du tableau de simulation — non
plus « ce créneau vaut quoi » mais « voilà ce que je peux prendre ».

À prévoir :

- Le **site n'est pas choisi** : le tableau propose des disponibilités, pas des
  affectations. Ne pas y faire figurer un site précis.
- Marquer les créneaux qui **font franchir le plafond** de 48 h, sans les
  retirer : c'est une information pour l'utilisateur, pas pour l'employeur.
- Prévoir la même chose pour les autres sites, pas seulement Crystal.

## Ce qu'il faudra rapporter en séance

La grille tarifaire et le fichier de trajets **ne sont pas versionnés** — le
dépôt est public. Une session neuve ne les a donc pas. À joindre :

- `grille_tarifaire.json` (version enrichie : Résonance mensualisé, Bichat,
  taux Martinets à 30,225, pause d'1 h, couleur d'agenda glycine)
- `trajets.json` (distances, durées par régime, stationnements)

L'agenda, lui, se relit tout seul via le connecteur Google.
