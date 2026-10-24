"""One-command entry point; Python 3.10+, no third-party packages."""
import sys
from pathlib import Path

# Also supports embedded Windows interpreters that omit the script directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ridgeline.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
