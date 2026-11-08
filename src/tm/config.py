#Utiliser pour charger les parametres du projet depuis le fichier config.yaml
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# src/tm/config.py -> racine = parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config.yaml"

def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
  """Load the configuration from a YAML file.
  Args:
      config_path (str | Path | None): Path to the configuration file. If None, uses the default config path.
  """
  if config_path is None:
      config_path = DEFAULT_CONFIG
  else:
      config_path = Path(config_path)

  if not config_path.exists():
      raise FileNotFoundError(f"Configuration file not found: {config_path}")

  with open(config_path, "r", encoding="utf-8") as f:
      config = yaml.safe_load(f)
  return config