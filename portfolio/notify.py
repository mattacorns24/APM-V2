"""Discord webhook notifications.

Reads DISCORD_WEBHOOK_URL from .env / environment. If unset, send() prints the
message and returns instead of raising, so routines never break on a missing
webhook. Delivery failures are reported but never propagate — a notification is
not worth aborting a trading routine over.

CLI: python -m portfolio.notify "message"   (sends a test message)
"""

import json
import os
import sys
import urllib.error
import urllib.request

from dotenv import load_dotenv

MAX_CONTENT = 1900  # Discord hard limit is 2000; leave headroom


def send(text: str) -> bool:
    """Post text to the Discord webhook. Returns True if delivered."""
    load_dotenv()
    url = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
    if not url:
        print(f"[notify skipped — DISCORD_WEBHOOK_URL not set]\n{text}")
        return False

    text = (text or "").strip()
    if not text:
        print("[notify skipped — empty message]")
        return False

    req = urllib.request.Request(
        url,
        data=json.dumps({"content": text[:MAX_CONTENT]}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "APM-V2 (https://github.com/mattacorns24/APM-V2, 1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                print(f"[notify failed — HTTP {resp.status}]")
                return False
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"[notify failed — HTTP {e.code}: {body}]")
        return False
    except Exception as e:  # network down, bad URL, timeout
        print(f"[notify failed — {type(e).__name__}: {e}]")
        return False

    print("[notify sent]")
    return True


if __name__ == "__main__":
    msg = " ".join(sys.argv[1:]) or "APM-V2 notification test"
    sys.exit(0 if send(msg) else 1)
