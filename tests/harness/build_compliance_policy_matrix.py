"""Shim — delegates to caid.matrices. Config: matrix_config.toml."""

from pathlib import Path
from caid.matrices import build_compliance_policy_matrix, load_config

ROOT = Path(__file__).parent.parent.parent
if __name__ == "__main__":
    build_compliance_policy_matrix(
        ROOT, load_config(Path(__file__).parent / "matrix_config.toml")
    )
