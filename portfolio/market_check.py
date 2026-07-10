"""Holiday/weekend guard for routines.

Usage:
    python -m portfolio.market_check
Exit 0 if the market opens (or opened) today, exit 3 if closed all day.
"""

import sys

from dotenv import load_dotenv

from . import broker


def main() -> None:
    load_dotenv()
    try:
        if broker.market_open_today():
            print("market open today")
        else:
            print("market closed today (weekend/holiday)")
            sys.exit(3)
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
