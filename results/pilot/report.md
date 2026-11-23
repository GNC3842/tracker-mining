# Rapport de faisabilité — crawl pilote

Sites visités : 200 · exploitables : 104 · statuts : {'error': 12, 'ok': 125, 'timeout': 42, 'http_error': 21} · challenges anti-bot : 30

| Critère | Valeur | Seuil | Verdict |
|---|---|---|---|
| 2. Taux de succès du crawl | 0.52 | 0.8 | NO-GO |
| 3a. Requêtes tierces à parent résolu | 0.985 | 0.8 | GO |
| 3b. Domaines majoritairement à profondeur >= 2 | 0.516 | 0.2 | GO |
| 4a. Domaines étiquetés (estimation crawl complet) | 1339 | 500 | GO |
| 4b. Part de domaines absents de Tracker Radar | 0.273 | 0.1 | GO |
| 5. Entités avec >= 2 domaines observés | 34 | 30 | GO |

## Indicateurs complémentaires

- Méthodes de résolution du parent : {'init_url': 1590, 'stack': 3579, 'redirect': 663, 'fallback': 90, 'none': 1}
- Profondeurs des couples site x domaine (4 = >= 4) : {'1': 417, '2': 289, '3': 115, '4': 72}
- Couples à profondeur >= 2 : 0.533 · domaines vus au moins une fois à >= 2 : 0.553
- Graphe tiers -> tiers : 273 nœuds, 801 arêtes
- Spearman(PageRank, prévalence) = 0.485 (proche de 1 = la structure n'apporte presque rien de plus que le comptage)
- Labels : {'unknown': 111, 'uncategorized': 118, 'tracking': 118, 'non_tracking': 38, 'ambiguous': 22} · entités observées : 151
- Sites avec bandeau de consentement : 0.038 · sites déposant des cookies tiers : 0.433
- Durée par site : médiane 10.16 s, p90 37.6 s · 105.8 Ko/site
- Crawl complet estimé (7665 sites, 4 en parallèle) : 5.4 h
- Règles EasyPrivacy chargées : 46995

Fichiers produits : metrics.json, inclusion_edges.csv, annotation_sample.csv.
