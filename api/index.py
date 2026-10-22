"""Entrada de Vercel: expone la app de Flask."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.web import app  # noqa: E402,F401
