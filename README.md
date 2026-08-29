# Xpert-manip — référentiel de protocoles

Référentiel de protocoles de radiographie conventionnelle, consultable en ligne
et depuis un téléphone : recherche instantanée par région, indication ou mot-clé
clinique.

## Contenu

- `docs/index.html` — le référentiel, 42 fiches. Fichier autonome : il fonctionne
  sans serveur, hors connexion, et s'ouvre directement depuis un téléphone.

## Périmètre de ce dépôt

**Ce dépôt est public.** Il ne contient que du contenu librement diffusable :
protocoles techniques, indications, paramètres d'acquisition, mots-clés de
recherche.

Ne doivent jamais y figurer :

- le manuscrit du guide (cas cliniques, règles de décision, raisonnement clinique
  issu de l'expérience terrain) — il vit dans un dépôt privé séparé ;
- des données personnelles, financières ou identifiantes, de quelque nature que
  ce soit.

Règle de partage : ce qui est disponible ailleurs (HAS, manuels) va ici. Ce qui
vient du jugement et de la décision reste dans le dépôt privé.

## État

- Diffusion en attente : GitHub Pages n'est pas activé.
- Structure cible : `donnees/protocoles.json` comme source unique de vérité,
  `docs/index.html` régénéré depuis ce JSON par `outils/build_site.py`.
- Deux fiches à ajouter au référentiel (pouce ; articulation sterno-claviculaire),
  ce qui portera le total à 44.
