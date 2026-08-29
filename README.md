# Xpert-manip — référentiel de protocoles

Référentiel de protocoles de radiographie conventionnelle, consultable en ligne
et depuis un téléphone : recherche instantanée par région, indication ou mot-clé
clinique.

## Contenu

- `donnees/protocoles.json` — les 42 fiches, source unique de vérité.
  Voir `donnees/schema.md` pour le contrat des champs.
- `docs/index.html` — la page livrée, **générée** depuis ce JSON. Fichier
  autonome : elle fonctionne sans serveur, hors connexion, et s'ouvre
  directement depuis un téléphone.
- `outils/build_site.py` — régénère la page. Le référentiel ne se modifie que
  par le JSON, jamais dans la page.

```
python3 outils/build_site.py              # régénérer docs/index.html
python3 outils/build_site.py --verifier   # docs/ est-il en phase avec donnees/ ?
python3 outils/verifier.py                # le contenu a-t-il dévié de l'origine ?
```

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
- Deux fiches restent à rédiger (pouce ; articulation sterno-claviculaire), ce qui
  portera le référentiel à 44 fiches.
