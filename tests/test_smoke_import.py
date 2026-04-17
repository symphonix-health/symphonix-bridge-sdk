from pathlib import Path
import sys


# Ensure src-layout package is importable in local repo test runs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_bridge_sdk_importable() -> None:
    import bridge_sdk  # noqa: F401
