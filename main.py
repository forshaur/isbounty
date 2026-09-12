"""Legacy entry point wrapper redirecting to isbounty.cli."""
import sys
from pathlib import Path

# Add src to path if running directly from git checkout
sys.path.insert(0, str(Path(__file__).parent / "src"))

from isbounty.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
