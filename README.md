# Xpert-manip — référentiel de protocoles

Référentiel de protocoles de radiographie conventionnelle, consultable en ligne
et depuis un téléphone : recherche instantanée par région, indication ou mot-clé
clinique.

## Contenu

- `donnees/protocoles.json` — les 44 fiches, source unique de vérité.
  Voir `donnees/schema.md` pour le contrat des champs.
- `docs/index.html` — la page livrée, **générée** depuis ce JSON. Fichier
  autonome : elle fonctionne sans serveur, hors connexion, et s'ouvre
  directement depuis un téléphone.
- `outils/build_site.py` — régénère la page. Le référentiel ne se modifie que
  par le JSON, jamais dans la page.

- `outils/vacations.py` — outil de planning : lit un mois d'agenda et en sort
  les heures, le revenu net projeté et les conflits de créneaux. Voir
  `outils/vacations.md`. Il ne lit **aucune** donnée versionnée ici : la grille
  tarifaire et l'export d'agenda restent hors du dépôt.

```
python3 outils/build_site.py              # régénérer docs/index.html
python3 outils/build_site.py --verifier   # docs/ est-il en phase avec donnees/ ?
python3 outils/verifier.py                # le contenu a-t-il dévié de l'origine ?
python3 outils/vacations.py --exemple     # l'outil de vacations, sur ses fac-similés
python3 outils/tests_vacations.py         # ses contrôles
```

## Périmètre de ce dépôt

**Ce dépôt est public.** Il ne contient que du contenu librement diffusable :
protocoles techniques, indications, paramètres d'acquisition, mots-clés de
recherche.

Ne doivent jamais y figurer :

- le manuscrit du guide (cas cliniques, règles de décision, raisonnement clinique
  issu de l'expérience terrain) — il vit dans un dépôt privé séparé ;
- des données personnelles, financières ou identifiantes, de quelque nature que
  ce soit. `outils/vacations.py` en manipule : son code est ici, ses données
  jamais. `.gitignore` couvre `donnees/grille_tarifaire.json` et
  `donnees/evenements.json` ; `outils/exemples/` ne contient que des
  fac-similés inventés.

Règle de partage : ce qui est disponible ailleurs (HAS, manuels) va ici. Ce qui
vient du jugement et de la décision reste dans le dépôt privé.

## État

- Diffusion en attente : GitHub Pages n'est pas activé.
- 44 fiches. Les deux dernières (pouce ; articulation sterno-claviculaire) sont
  rédigées mais **en attente de relecture professionnelle** avant diffusion.
