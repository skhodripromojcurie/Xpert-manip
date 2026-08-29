# Contrat des champs — `protocoles.json`

Source unique de vérité du référentiel. `docs/index.html` en est un produit
généré : **on ne modifie jamais la page à la main**, on modifie ce JSON et on
relance `python3 outils/build_site.py`.

## Champs

| Champ | Publié | Rôle |
|---|---|---|
| `id` | oui | Identifiant stable, en minuscules avec tirets. C'est la clé à laquelle le guide accroche ses renvois et ses encarts de cas. **Ne se renomme pas** une fois posé : un renvoi cassé est silencieux. |
| `modality` | oui | `Radiographie` pour l'instant. Le rendu regroupe par modalité. |
| `modalityClass` | oui | Classe CSS associée (`radio`). |
| `title` | oui | Intitulé affiché de la fiche. |
| `region` | oui | Région anatomique fine, affichée sur la carte. 28 valeurs distinctes. |
| `groupe` | non | Un des 11 groupes ci-dessous. Sert au découpage régional du guide. |
| `axe` | non | `traumato`, `rhumato` ou `mixte`. |
| `indication` | oui | Indication clinique, sourcée. |
| `parameters` | oui | Liste des paramètres d'acquisition et critères de qualité. |
| `keywords` | oui | Mots-clés de recherche, y compris en langage patient. |

`groupe` et `axe` sont internes : `build_site.py` les retire de la page livrée.
Ils existent pour que le guide et le référentiel partagent le même découpage sans
que le lecteur du site ait à en connaître l'existence.

## Les 11 groupes

`thorax`, `rachis`, `bassin`, `epaule`, `coude-bras`, `main-poignet`,
`femur-jambe`, `genou`, `cheville-pied`, `tete`, `asp`.

Ils reprennent exactement le découpage régional du guide, de sorte que chaque
chapitre du guide corresponde à un `groupe` et à rien d'autre. Les libellés
affichables sont dans `outils/build_site.py`.

## Ce qui a le droit d'entrer ici

Uniquement ce qui est librement diffusable : protocoles, indications, paramètres,
mots-clés. Le raisonnement clinique, les cas et les règles de décision relèvent du
dépôt privé du guide — voir le README.

Un fait de manuel reste un fait de manuel même quand il a été rencontré sur un
cas : il a sa place ici. C'est la décision prise autour de ce fait qui n'y est pas.

## Contrôles

    python3 outils/build_site.py             # régénère docs/index.html
    python3 outils/build_site.py --verifier   # docs/ est-il en phase avec donnees/ ?
    python3 outils/verifier.py                # le contenu publié a-t-il dévié de l'origine ?

`build_site.py` refuse de construire sur des identifiants en double, un `groupe`
ou un `axe` inconnu, ou un contenu qui fermerait le `<script>` de la page.
