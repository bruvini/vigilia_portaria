"""Configuração da suíte: torna functions/vigilia_core importável."""

import sys
from pathlib import Path

_FUNCTIONS_DIR = Path(__file__).resolve().parent.parent / "functions"
if str(_FUNCTIONS_DIR) not in sys.path:
    sys.path.insert(0, str(_FUNCTIONS_DIR))
