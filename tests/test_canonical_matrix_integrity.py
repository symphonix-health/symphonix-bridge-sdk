"""Canonical matrix integrity tests — delegates to caid.matrices shared suite."""
import sys
from pathlib import Path

# Sibling-workspace path injection: caid-agent is checked out alongside
# this repo; its src/ must be on sys.path BEFORE we can import caid.matrices.
_SIBLING_CAID = Path(__file__).resolve().parents[2] / "caid-agent" / "src"
if _SIBLING_CAID.exists() and str(_SIBLING_CAID) not in sys.path:
    sys.path.insert(0, str(_SIBLING_CAID))

import caid.matrices._integrity_tests as _suite
_suite._REPO_ROOT = Path(__file__).parent.parent
_suite._cfg_cache = None  # clear cache in case module was imported earlier
from caid.matrices._integrity_tests import *  # noqa: F401, F403, E402
