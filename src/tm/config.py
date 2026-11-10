#Utiliser pour charger les parametres du projet depuis le fichier config.yaml
from pathlib import Path

import yaml

# src/tm/config.py -> racine = parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"


def load_config(config_path=None):
  """Charge config.yaml (ou le fichier donné)."""
  config_path = Path(config_path) if config_path else DEFAULT_CONFIG
  if not config_path.exists():
    raise FileNotFoundError(f"Configuration file not found: {config_path}")
  with open(config_path, "r", encoding="utf-8") as f:
    return yaml.safe_load(f)


def repo_path(rel):
  """Chemin absolu d'un chemin relatif à la racine du dépôt (absolu : inchangé)."""
  p = Path(rel)
  return p if p.is_absolute() else REPO_ROOT / p


def ensure_dir(p):
  d = repo_path(p)
  d.mkdir(parents=True, exist_ok=True)
  return d
