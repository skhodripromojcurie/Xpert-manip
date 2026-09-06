# `vacations.py` — heures, revenu net et conflits d'un mois d'agenda

Le planning de vacations vit dans l'agenda Google, pas dans un tableur. Chaque
créneau y est un événement, reconnu soit à sa **couleur**, soit à un **mot-clé**
dans son titre. Cet outil relit un mois et répond aux quatre questions qui
décident d'accepter, ou non, une vacation de plus :

1. combien d'heures, créneau par créneau ;
2. combien d'heures par semaine — le plafond de 48 h **alerte**, il ne bloque pas ;
3. combien net à la fin du mois, employeur par employeur ;
4. deux créneaux se marchent-ils dessus.

```
python3 outils/vacations.py --exemple                 # sur les fac-similés du dépôt
python3 outils/vacations.py --mois 2026-09            # sur donnees/
python3 outils/vacations.py --mois 2026-09 --json     # même chose, exploitable
python3 outils/tests_vacations.py                     # les contrôles

python3 outils/rapport_html.py --mois 2026-09 --sortie ~/vacations.html
```

`rapport_html.py` met la même analyse en page : un fichier HTML autonome, sans
ressource externe, qui s'ouvre depuis un téléphone et s'imprime. Il ne recalcule
rien — il lit `analyser()` et le met en forme, pour que le terminal et la page ne
puissent pas diverger.

## Ce dépôt est public : les données restent dehors

La grille tarifaire (employeurs, taux, statuts) et l'export d'agenda sont des
données personnelles et financières. Le README l'interdit, et `.gitignore` le
tient : ces deux fichiers sont attendus dans `donnees/`, où ils ne sont pas
versionnés.

| Fichier | Versionné | Contenu |
|---|---|---|
| `donnees/grille_tarifaire.json` | **non** | la vraie grille |
| `donnees/evenements.json` | **non** | l'export d'agenda du mois |
| `outils/exemples/grille.exemple.json` | oui | fac-similé inventé, même forme |
| `outils/exemples/evenements.exemple.json` | oui | fac-similé inventé, même forme |

Pour produire `donnees/evenements.json` : la réponse brute de l'API Google
Calendar (`events.list`) convient telle quelle — `{"events": [...]}`, ou une
liste nue. Prendre une fenêtre **plus large que le mois** : les semaines ISO à
cheval débordent, et le plafond hebdomadaire se compte lundi-dimanche.

## Comment un événement devient une vacation

**Les mots-clés priment sur les couleurs.** Un événement sans `colorId` n'est pas
incolore : il hérite de la couleur de l'agenda. Si cette couleur est celle d'un
employeur, tout événement non coloré lui serait attribué — les vacations
reconnues au titre passeraient à la trappe. D'où l'ordre.

- **Mot-clé** : le titre contient le mot. `mot_cle` accepte le commentaire qui
  l'accompagne dans la grille (`"Altair (…, ex: Alta)"` → `alta`, qui
  couvre les deux) ; `mots_cles: [...]` est la forme propre.
- **Couleur explicite** (`colorId` posé) : la couleur suffit.
- **Couleur héritée** (pas de `colorId`) : elle ne porte aucune intention, donc
  le titre doit être **purement horaire** (`8-19h` oui, `Rentrée 9h30` non).
  Cette couleur n'est pas dans l'export : la donner par `--couleur-agenda`, ou
  par `"couleur_agenda_par_defaut"` dans la grille. Sans elle, l'outil le dit.

Google numérote deux palettes distinctes à partir de 1 : celle des **événements**
(11 couleurs) et celle des **agendas** (24). « Glycine » n'existe que dans la
seconde — c'est pourquoi elle ne se lit jamais dans un `colorId`, elle se déduit
de son absence.

## Comment on trouve les heures

Dans l'ordre :

1. **L'horaire du titre** — `8-19h`, `8h30-12h30`, `21h-7h`, `de 8h à 12h30`.
   Une fin ≤ début franchit minuit. Le `h` (ou `:`) est obligatoire : sans lui,
   un titre contenant une date se lirait comme un horaire.
2. **La durée de l'événement**, s'il est horodaté.
3. **Le créneau par défaut** — `matin`, `apres_midi`, `journee`, `nuit`, choisi
   dans cet ordre : un mot du titre (« aprèm », « journée »…), puis la contrainte
   du jour, puis la durée par défaut de l'employeur.

**`jours_possibles` ne dit pas que quels jours sont ouverts.** Une entrée de la
forme `samedi_matin` dit aussi qu'on n'y fait que le matin : un titre sans
précision y vaut une demi-journée, pas une journée, et le rapport le signale.
Un mot explicite dans le titre reprend la main.

**« AM » et « PM » ne sont pas tranchés.** « AM » se lit *ante meridiem* en
anglais et *après-midi* en français — deux demi-journées opposées, et un écart
d'argent réel. L'outil applique la durée par défaut et le signale, plutôt que de
choisir. Pour lever l'ambiguïté : écrire le mot dans le titre, ou déclarer la
convention par `mots_cles` dans la grille.

**Un bloc « journée entière » sur plusieurs jours vaut une vacation par jour.**
« 8-19h » du 14 au 16 fait 33 h, pas 11. Le rapport le signale à chaque fois.

### Les durées par défaut sont des hypothèses, pas des faits

