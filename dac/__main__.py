"""Allow running as `python -m dac`."""
import sys
from dac.launcher import main
if __name__ == "__main__":
    sys.exit(main())
