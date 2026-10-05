"""Launch the optional experiment editor using the existing analysis environment."""

import sys
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY))
sys.path.insert(0, str(REPOSITORY / "src"))

if __name__ == "__main__":
    try:
        from gui.server import main
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"The CSV viewer needs the existing ACE-NeuroTools Python environment ({exc.name} is missing). "
            "Activate that environment and run this command again."
        ) from exc
    main()
