"""Run from any directory; outputs are never silently overwritten."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from quality_lab.pipeline import main  # noqa: E402

if __name__ == "__main__":
    main()
