"""Allow running as `python -m gcia`."""
import sys
from gcia.launcher import main

if __name__ == "__main__":
    sys.exit(main())
