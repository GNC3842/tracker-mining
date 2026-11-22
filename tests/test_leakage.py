"""Garde-fou anti-fuite : seuls les modules de labels, d'évaluation et de faisabilité
ont le droit de lire les labels (Tracker Radar / EasyPrivacy).
Tout module qui produit des FEATURES ou des GRAPHES ne doit jamais y accéder,
sinon les scores de T1 seraient gonflés artificiellement."""
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "tm"
ALLOWED = {"labels", "eval", "feasibility", "tools", "discover"}
FORBIDDEN = ("labels.parquet", "tm.labels", "tracker_radar", "easyprivacy", "load_tracker_radar")


@pytest.mark.parametrize("py", sorted(p for p in SRC.rglob("*.py")
                                      if p.relative_to(SRC).parts[0] not in ALLOWED),
                         ids=lambda p: str(p.relative_to(SRC)))
def test_no_label_access_outside_allowed_modules(py):
    text = py.read_text(encoding="utf-8")
    hits = [f for f in FORBIDDEN if f in text]
    assert not hits, f"{py.relative_to(SRC)} référence {hits}"
