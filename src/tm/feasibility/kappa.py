"""Accord entre les deux annotateurs (kappa de Cohen) sur annotation_sample.csv.

Remplir label_A et label_B avec tracking / non_tracking / unsure (au moins 50
lignes annotées par les deux), puis :
  python -m tm.feasibility.kappa results/pilot/annotation_sample.csv

kappa = (p_o - p_e) / (1 - p_e), où p_o est l'accord observé et p_e l'accord
attendu par hasard. Interprétation (Landis & Koch) : < 0,40 faible ;
0,41-0,60 modéré ; 0,61-0,80 substantiel ; > 0,80 quasi parfait. Seuil du
projet : kappa >= 0,6.
"""
import csv
import sys
from collections import Counter


def cohen_kappa(a, b):
  n = len(a)
  observed = sum(x == y for x, y in zip(a, b)) / n
  ca, cb = Counter(a), Counter(b)
  expected = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
  return (observed - expected) / (1 - expected) if expected < 1 else 1.0, observed


def main():
  with open(sys.argv[1], encoding="utf-8") as fh:
    rows = [r for r in csv.DictReader(fh) if r["label_A"].strip() and r["label_B"].strip()]
  if len(rows) < 2:
    sys.exit("Pas assez de lignes annotées par les deux annotateurs.")
  a = [r["label_A"].strip().lower() for r in rows]
  b = [r["label_B"].strip().lower() for r in rows]
  k, observed = cohen_kappa(a, b)
  verdict = "GO" if k >= 0.6 else "NO-GO : préciser la grille d'annotation"
  print(f"n = {len(rows)} · accord brut = {observed:.3f} · kappa = {k:.3f} -> {verdict}")
  print("Désaccords :", Counter((x, y) for x, y in zip(a, b) if x != y).most_common(5))


if __name__ == "__main__":
  main()
