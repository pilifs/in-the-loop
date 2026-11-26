"""Replay the alternative WebTestClient builder initializations on the O06 pins."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "tools"))
from targets.public_comparison import replay

if __name__ == "__main__":
    replay(HERE)