Ce que vaut « une journée » n'est écrit nulle part dans la grille. Les valeurs
retenues sont affichées en fin de rapport, section **Hypothèses appliquées**, et
se corrigent employeur par employeur :

```json
"cabinet_vega": {
  "methode": "texte",
  "mot_cle": "Vega",
  "duree_si_non_precise": "journee",
  "creneaux_par_defaut": { "journee": "9h-13h, 14h-18h", "matin": "9h-13h" }
}
```

Par défaut : `matin` 9h-13h, `apres_midi` 14h-18h, `journee` 9h-13h + 14h-18h
(8 h, pause déjeuner déduite), `nuit` 21h-7h. Si l'employeur a un `creneau_type`
(ou `creneau`, ou `creneaux`), il remplace son créneau par défaut — c'est ainsi
qu'un samedi matin en clinique vaut 8h30-12h30, soit 4 h.

### La pause non payée

Aucune pause n'est déduite par défaut : `8-19h` compte 11 h. Quand une journée
en comporte une, l'employeur la déclare :

```json
"pause_non_payee_heures": 1,
"pause_a_partir_de_heures": 6
```

`8-19h` vaut alors 10 h, et `8-13h` reste à 5 h — le seuil évite d'amputer une
demi-journée. La pause sort du salaire **et** du plafond hebdomadaire : elle
n'est pas du travail effectif. Comme rien ne dit à quelle heure elle tombe, elle
se retire au prorata du créneau, ce qui préserve la répartition entre heures de
jour, de nuit et de dimanche.

## Comment on calcule le net

Trois modes de rémunération, choisis d'après ce que la grille dit de l'employeur.

### À l'heure

- `taux_net_heure`, ou `taux_net_estime_heure_{jour,nuit,dimanche_ferie}`
  pour un employeur à taux variable. Une valeur `_estime` est signalée comme telle.
- Un employeur qui n'a qu'un `taux_brut_*` n'est pas converti : le rapport dit
  « taux brut seul ».
### Au forfait

- `forfait_net` ou `forfait_net_estime` : une fois par événement, pas par jour —
  une astreinte de week-end est un forfait, pas deux. `"forfait_par_jour": true`
  inverse la règle.

### Au mois

Un salarié mensualisé touche son mois, pas ses heures. Ses créneaux restent lus
et comptés — ils pèsent sur le plafond hebdomadaire, et peuvent chevaucher une
vacation — mais ils ne produisent aucun euro : le montant vient du contrat.

```json
{
  "nom": "…", "type": "salaire_mensuel",
  "brut_mensuel": 4337.76, "prime_13e_mois": true,
  "taux_charges_salariales": 0.22,
  "heures_mensuelles": 151.67,
  "date_debut": "2026-09-15", "prorata": "ouvres"
}
```

- `net_mensuel` court-circuite le brut et n'est pas présenté comme une estimation.
- `prime_13e_mois` ajoute un treizième du brut chaque mois (versement en douze
  mensualités). Si le 13e mois est versé en une fois, ne pas l'activer.
- `date_debut` / `date_fin` déclenchent le **prorata** d'un mois partiel. La
  méthode change le résultat de plusieurs centaines d'euros, donc elle est
  affichée : `ouvres` (défaut, jours du lundi au vendredi), `calendaire`, ou
  `heures` (heures réellement posées / `heures_mensuelles`).
- Sans `net_mensuel` ni `taux_charges_salariales`, rien n'est deviné : le
  rapport dit ce qui manque.

Le rapport marque les heures d'un mensualisé d'une `*` — « heures indicatives,
sans effet sur le montant ».
- Les heures sont découpées à minuit, puis ventilées : **dimanche ou férié**
  d'abord, sinon **nuit** (fenêtre `plage_nuit`, 21h-7h par défaut) ou **jour**.
  Les jours fériés se passent par `--feries fichier.json` (liste de `AAAA-MM-JJ`).
### Communs aux trois modes

- Les heures sont découpées à minuit, puis ventilées : dimanche ou férié
  d'abord, sinon nuit ou jour (voir plus haut).
- `delai_paiement_mois` ne change pas le montant : il ajoute le mois
  d'encaissement au rapport.
- `taux_prelevement_source` (à la racine de la grille) ajoute une ligne « après
  impôt sur le revenu » sous le total. Les « net » d'un bulletin de paie sont
  des nets **avant** impôt : c'est cette ligne qui dit ce qui arrive sur le compte.
- Un bloc à cheval sur deux mois est **proratisé** : seules les heures tombant
  dans le mois sont facturées, mais toutes comptent dans leur semaine.

Un employeur présent dans l'agenda mais **absent de `employeurs`** voit ses
heures comptées et son revenu déclaré non chiffrable. C'est volontaire : mieux
vaut un trou visible qu'un total faux.

## Ce que le rapport signale

Rien de tout cela n'est bloquant :

- semaine au-dessus du plafond, tous employeurs confondus — les heures
  d'astreinte en sont exclues (disponibilité, pas travail effectif ; renversable
  par `"compte_dans_plafond": true`) ;
- deux vacations qui se recouvrent, avec la tranche exacte ;
- une vacation posée pendant un autre événement de l'agenda (congés, rendez-vous) ;
- un employeur au statut non actif, un jour hors de ses `jours_possibles`, une
  vacation antérieure à sa date de démarrage (lue dans `note`, « commence le … ») ;
- un mot-clé ou une durée encore à définir dans la grille.
