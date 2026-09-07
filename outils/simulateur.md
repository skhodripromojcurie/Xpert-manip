# `simulateur.py` — où poser une vacation de plus, et ce qu'elle coûte vraiment

Le planning Résonance est fixe : il se lit dans l'agenda. Ce qui se décide, ce
sont les créneaux qu'on ajoute par-dessus, sur les jours restés libres.

```
python3 outils/simulateur.py --mois 2026-11 --rentabilite
python3 outils/simulateur.py --mois 2026-11 --cible 5500
python3 outils/simulateur.py --mois 2026-11 --sans-gamelle --sans-plafond
```

**Rien du calcul de paie n'est réécrit.** Le simulateur fabrique des événements
d'agenda et les fait passer par `vacations.analyser` : même identification, même
tarif, même plafond, même repos de 11 h. Un scénario dit donc exactement ce que
dira le mois une fois les créneaux posés. Ce qu'il ajoute, c'est le coût du
déplacement et le temps de trajet — invisibles sur une fiche de paie, et
suffisants pour renverser le classement des sites.

## Le fichier de trajets

`donnees/trajets.json`, non versionné (le dépôt est public). Un fac-similé
inventé dans `outils/exemples/trajets.exemple.json` fait tourner les tests.

Par site : `distance_domicile_km_aller`, `duree_domicile_min_aller`,
`stationnement` (texte) et `stationnement_eur` (montant, si connu et fixe).

- « gratuit » vaut zéro euro.
- « variable », « selon la place », « non précisé », « difficile » ne se
  chiffrent pas : le site est **classé à part**, jamais crédité d'un zéro qui
  fausserait son rang.
- Sans distance, ni carburant ni rendement ne sont calculables, et le rapport le
  dit — il ne remplace pas un trou par un zéro.

Le coût kilométrique est du carburant seul (4,5 L/100 km à 2 €/L, soit
0,09 €/km) : ni péage, ni usure. Le repas vaut 0 € avec gamelle, sinon le
montant de `repas.montant_eur`.

## Les trois optimisations

Elles ne donnent pas la même réponse, et aucune n'est désignée « la bonne ».

| | Ce qu'elle maximise |
|---|---|
| **Revenu maximal** | le net après coûts, sans regarder le temps |
| **Rendement maximal** | le net après coûts par heure **passée**, trajet compris |
| **Cible** | atteindre un montant en y passant le moins de temps |

Le découpage par semaine tient l'énumération dans des tailles raisonnables : le
plafond hebdomadaire est la seule contrainte qui lie des jours entre eux. Les
trois résultats sont **exacts**, pas approchés — le rendement passe par le
paramètre λ (Dinkelbach), qui rend un rapport de sommes séparable ; la cible par
un sac à dos sur les semaines.

## Ce que le simulateur refuse de proposer

- **Une séance qui casse le repos de 11 h** avec le planning déjà posé. La
  proposer reviendrait à recommander quelque chose d'illégal ; elle est écartée
  et comptée, avec le repos qu'elle aurait laissé.
- **Un jour dont un événement porte un titre mal formé** (`8h19h` au lieu de
  `8-19h`). Ce titre n'est lu par personne, le jour paraît libre sans l'être. Il
  est écarté, et le rapport dit lequel corriger.
- **Un site pour un employeur mensualisé** : son heure marginale vaut zéro, une
  rentabilité horaire n'aurait pas de sens.

## Ce qu'il faut savoir lire

Quand aucune distance n'est renseignée, les deux premières optimisations
donnent le même résultat — sans trajet, il n'y a pas d'arbitrage entre argent et
temps — et le site retenu pour un employeur multi-sites est **arbitraire**. Le
rapport l'annonce plutôt que de laisser croire à une recommandation.
